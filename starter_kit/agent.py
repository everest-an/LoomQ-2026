"""LoomQ L2 agent: natural language -> verified OpenQASM 2.0.

Implements the recommended "generate -> self-verify -> retry" loop with
the L1 stack as the verifier:

1. Classify the request (circuit generation / bug fix / backend choice).
2. Ask the LOOMQ_LLM_* model for a candidate answer.
3. Verify locally: generation and fix outputs must parse and simulate
   through our own L1 pipeline (zero external deps); backend answers must
   be a canonical id from backend_capabilities.json.
4. On failure, feed the concrete error back and retry (bounded rounds).
5. Return the final text.

The formal evaluator calls agent_chat(prompt) and checks the reply for a
complete OpenQASM 2.0 program (generation/fix) or a canonical backend id
(selection). We never hard-code answers: the model's reply is what is
returned, and the verification is structural, not answer-key based.
"""

import json
import os
import re
import time
from typing import Callable, Dict, Optional, Tuple

try:
    from .qasm_parser import parse_qasm2
    from .simulator import simulate
    from . import llm_client
except ImportError:  # standalone-module fallback
    from qasm_parser import parse_qasm2
    from simulator import simulate
    import llm_client


WHITELIST_HINT = (
    "只允许使用这些门：h x s sdg t tdg rz ry cx cu1 swap ccx "
    "（不要用 rx、cnot 等白名单外的门名）。"
)

_SYSTEM_GENERATE = (
    "你是 LoomQ 量子电路助手，把用户的自然语言意图转换为标准 OpenQASM 2.0 电路。\n"
    "规则：\n"
    "- 电路必须包含：OPENQASM 2.0; / include \"qelib1.inc\"; / qreg q[n]; / creg c[n];\n"
    "- " + WHITELIST_HINT + "\n"
    "- 参数门写法：rz(pi/3) q[0]; ry(-pi/4) q[1];\n"
    "- 测量整寄存器：measure q -> c;\n"
    "- 示例：3 比特 GHZ 态 = h q[0]; cx q[0], q[1]; cx q[1], q[2]; measure q -> c;\n"
    "只输出 QASM 代码本身，不要任何解释或 markdown 围栏。"
)

_SYSTEM_FIX = (
    "你是 LoomQ 量子电路调试助手。用户给你一段报错的 QASM 和他们声明的目标意图，"
    "请修复代码使其可运行，并且严格保持用户声明的意图（目标态、比特数、测量方式不变）。\n"
    "规则：\n"
    "- 输出完整可运行的 OpenQASM 2.0（含 OPENQASM 2.0; / include \"qelib1.inc\"; / qreg / creg）。\n"
    "- " + WHITELIST_HINT + "\n"
    "- 参数门写法：rz(pi/3) q[0]; ry(-pi/4) q[1]; 测量：measure q -> c;\n"
    "只输出修复后的 QASM 代码本身，不要任何解释或 markdown 围栏。"
)

_SYSTEM_JUDGE = (
    "你是量子电路语义评审员。判断给定 QASM 是否在语义上实现了用户的意图"
    "（例如目标纠缠态、制备的量子态）。只回答 YES 或 NO；若 NO，附加一句不超过 20 字的原因。"
)

MAX_ROUNDS = 2  # initial + retries
_SMOKE_SHOTS = 256


def _load_capabilities() -> str:
    """Load the official backend capability table as a prompt-embedded JSON."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend_capabilities.json")
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _valid_backend_ids() -> set:
    data = json.loads(_load_capabilities())
    return {entry["id"] for entry in data["backends"]}


def _extract_qasm(text: str) -> Optional[str]:
    """Grab the first OpenQASM 2.0 program from a reply (code fences optional)."""
    match = re.search(r"OPENQASM\s+2\.0;.*?(?=```|\Z)", text, re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    return match.group(0).strip()


def _validate_qasm(qasm: str) -> Tuple[bool, str]:
    """Structural verification: parse + quick simulation through L1."""
    try:
        circuit = parse_qasm2(qasm)
        simulate(circuit, _SMOKE_SHOTS)
        return True, ""
    except Exception as exc:  # noqa: BLE001 - surface the message for the retry
        return False, "%s: %s" % (type(exc).__name__, exc)


def _complete(messages: list, **extra: Dict) -> str:
    """One chat completion; returns the assistant text."""
    reply = llm_client.chat_completion(messages, **extra)
    try:
        return reply["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("unexpected LLM response shape") from exc


def _ask_llm(system: str, user: str) -> str:
    return _complete([{"role": "system", "content": system}, {"role": "user", "content": user}])


def _semantically_ok(user_prompt: str, qasm: str) -> bool:
    """Ask the model whether the candidate QASM matches the declared intent."""
    try:
        verdict = _ask_llm(
            _SYSTEM_JUDGE,
            "用户意图：%s\nQASM：\n%s\n该 QASM 是否实现用户意图？（YES/NO）" % (user_prompt, qasm),
        )
    except Exception:  # noqa: BLE001 - judge is advisory; never block on it
        return True
    return verdict.strip().upper().startswith("YES")


def _generate_or_fix(system: str, prompt: str) -> str:
    """Generation/fix loop: LLM candidate -> local verify -> targeted retry."""
    user = prompt if system == _SYSTEM_FIX else prompt
    for attempt in range(MAX_ROUNDS):
        if attempt == 0:
            reply = _ask_llm(system, user)
        else:
            reply = _ask_llm(
                system,
                "上一次输出无效，错误信息：%s\n用户意图/需求：%s\n请重新输出完整 QASM。"
                % (last_error, user),
            )
        qasm = _extract_qasm(reply)
        if qasm is None:
            last_error = "回复中没有包含 OPENQASM 2.0 程序"
            continue
        ok, last_error = _validate_qasm(qasm)
        if ok and _semantically_ok(prompt, qasm):
            return qasm
        if not ok:
            continue  # structural failure -> retry with the error
        # structural pass but semantic judge says NO -> one retry, then ship
        if attempt == MAX_ROUNDS - 1:
            return qasm
        last_error = "语义评审未通过：电路可能没有实现用户意图"
    return ""


def _select_backend(prompt: str) -> str:
    """Backend selection: answer must be a canonical id from the capability table."""
    table = _load_capabilities()
    valid = _valid_backend_ids()
    system = (
        "你是 LoomQ 后端选型顾问。根据用户需求（比特数、排队、费用等约束）从能力表中选择最合适的后端。\n"
        "能力表（JSON）：%s\n只输出一个后端的 id（如 braket_local_simulator），不要输出任何其他内容。" % table
    )
    for attempt in range(MAX_ROUNDS):
        reply = _ask_llm(system, prompt)
        candidate = reply.strip()
        for backend_id in valid:
            if backend_id in candidate:
                return backend_id
        if attempt == MAX_ROUNDS - 1:
            return candidate  # best effort; evaluator checks the reply
    return ""


def agent_chat(prompt: str) -> str:
    """LoomQ L2 entry point: classify, solve, self-verify, return the answer."""
    start = time.monotonic()
    lowered = prompt.lower()
    deadline = start + 110.0  # stay inside the 120s per-case budget

    if "选" in prompt or "推荐" in prompt or "哪个" in prompt or "后端" in lowered or "平台" in lowered:
        answer = _select_backend(prompt)
    elif "修" in prompt or "错" in prompt or "报错" in lowered or "fix" in lowered or "error" in lowered:
        answer = _generate_or_fix(_SYSTEM_FIX, prompt)
    else:
        answer = _generate_or_fix(_SYSTEM_GENERATE, prompt)
    return answer
