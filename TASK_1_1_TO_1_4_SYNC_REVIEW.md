# task-1-1 ～ task-1-4 主页修改清单（简洁版）

沿用现有页面的小节、英文语气和大致篇幅，原位替换过时的数字与规则。需要解释的变化控制在一两句内，数据筛选和实现细节由 benchmark 仓库承载。

依据：2026-09-23 核对的 benchmark `aa34151`。已按清单完成四个任务页及目录文案的本地修改，HTML 已重新生成，生成一致性与 diff 空白检查通过。以下保留修改前行号和审阅文案。

## task-1-1

文件：[content/tasks/task-1-1.md](content/tasks/task-1-1.md)。只需修改 Inputs 和 Evaluation。

| 位置 | 修改内容 |
| --- | --- |
| Inputs，原第 25 行 | public query 数量：`3 → 10`。 |
| Evaluation，原第 36–40 行 | 明确有 10 条 hidden query；将“全部命中才得 1 分”改为按 Top-3 命中比例给分；用一句话说明执行、输出或审查失败会使总 reward 为 0。 |

Evaluation 建议直接替换为一个短段落：

> The verifier evaluates 10 hidden queries. A query is a hit when at least one relevant document appears in its top three results. Reward is the fraction of queries hit. Execution or output-validation failure, or a failed trajectory audit, sets the final reward to `0`.

依据：[任务 README](../search_swe_main/tasks/task-1-1/README.md)、[评分实现](../search_swe_main/tasks/task-1-1/tests/grader.py)。

## task-1-2

文件：[content/tasks/task-1-2.md](content/tasks/task-1-2.md)。修改两条运行限制、public 数量和 Evaluation 的首段。

| 位置 | 修改内容 |
| --- | --- |
| Runtime，原第 19 行 | `120 seconds` 后补充 `including index construction and service startup`。 |
| Runtime，原第 20 行 | `0.5 seconds` 后补充 `per invocation, measured from process start to exit`。 |
| Inputs，原第 29 行 | public query 数量：`5 → 20`。 |
| Evaluation，原第 37 行 | 改为 20 条 hidden query，每条同时评估 Top-3 命中和时延；得分为逐 query 得分均值。单条失败得 0，build / 整体评估 / 审查失败则总 reward 为 0。 |

Evaluation 首段建议替换为：

> The verifier evaluates 20 hidden queries. A query scores `1` only if its invocation succeeds within `0.5 seconds`, its output is valid, and a relevant document appears in the top three results; otherwise it scores `0`. Reward is the mean of these per-query scores. Build or overall evaluation failure, or a failed trajectory audit, sets the final reward to `0`.

这段同时更新了旧的“质量集 + 独立性能集”和“全部通过才得分”两处规则，并说明 `Accuracy@3` 包含时延门槛。

依据：[任务 README](../search_swe_main/tasks/task-1-2/README.md)、[任务 instruction](../search_swe_main/tasks/task-1-2/instruction.md)。

## task-1-3

文件：[content/tasks/task-1-3.md](content/tasks/task-1-3.md)。三处局部替换即可。

| 位置 | 修改内容 |
| --- | --- |
| Inputs，原第 27 行 | public question 数量：`25 → 10`。 |
| Evaluation，原第 38 行 | hidden question 数量：`25 → 10`。 |
| Outputs，原第 32 行 | 在 `evidence` 后加简短解释：`the PDF filename without the .pdf extension`。 |

现有评分和失败规则继续适用：执行失败或结构无效仍会使整份提交无效。

依据：[任务 README](../search_swe_main/tasks/task-1-3/README.md)、[任务 instruction](../search_swe_main/tasks/task-1-3/instruction.md)。

## task-1-4

文件：[content/tasks/task-1-4.md](content/tasks/task-1-4.md)。在现有各小节内同步单 PDF 设定和执行规则。

| 位置 | 修改内容 |
| --- | --- |
| 概述，原第 3 行 | 改为在一份长 PDF 内定位证据，输入为自然语言 query。 |
| Primary focus，原第 8 行 | 将 `in long PDFs` 改为 `in a long PDF`。 |
| Runtime，原第 20 行附近 | 补一条 `Per-query limit: 900 seconds, with up to five concurrent invocations`；保留整组 query 共享 `1,800 seconds` 的限制。 |
| Inputs，原第 26 行 | `six public development PDFs` 改为 `one 2,043-page PDF of War and Peace`。 |
| Inputs，原第 27 行 | public query 数量：`30 → 10`；短句说明所有 query 对应同一 PDF。 |
| Inputs，原第 28 行 | `ground_truth.jsonl → golden_answers.jsonl`，说明提供物理页码标签和证据摘录。 |
| Evaluation，原第 36 行 | 改为在同一 PDF 上重新构建，评估 10 条 hidden query。 |
| Evaluation，原第 36–42 行 | 单条执行失败或输出无效记 0，仍计入全部 10 条 query 的平均分；共享 build/setup 或审查失败使总 reward 为 0。公式明确 reward 为平均 Recall@5，展示 score 为其 100 倍。 |

概述建议替换为：

> Build an executable evidence-localization system over a single long PDF. Given a natural-language query, return the physical pages that best contain the relevant evidence.

Evaluation 首段建议替换为：

> The verifier rebuilds the system on the same PDF and evaluates 10 hidden queries. For each query, `Recall@5` is the fraction of all relevant evidence pages retrieved in the top five. Reward is the mean across all 10 queries, with failed or invalid queries contributing zero.

沿用现有公式块，写为：

```text
reward = average(Recall@5)
score = 100 * reward
```

末段收为：

> Page relevance is scored deterministically; no model judges answer correctness. Shared build/setup failure or a failed trajectory audit sets the final reward to `0`.

依据：[任务 README](../search_swe_main/tasks/task-1-4/README.md)、[任务 instruction](../search_swe_main/tasks/task-1-4/instruction.md)、[资源清单](../search_swe_main/tasks/task-1-4/assets.json)。

## 目录文案与生成文件

[content/tasks/catalog.json](content/tasks/catalog.json) 中，仅建议将 task-1-4 的 summary 做一个短语替换：`a target long PDF → a single long PDF`。其余三个任务的卡片概述仍准确。

实际修改时，编辑上述四份 Markdown 和这一处 catalog 文案，再完整生成任务页及目录：

```bash
python scripts/build_tasks.py
python scripts/build_tasks.py --check
git diff --check
```
