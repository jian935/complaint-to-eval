# complaint-to-eval

**用户早就把评测集写好了，只是你没把它变成评测集。**

把用户吐槽转成 AI Agent 的**未人工复核的回归用例候选**：带原文证据的缺陷分类法、
每条发现对应的最小复现输入、以及两个版本之间的 diff。确定性规则、纯标准库、
零 API Key、不调用模型。

![complaint-to-eval 在终端跑 demo](assets/demo.gif)

_由 `scripts/make_demo_gif.py` 直接抓真实 `cte demo` 输出渲染；gif 里的数字来自
那次真实运行，不是手敲的。_

```text
$ python -m complaint_to_eval demo
records=12 candidates=11 accepted=0
provenance=synthetic (FABRICATED; demo artefact only, never a metric)
wrote out/demo/report.json
wrote out/demo/report.md
wrote out/demo/promptfoo-candidates.json
```

**注意**：`accepted = 0`。目前还没有人工标注集。本工具产出的一切都是
**candidate（候选）**，不是标注样本，不能用来报准确率、精确率、召回率、覆盖率或修复率。
见[诚实边界](#诚实边界)。

[English README](README.md)

## 为什么做这个

用 Agent 的团队都在收集吐槽：GitHub issues、客服工单、应用评论、对话日志。
但这些吐槽几乎从没变成测试。下游工具其实已经很成熟：promptfoo、Langfuse
能跑评测集、能进 CI 门禁。缺的是上游：**评测集从哪来，谁判定「这条吐槽属于这类缺陷」？**

本项目补这一段。它不跑评测，只产出「人类可以据此整理成评测集」的原料。

## 快速开始

无需安装：

```bash
git clone <this-repo> && cd complaint-to-eval
python -m complaint_to_eval demo
```

或安装 `cte` 命令：

```bash
pip install .
cte run --input feedback.jsonl --real --out out/report
```

`--real` 是声明「已核对语料的许可与授权」；编造数据用 `--synthetic`。
两者都不写会被标成 `provenance: unspecified` 并打印警告。

## 输入格式

`.jsonl` 或 `.csv`，`//` 开头的行会被忽略。

```json
{"id":"r1","text":"回答里直接编造数据，说转化率是 87%。","source":"github-issues","product":"demo","version":"v1"}
```

正文字段可用 `text` / `feedback` / `body` / `content` / `comment`；
可选 `source` / `product` / `version`；没有正文的行跳过。

**脱敏发生在分类和引用之前**，证据里的偏移量指的是脱敏后的文本。

## 产出

| 文件 | 内容 |
| --- | --- |
| `report.json` | 发现、candidate 用例、计数、数据来源、警告 |
| `report.md` | 可读报告，顶部重复完整诚实声明 |
| `promptfoo-candidates.json` | 供人工挑选后复制进配置的暂存测试 |

## 命令

| 命令 | 用途 |
| --- | --- |
| `cte demo` | 跑内置**编造**示例数据 |
| `cte run --input F --out D [--synthetic\|--real]` | 分析反馈文件 |
| `cte diff --base A.json --head B.json` | 对比两次运行（仅 candidate） |
| `cte validate --labels F.jsonl` | 检查标注文件结构 |
| `cte taxonomy` | 打印草稿分类法并校验不变量 |
| `cte privacy --path DIR` | 扫描数据文件里残留的个人信息 |

## 边界：它不是什么

- **不是评测框架，也不是可观测平台**。它给 promptfoo / Langfuse 喂数据，不替代它们。
  `promptfoo-candidates.json` 故意**不是**可直接运行的 promptfoo 配置——把未复核的
  candidate 直接塞进 CI，正是本项目要反对的做法。
- **不是 Agent 框架、harness 或记忆层**，那些位置已经没有缝隙。
- **不是发布门禁**：[release-contract](https://github.com/jian935/release-contract)
  负责判断「基于离线证据能不能发」，本项目负责回答「该测什么」。两者是上下游，
  输入与产出都不同，互不引用对方的结论或数字。
- **不是「需求文档 → 测试用例」生成器**：ASSERT 从需求出发，本项目从用户真实不满出发。
- **不是论文分类法**：MAST 是学术分类，本项目交的是可运行、可版本化、可复跑的流水线。
- **不是作者旧项目的延续**：`ai-claim-audit` 审 AI 输出里的数字，
  `experiment-copilot` 判 A/B 实验能不能上线，`career-loop` 做 JD×经历匹配。
  输入、产出、要回答的问题都不同。迁移过来的是方法：语境约束、否定辖域、
  人工标注纪律、脱敏先行。

## 诚实边界

1. 产出全部是未复核的 **candidate**；v0.1 没有人工标注，`accepted_cases` 恒为 `0`。
2. `complaint_to_eval/demo.jsonl` 是**编造的**，而且刻意写进了分类法里的原词，
   所以命中数高是文件写法决定的，不是能力证明。每份报告都会重复这句。
3. 分类法是**草稿**（`0.1.0-draft`）。任何精确率、召回率、覆盖率、一致性数字
   都没有计算、没有声称、也不暗示。
4. `cte diff` 比的是 candidate 上命中的短语，报的是 `resolved_candidates`，
   明确**不是**修复率。
5. 人工标注与规则冲突时，**改标注，不改引擎**。完整规则见
   [eval/ANNOTATION_GUIDE.md](eval/ANNOTATION_GUIDE.md)。
6. 原始语料放 `.local/`（已 gitignore）；公开仓库只放聚合数字与脱敏后的引用。

## 路线

| 阶段 | 交付 |
| --- | --- |
| L1（当前） | 单点 CLI + 可安装的 Agent Skill |
| L2 | 300 条人工标注、双标注者、公开一致性与混淆矩阵、dev/hold-out、版本化 accepted 集进 CI |
| L3 | 社区提交 badcase + 每周回归报告 |

L1 阶段最欢迎的贡献是**反向测试**：给一句当前规则判错的文本，附上正确判定。
不要只丢一个新关键词——必须带上失败样例和基于标注集的精确率检查；
泛词靠同行语境约束解决，不靠加词。

## 许可

MIT · Copyright (c) 2026 jian935
