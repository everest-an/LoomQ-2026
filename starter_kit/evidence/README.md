# LoomQ 人工评分证据

## 队伍信息

- 团队名称：everest-an
- 提交账号（Team ID）：everest-an

这份文件是人工评分材料的统一入口。请直接编辑它，只填写要申报的项目。截图、原始结果或图表统一放在 `starter_kit/evidence/files/`，也可以引用 `starter_kit/` 中已有的代码和文档。

证据包是可选的。没有申报某项人工分时，留空即可，不影响自动评分。

## 提交前填写

把要申报项目的方框改成 `[x]`，并填写对应内容：

- [ ] L1 真机
- [x] L2 交互体验
- [x] 工程与产品化
- [ ] 自定义量子 RISC-V Bonus
- [ ] 新手引导与视觉叙事 Bonus

## L1 真机

每个有效真机平台计 5 分，最多两个平台。模拟器不计真机分。每个平台复制并填写一次下面的信息：

```text
平台名称：[填写]
平台 job ID：[填写]
运行时间：[填写，带时区]
shots：[填写]
实际执行的 QASM：[填写仓库内路径]
平台返回的原始结果：[填写仓库内路径]
任务页截图：[选填，填写仓库内路径]
```

建议把文件放进 `evidence/files/`，比如：

```text
evidence/files/spinq-circuit.qasm
evidence/files/spinq-result.json
evidence/files/spinq-screenshot.png
```

工作人员会核对 job ID、运行时间、电路、shots 和原始结果。截图只能辅助说明，不能代替 job ID 和原始结果。

## L2 交互体验

请填写：

```text
启动界面或 CLI 的命令：[见下方「启动方法」]
测试入口或页面地址：[无，CLI 交互终端]
适合现场体验的 3 个用户任务：
1. [任务 A] 输入「生成一个 3 比特 GHZ 纠缠态」——观察 CLI 自动生电路、本地验证并画出 000/111 各约 50% 的分布图
2. [任务 B] 输入「我想制备贝尔态，但这段代码报错了帮我修好：H q[0]; CX q[0] q[1]」——观察纠错闭环返回可运行电路并显示贝尔态分布
3. [任务 C] 输入「我需要运行一个 15 比特电路，且零排队等待，选哪个平台？」——观察 Agent 依据后端能力表给出规范后端 id
截图或演示视频：[选填]
```

**启动方法**（在 fork 根目录，需配置 LOOMQ_LLM_* 环境变量）：

```bash
export LOOMQ_LLM_BASE_URL=<OpenAI-compatible 地址>
export LOOMQ_LLM_API_KEY=<你的 Key>
export LOOMQ_LLM_MODEL=<模型名>
python3 starter_kit/cli.py
# 可选：python3 starter_kit/cli.py --backend braket --shots 8192
# 单轮模式：python3 starter_kit/cli.py --prompt "生成一个 2 比特贝尔态"
```

CLI 内置新手引导（欢迎页 + help 命令）、电路可视化（ASCII 分布条）和
「生成 → 本地验证 → 重试」闭环；每轮回答都会在本地通过 L1 中间层实际
模拟验证并给出结果解读。

工作人员会在组委会统一模型环境中运行最终代码，测试新手是否看得懂、出错后能否得到有效帮助、结果是否清楚，以及多轮回答是否一致。选手自己的对话截图只用于说明产品流程，不直接证明得分。

## 工程与产品化

已有内容可以直接引用主 README 或其他项目文档，不必复制到本目录。

```text
干净环境中的构建和启动命令：
  python3 starter_kit/evaluator.py --level declared --target spinq,originq,braket   # 契约自测（零第三方依赖）
  python3 starter_kit/selftest_fhb.py    # FHB 闭式解自测（易经卦象 ↔ 超立方体量子游走）
  python3 starter_kit/selftest_l3.py     # Hybrid-QASM 混合编译穷举自测
  python3 starter_kit/selftest_roundtrip.py  # 隐藏电路风格 round-trip 语义自洽
  python3 starter_kit/cli.py             # L2 交互入口
架构说明：见 starter_kit/PROJECT.md（parser → 统一 IR → 模拟器/三后端 codegen 三段式，零第三方依赖）
目标用户和使用场景：没有量子背景的跨界创作者/学生/产品经理——用自然语言驱动量子模拟器与云端真机
完整使用流程：见 starter_kit/PROJECT.md「快速上手」与 CLI 欢迎页
```

工作人员会按最终 commit 实际构建和启动，并检查文档与代码是否一致、产品是否真的降低了量子计算的使用门槛。

## 自定义量子 RISC-V Bonus

以下三项必须齐全且测试通过，才获得 8 分：

```text
指令编码规格：[填写文档路径]
模拟器扩展实现：[填写代码路径]
端到端测试命令：[填写命令或文档路径]
```

## 新手引导与视觉叙事 Bonus

请填写已有材料的路径，不要求为评分另写一套文档：

```text
零基础首次运行指南：[填写]
量子概念解释：[填写]
结果可视化：[填写]
错误恢复或无障碍引导：[填写]
```

以上四项各 1 分。普通项目 README 完整不代表自动获得 Bonus。

## 提交规则

- 所有材料都要在截止前进入最终提交的 commit，工作人员不接受截止后补交。
- 外部视频可以用稳定只读链接，源码、原始结果和复现命令应保存在仓库中。
- 整个 fork commit 的归档包不得超过 100 MiB。
- 不要提交 API Key、Token、Cookie、个人身份信息或平台账户隐私。
- 如申报 L1 真机分，在最终提交 Issue 的 `Hardware evidence` 中填写 `starter_kit/evidence/README.md`。
