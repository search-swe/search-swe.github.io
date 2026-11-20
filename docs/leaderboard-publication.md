# Leaderboard：从本地预览发布到 Hugging Face

官网保持静态 HTML/CSS/JS。榜单及任务分数随网站发布，轨迹、日志和文件预览
从公开的 HF Dataset [`search-swe/trajectories`](https://huggingface.co/datasets/search-swe/trajectories)
匿名按需读取。浏览器不需要 HF Token。

## 当前更新：PR #3 的 Sonnet 5.5 与 Gemini 4 Argon

两组各 47 题，均分分别为 38.42 和 34.02。条目详情的 Provider 为 Vertex AI。
Sonnet 使用 Claude Code 2.1.309 / max。Argon 使用 Antigravity CLI 1.5.2 / high。
贡献者提供 91 条选定轨迹。Sonnet 的 `rust-bm25-search` 和两组的
`large-scale-formula-retrieval` 使用归档中的 OpenRouter 补跑，逐题保留实际路由。
Sonnet 费用使用 Claude Code 记录的估算。Argon 的 token 和费用显示为缺失。
8 条贡献者轨迹缺少完整的原始时间戳，耗时使用第一步至最后一步的记录，详情中注明估算依据。

来源固定在 [PR #3](https://github.com/search-swe/search-swe.github.io/pull/3) 的第二轮复评
及 `content/leaderboard/community-source-evidence.json` 中的 HF SHA。
发布包 `.build/hf-trajectories-pr3` 在 GLM 包上追加 94 条轨迹，现有 846 条。
生产榜单固定在通过远端核验的版本
[`0d3e242e805487877b4bde293d0e831ce0f56c29`](https://huggingface.co/datasets/search-swe/trajectories/commit/0d3e242e805487877b4bde293d0e831ce0f56c29)。
Argon 的 Rust BM25 分数与贡献者的原始评分报告一致。

```bash
python scripts/download_pr3_results.py
python scripts/publish_pr3_results.py --upload
```

后续发布以 `.build/hf-trajectories-pr3` 为基线。发布包准备完毕后可沿用同一文件集续传。

```bash
python scripts/append_hf_trajectories.py --base-package .build/hf-trajectories-glm53-tokenplus --package .build/hf-trajectories-pr3 --published-base --upload
```

## 历史更新：GLM 5.3 与 GLM 5.3 Flash

2026-11-19 新增 GLM 5.3 和 GLM 5.3 Flash，各 47 题，均为 Claude Code 2.1.309 / max。
均分分别为 18.3592699115 和 16.3564352232。前端 Provider 显示 Z.ai，详情记录
SiliconFlow TokenPlus 路由及请求模型的 `?provider=z-ai`。现为 14 个模型、16 个 settings、
752 条结果。24,274 个源文件（103,578,605,907 bytes）通过大小和 SHA-256 校验。

GLM 5.3 的 composed-image-search、layout-page-search、same-place-image-search、
sketch-text-search 和 visual-document-qa 在 Claude Code 尝试读取图片后停止，
按已归档裁定计 0 分，并在榜单与试验详情标注。两组共 7 条重评分复用原编码耗时和用量。
两组各 47 题均有原始耗时。GLM 5.3 的 budgeted-bimetric-retrieval 使用和 ATIF
总计一致的去重会话回执，覆盖最终 CLI 调用之前的记录。

总用量和参考费用分别为 GLM 5.3 的 580,262,443 tokens / $191.41086788，以及
Flash 的 663,177,282 tokens / $24.80453692。费用采用 [智谱官方 USD 标准价](https://docs.z.ai/guides/overview/pricing)。
本地包为 `.build/hf-trajectories-glm53-tokenplus`，基线为 `.build/hf-trajectories-step5`。
官网引用的不可变 HF 版本以 `content/leaderboard/storage.json` 为准。

```bash
python scripts/publish_final_results.py --base-package .build/hf-trajectories-step5 --package .build/hf-trajectories-glm53-tokenplus --upload
```

续传用 `scripts/append_hf_trajectories.py` 及相同参数。下一次追加使用
`.build/hf-trajectories-glm53-tokenplus` 作为基线。

## 历史更新：Step 5 Preview / Claude Code / max

2026-11-18 新增 Step 5 Preview / Claude Code 2.1.309 / max，Provider 为 StepFun，
覆盖 47/47 题，平均 19.4745596453。现为 12 个模型、14 个 settings、658 条结果。
原 611 条结果、用量、耗时、费用和公开 payload 字节全部保留。PR #3、Sonnet、Argon 当时仍暂缓。

16,255 个原始归档文件（41,169,460,843 bytes）再次通过大小及 SHA-256 核验。
大二进制产物仍只列清单，公开包包含轨迹、会话、文本日志和证据。
七道重评分题的原编码材料通过冻结的逐文件哈希与原始 UUID 绑定，证据保存在
coding-source-evidence.json；公开 Agent 文件组补充 original-coding/ 下的 result、
config 和 harness。全部 47 题有原始编码时长；evolving-personal-memory 和
instruction-following-embedding 恢复为 7201.643989 / 7201.056449 秒，无新增估算。

总用量 800,569,286 tokens；34 题使用最终累计计数，13 题沿用去重的已记录响应
回退规则，不估算未记录用量。三道题原有 API_TRANSPORT_DEGRADATION_RECORDED
标记保留在单题证据中。费用按阶跃星辰官方标准 USD 实时价估算，每百万未缓存
输入／缓存读取／输出为 $1.00／$0.10／$2.70；缓存填充按普通输入价，思考已包含
在输出中，不叠加计费。总费用 $119.1053147，不应用订阅或账户优惠。
来源：[StepFun 官方价格表](https://platform.stepfun.ai/docs/en/guides/pricing/details)。

当前包为 .build/hf-trajectories-step5，基线为 .build/hf-trajectories-hy4；公开包共
314,927 个文件、约 11.59 GiB，包含 658 份 ATIF 和 669 份原始会话 JSONL。
准备及上传：

```bash
python scripts/publish_final_results.py --base-package .build/hf-trajectories-hy4 --package .build/hf-trajectories-step5 --upload
```

准备完成后的续传命令：

```bash
python scripts/append_hf_trajectories.py --base-package .build/hf-trajectories-hy4 --package .build/hf-trajectories-step5 --upload
```

逐文件远端核验、匿名下载及 CORS 校验通过后，脚本固定 HF SHA 并生成生产页面。
当前版本记录在 content/leaderboard/storage.json，完整私有回执为
.build/hf-trajectories-step5-uploaded.json。后续追加以 Step 5 包为 --base-package，
保留社区结果及所有既有 payload。
本次固定版本为
[`a4d445dc0b8f8324fbc959fe57885c5474c7b939`](https://huggingface.co/datasets/search-swe/trajectories/commit/a4d445dc0b8f8324fbc959fe57885c5474c7b939)。

本次帕累托图将模型名称从圆点链接中拆出，名称本身不触发悬浮；仅圆点触发，
提示按实际屏幕位置定位并显示模型 / harness。标签在对应点附近避让，桌面图高
520px，窄屏保持 330px 并使用完整图例；键盘聚焦与点击入口保留。Cost、Tokens、
Time 继续使用线性横轴，DeepSeek 仍只展示整体均分最高的 Claude Code。

## 历史更新：Hy4 / Claude Code / high

2026-11-17 接纳、2026-11-18 发布 Hy4 / Claude Code 2.1.309 / high，覆盖 47/47 题，平均
21.5478648705。现为 11 个模型、13 个 settings、611 条结果。43 题来自已审查的
社区包，4 题来自本地选中档案；Provider 在前端统一显示 Tencent，采用常规榜单展示。
原 564 条结果、用量、耗时、费用与公开 payload 保持不变。当时 Step-5-preview、
PR #3、Sonnet、Argon 继续暂缓。

使用最终 modelUsage 累计数恢复原导出遗漏的 10,260,191 tokens；总用量为
795,131,123 tokens。四道仅有 CLI 的题修正了派生 ATIF 版本和最终累计指标，
逐步输出用量仍为未知，不虚构逐响应计数或请求 ID。全部 47 题都有原始 coding
时长，无新增估算。原始执行记录不改写，源材料哈希固定在
content/leaderboard/community-source-evidence.json。

费用按腾讯官方标准实时 USD 目录价估算：每百万未缓存输入／缓存读取／输出为
$0.834／$0.042／$2.501，不应用临时促销与账户折扣；最终计数与逐响应记录只计一次。
总费用为 $143.890236356，不代表内部端点或 OpenRouter 的实际账单。
来源：[腾讯官方价格表](https://www.tencentcloud.com/document/product/1300/78937)。

该次包为 .build/hf-trajectories-hy4，基线为 .build/hf-trajectories-mimo。
公开包共 286,268 个文件、约 10.48 GiB，包含 611 份 ATIF 和 619 份原始会话 JSONL。
脚本仅导出选中记录，不包含 Mac 附加元数据。首次准备及上传：

```bash
python scripts/import_hy4_results.py --upload
```

准备完成后，中断续传可直接使用：

```bash
python scripts/append_hf_trajectories.py --base-package .build/hf-trajectories-mimo --package .build/hf-trajectories-hy4 --upload
```

上传、逐文件远端核验与匿名下载/CORS 校验通过后，脚本固定 HF 版本并生成本地
production 页面；官网 Git 提交和推送仍单独执行。本次 HF 固定版本为
[`75abb07ad387c478060ece8d216a854ffdfdf2c4`](https://huggingface.co/datasets/search-swe/trajectories/commit/75abb07ad387c478060ece8d216a854ffdfdf2c4)。
后续原生结果增量导入须将
包含 Hy4 的已验证包作为 --base-package，以保留社区结果及其 payload。

## 历史更新：MiMo-V2.6-Flash / Pro

2026-11-17 新增两组 Claude Code 2.1.309 / OpenRouter / max，各 47 项：Flash
平均 15.2727619964，Pro 平均 18.6302226440。现为 10 个模型、12 个 settings、
564 条结果。原 470 条结果、用量、耗时、费用和公开 payload 字节保持不变。

Provider 简写 Xiaomi，详情保留 Xiaomi (via OpenRouter)。依据是用户确认生效的
provider allowlist 与官方 OpenRouter 模型端点的交集；保留 OpenRouter API 渠道。
DeepSeek 的 Pareto 选择仍为整体均分最高的 Claude Code；MiMo 两模型均正常展示。

94 项原始档案的 81,855 个文件通过大小与 SHA-256 核验。Flash 的
budgeted-bimetric-retrieval 和 constrained-molecular-search 是 NoP 重评分，原编码
材料通过 UUID、轨迹和逐文件哈希绑定后，在公开 Agent 文件组的 original-coding/
补充导出。固定证据为 content/leaderboard/coding-source-evidence.json，不修改原始
final-trajectories。真实耗时为 7201.120332 / 16127.410464 秒，无新增耗时估算。
Flash instruction-following-embedding 已有原生会话，另在 coding-time-evidence.json
固定其原始 result 和 7201.244785 秒耗时，并导出原始 result。
Molecular 使用原始最终累计数，多计入 ATIF 未汇总的 352,574 tokens；保留 Source2
条件性 coding eligibility、只读 observation 扩展与额外 NoP 机会的来源记录。

Flash 总 tokens 474,136,575，Pro 565,324,699；分别 25/15 项没有最终累计计数，
沿用已记录主/子 agent 响应按 message ID 去重后的最终报告口径，不推算后台缺失用量。
小米官方标准实时 USD 每百万 input/cache read/output 费率分别为
Flash $0.14/$0.0028/$0.28、Pro $0.435/$0.0036/$0.87，来源为
[Flash](https://mimo.mi.com/models/en-US/mimo-v2.6-flash) 和
[Pro](https://mimo.mi.com/models/en-US/mimo-v2.6-pro)。不用订阅、batch 或 harness 猜测费用。
两组估算总费用分别为 Flash $6.0017513024、Pro $17.1207614100。

当前包为 .build/hf-trajectories-mimo，基线为 .build/hf-trajectories-ds-cc-pi-kimik3。
公开包 267,627 个文件、约 9.45 GiB；本次新增约 2.54 GB，含 564 个 ATIF 和
573 份原始会话 JSONL（235 Codex、291 Claude Code、47 Pi）。
当时 Step-5-preview、PR #3、Sonnet、Argon 继续暂缓。

```bash
python scripts/publish_final_results.py --base-package .build/hf-trajectories-ds-cc-pi-kimik3 --package .build/hf-trajectories-mimo --upload
```

已完成上传并固定 HF 版本
[`16c6a5e364e2a09609cf85df85484795dcbbe4e8`](https://huggingface.co/datasets/search-swe/trajectories/commit/16c6a5e364e2a09609cf85df85484795dcbbe4e8)。
267,627 个远端文件的大小、内容哈希及匿名下载/CORS 均通过；另对两组 MiMo
及补充的原始编码材料完成 13 项匿名下载抽查。本地 storage.json 和 579 个
production 文件已更新到该版本；网站 Git 提交与推送单独执行。

## 历史更新：DeepSeek Claude Code / Pi 与 Kimi K3

2026-11-16 新增三个 max settings，各 47 项，共 141 条：DeepSeek / Claude Code
2.1.309 平均 27.5927375730；DeepSeek / Pi 1.4.0 平均 18.4387816458；
Kimi K3 / Claude Code 2.1.309 平均 25.3719202415。现有 8 个模型、10 个 settings、
470 条结果，主榜保留 DeepSeek 的 Codex、Claude Code、Pi 三行。
帕累托图各维度和硬件范围仅保留整体平均分最高的 DeepSeek / Claude Code。

新增结果的原始文件大小与 SHA-256 全部通过。8 条重评分缺失耗时从源机器原始
Harbor result 恢复，原生会话哈希与归档匹配，证据固定在
`content/leaderboard/coding-time-evidence.json`。本次无新增估算耗时。
Pi 的 agentic-search-vectorless、budgeted-candidate-reranking、document-page-search
原生会话比 CLI/ATIF 多出末尾响应，按 response ID 合并去重后计入用量。
DeepSeek Claude Code 的 6 条与 Kimi K3 的 14 条缺少最终累计计数，沿用已记录响应
汇总口径；不完整零 token 流头不当作完整回执，存在累计计数时由累计数覆盖。

DeepSeek 三种 harness 均采用官方谷价；Kimi K3 每百万 input/cache read/5-minute
write/output 为 $3/$0.30/$3/$15，来源为 [Moonshot 官方价格表](https://platform.kimi.ai/)。
Provider 分别为 DeepSeek via OpenRouter 和 Moonshot AI。
当时 Step-5-preview、PR #3、Sonnet、Argon 继续暂缓，不包含在该次发布中。

当前包为 `.build/hf-trajectories-ds-cc-pi-kimik3`，基线为
`.build/hf-trajectories-astra-deepseek`，保留原 329 条结果和全部 payload 字节。
公开包共 206,227 个文件，约 7.09 GiB，包含 470 个 ATIF 和 478 份原始会话文本；
本次新增公开数据约 3.01 GB。新增费用为 DeepSeek / Claude Code $16.609308594、
DeepSeek / Pi $7.392789384、Kimi K3 / Claude Code $290.1819234。

```bash
python scripts/publish_final_results.py --base-package .build/hf-trajectories-astra-deepseek --package .build/hf-trajectories-ds-cc-pi-kimik3 --upload
```

上传并核验后更新本地 production 页面；网站 Git 提交与推送独立于 HF 上传执行。
已核验 HF 固定版本为
[`5b68ad4b54187858faab15eebc2603f63d7a1bcd`](https://huggingface.co/datasets/search-swe/trajectories/commit/5b68ad4b54187858faab15eebc2603f63d7a1bcd)，
全部 206,227 个远端文件哈希及匿名下载/CORS 通过；该次发布后的本地 storage.json 与该版本一致。

## 历史更新：加入 GPT-6 Astra 和 DeepSeek V4.1 Flash 1017

共 7 个榜单条目、329 条结果。两组新增结果均为 **Codex 0.164.0 / max**，
各覆盖 47 个任务，均分分别为 **45.9273539796** 和 **21.0540612397**。
28,868 个源文件（59,761,934,520 字节）的大小和 SHA-256 全部核验通过。
94 份原生会话的逐响应 token 总数与最终 thread 计数一致。
Astra 原始解题时长完整；DeepSeek 的 `spoken-query-search` 按用户指定记为
7200 秒，参与展示和平均耗时统计。原始结束时间仍为空，赋值依据保存在
`agent_time_basis`，并按原始轨迹 SHA-256 固定在导入逻辑中。
另有七条既有缺失耗时按同一规则补为 7200 秒：Luna 的 agentic-search、
scientific-paper-qa；Terra 的 visual-document-qa；Kimi 的 evolving-personal-memory、
incremental-vector-search、long-pdf-evidence-vectorless、paper-metadata-retrieval。
其中六条原始会话覆盖到两小时预算附近；Terra 的原始 Harbor 记录确认
7200.519128 秒后 AgentTimeoutError，且会话 SHA-256 与归档一致。
当前 329 条结果都有耗时，每个模型均为 47/47；原始时间戳和终止状态不改写。

保留已核验的有效零分：DeepSeek 多语言任务执行的 `pkill` 终止了 Codex；
query-encoder-alignment 有健康完成的完整性拒绝；filtered-ann-retrieval 构建超时。
Astra agentic-search 用尽两小时预算，末尾重连已由原评测审查确认可接受，
最终测量和三次审查均健康完成。原记录不改写，也不因低分重新解题。

Provider 显示：Astra/Sol 为 OpenAI，Kimi 为 Moonshot AI，Luna/Terra/Opus
为 OpenRouter，DeepSeek 表格简写为 **DeepSeek**，模型页副标题注明
**DeepSeek via OpenRouter**，详情和下载保留完整渠道。后者依据用户确认的
Guardrail 与官方端点清单的交集；保留 OpenRouter 渠道，避免误写为直连。
其余 OpenRouter 模型不展开列举可能的上游服务商，也不宣称已核实逐请求路由。

新包为 `.build/hf-trajectories-astra-deepseek/`，复用先前 235 条结果及全部 payload。
包含 329 个 ATIF、337 份原始会话文本；该次导入器、上传器和浏览器检查默认使用
这个包；现在默认使用本文开头的十三 settings 包。`.build/hf-trajectories-current/` 保留为旧的 235 条结果基线。上传及续传命令如下：

```bash
python scripts/publish_final_results.py --base-package .build/hf-trajectories-current --package .build/hf-trajectories-astra-deepseek --upload
python scripts/append_hf_trajectories.py --base-package .build/hf-trajectories-current --package .build/hf-trajectories-astra-deepseek --upload
```

脚本校验远端后更新本地生产配置，不执行官网 Git add、commit、push。
本地审查记录在 `.build/astra-deepseek-review/`；已验证版本以 storage.json
及 `.build/hf-trajectories-astra-deepseek-uploaded.json` 为准。
费用沿用官方公开费率估算口径：Astra 为 $1,339.084603，DeepSeek 为
$11.941868994。2026-11-14 起，DeepSeek 全部请求统一使用官方谷价：
每百万未缓存输入/缓存读取/输出为 $0.15/$0.003/$0.60。此固定比较口径
不按请求时间切换峰谷价，也不代表实际 OpenRouter 账单。

## 历史更新：加入 Claude Opus 5.5，五个榜单条目共 235 条轨迹

Opus 条目覆盖 47/47 道题，平均分 **48.4108822466**。配置均为
**Claude Code 2.1.309 / max / OpenRouter**，版本与评测仓库默认配置一致。
46 个任务实际使用 `anthropic/claude-opus-5.5`；`constrained-molecular-search`
实际使用 `anthropic/claude-opus-5`，最终得分 **19.5839**。五次先前的 Opus 5.5
尝试均有 `bio` 分类拒绝记录，事件类型为 `model_refusal_no_fallback`。

[Anthropic 官方说明](https://code.claude.com/docs/en/model-config#automatic-model-fallback)
推荐对 Opus 5.5 的生物安全分类拒绝回退到 Opus 5。文档不规定先重试五次，
也没有规定 benchmark 应如何归属替代结果；这两点属于本次评测决策。
`selection.json` 保存明确的替代关系、五次拒绝的会话及原始日志哈希。
主榜单、模型页和任务详情均有注释；真实配置、轨迹和计费仍保留 Opus 5。

47 个 Opus 归档共 **15,567 个文件**，大小和 SHA-256 全部核验通过，
最终 reward、result、INDEX、FINAL_RESULT 一致。47 个任务均有累计 token
计数和原始解题时长，总 tokens 为 **912,829,589**，官方标准价估算费用
**$498.74161865**。Opus 5.5 每百万输入/缓存读取/5 分钟缓存写入/输出为
$4/$0.20/$5/$20，Opus 5 为 $5/$0.50/$6.25/$25，来源为
[官方价格表](https://platform.claude.com/docs/en/about-claude/pricing)。
费用只统计最终选中运行，不包括五次被拒绝的尝试。

Claude Code 的本地合成错误消息不计 token；恢复会话取最终累计数，不把
多个累计数相加。`layout-page-search` 一条中断响应缺少 reasoning 明细，
但最终累计数完整，使用累计数对齐总量。JSONL 中的 Unicode 行分隔符属于
字符串内容，不作为记录边界。既有 Kimi 的 7 个 token 回退任务沿用已有口径。

该次公开包为 `.build/hf-trajectories-current`，**99,100 个文件、约 3.34 GiB**，
含 235 个 ATIF 和 243 份原始会话文本。之前四个模型的 188 份结果和全部
payload 保持不变。该次已验证 HF SHA 见历史回执
`.build/hf-trajectories-current-uploaded.json`；`content/leaderboard/storage.json`
现在记录的是本文开头的十三 settings 版本。

## 历史记录：2026-11-13 统一目录并清理重复发布

HF 当前分支只保留 `releases/current/`，不在目录名中列举模型或日期。
固定 commit SHA 负责版本标识；网站依然使用固定 SHA 下载，不读取可变的 `main`。

- 将 `releases/2026-11-11-luna-terra-sol-0b5b811770/` 原样迁移为 `releases/current/`。
- 从 `main` 删除 `releases/2026-11-09-luna-terra-a9eb7c2ac3/`。其中 94 条结果的
  score、原始轨迹和 reward 哈希均与当前选择一致，32,467 个轨迹文件也逐字节重复。
- 235 条 trial、snapshot 内容以及网站 entry/trial URL 均不变。旧目录在历史
  commit 中仍然存在，既有固定 SHA 下载链接继续有效；未重写 Git 历史。

迁移复用 Git tree/blob 对象，只需上传修改后的 README 和压缩清单。
普通 fast-forward push 防止覆盖并发发布；全量远端哈希、大小、匿名下载和 CORS
校验通过后才更新本地 storage 并生成生产页面。迁移脚本不提交或推送官网仓库。

```bash
python scripts/normalize_hf_layout.py --source-package .build/hf-trajectories-luna-terra-sol-kimi-opus --package .build/hf-trajectories-current
python scripts/normalize_hf_layout.py --source-package .build/hf-trajectories-luna-terra-sol-kimi-opus --package .build/hf-trajectories-current --apply
```

第一条命令只准备和检查；第二条执行迁移，网络中断后可使用同一命令续做校验。
依赖 Git 及 `python -m pip install -r scripts/requirements-hf.txt`，使用现有 HF 登录。

## 后续追加模型

完成模型选择、元数据及导入配置更新后，以最近的已验证包为基线，指定新的本地包：

```bash
python scripts/publish_final_results.py --base-package .build/hf-trajectories-pr3 --package .build/hf-trajectories-next --upload
```

不带 `--upload` 只准备本地预览。增量上传只新增 trial，保留 `releases/current/`
及旧 trial 的字节内容。远端元数据与基线和新包均不匹配时中止。续传时使用
`append_hf_trajectories.py`，传入相同的 `--base-package`、`--package` 和 `--upload`。
发布成功后的新包作为下一次追加的基线。网站仓库的 add、commit、push 独立执行。

## 本地重建与审计

```bash
python scripts/import_final_results.py --package .build/hf-trajectories-pr3 --check
python scripts/leaderboard_costs.py --usage .build/hf-trajectories-pr3.usage.json --check
python -m unittest discover -s scripts -p 'test_*.py'
python scripts/build_tasks.py --check
python scripts/build_leaderboard.py --production --check
```

公开包、原始用量回执和网站备份位于 `.build/hf-trajectories-*`，不会进入 Git。
若源归档已经变化，应指定新的 `--package` 路径，不覆盖旧包。恢复生产配置可使用：

```bash
python scripts/upload_hf_release.py --package .build/hf-trajectories-pr3 --verify-revision <FULL_HF_SHA>
```

评分沿 `FINAL_RESULT.json` 的最终 reward 指针读取，原生 reward × 100 必须
与索引分数相符。Codex 用量来自原始 coding session 中按 response ID 去重的
`token_usage_record`，并与最终 thread 累计计数核对。ATIF 汇总落后时使用完整
请求回执，具体说明保存在 Agent tab。重评分不会重复计入解题用量；
Luna 两条、Terra 一条、Kimi 四条原先缺失的耗时，加上 DeepSeek spoken-query-search，
共八条按用户认可的两小时编码预算记为 7200 秒；各自保留赋值依据，
只补耗时，不把原始缺失时间戳伪装成已记录的起止时间。

Sol 使用 OpenAI 直连，Luna/Terra 使用 OpenRouter；provider 和 session ID
均与原生会话元数据核对。Sol 的 `large-scale-formula-retrieval` 原始会话位于
`agent/original-codex-sessions/`，其余会话位于 `agent/sessions/`，两者均按归档
文件清单验证并导出。qualification 标记和限制保留在 Verifier tab 和结果下载中。

Cost 使用 `official-pricing.json` 保存的官方标准处理 USD 价格，包含缓存读写及
逐请求长上下文档位。Sol 价格和 2026-09-29 发布日期来自
[模型文档](https://developers.openai.com/api/docs/models/gpt-6.1-sol)及
[官方更新日志](https://developers.openai.com/api/docs/changelog)，核实日期为 2026-11-11。
Kimi 使用上述官方平价 USD 费率和独立的 Claude Code 会话计数口径。
DeepSeek 使用上述官方谷价作为所有请求的固定估算费率；主榜、模型页、
任务详情和 Cost 帕累托图均注明该口径，结果下载保留完整价格表。
费用是按官方费率估算的解题开销，不是账户账单，
不包含 verifier、任务内 API 或基础设施。仅更新价格可单独重算，不必重传轨迹。

Pareto 图横轴可选 Cost、Tokens、Time，默认 Cost，没有 Release Date 选项。
三种横轴统一为从零开始的线性坐标，使用等距的整洁刻度，手机端减少刻度数量。
悬浮或键盘聚焦数据点时，提示标题显示“模型 / Harness”，并保留 reasoning effort、
得分、当前维度的数值及任务覆盖数。
三项均汇总当前 All／CPU／GPU 范围内的任务；Time 使用结果摘要中的 Agent 耗时，
包括上述八条补齐的 7200 秒，当前各模型耗时覆盖均为 47/47。将来若有未审定的
缺失时间，仍跳过并显示覆盖数。切换横轴会重算前沿，
并通过 `x=cost|tokens|time` 保存到链接，刷新和从模型详情返回时保留。

公开包包含全部 564 个 ATIF 下载及各 setting 的原始会话文本导出；预览与下载
使用相同的脱敏文本。主机路径替换为别名，凭证和环境值脱敏。
二进制索引、权重等只列名称、大小和不可预览原因，不上传其内容。

## 历史记录：2026-11-09 Luna/Terra 替换

此前的两模型版本已完成上传、旧轨迹清理和校验，HF 固定提交为
[`1f675a76e0eb10ca5dfb514287c836904c923f18`](https://huggingface.co/datasets/search-swe/trajectories/commit/1f675a76e0eb10ca5dfb514287c836904c923f18)。
当时共 94 条轨迹、32,470 个公开文件，旧 `releases/2026-10-30-3090361873/`
目录从 HF 当前树移除，历史提交保留。该过程由 `replace_hf_trajectories.py`
和 `.build/hf-replacement-luna-terra.json` 记录。之后加入 Sol 使用新增 release；Kimi 和 Opus 使用增量追加，
不执行这个历史删除计划。

## 历史记录：2026-11-04 GLM 下架

2026-11-04 从网站移除 `z-ai/glm-5.3-flash`。当时网站为 **47 道题、3 个模型、
141 份结果**；其他模型的结果、费用和 entry/trial 链接不变。原始 jobs 不修改。

当时 HF 删除及校验完成，固定版本为
[`824b6d863b69b1f86b9d73b365dca28af200de7c`](https://huggingface.co/datasets/search-swe/trajectories/commit/824b6d863b69b1f86b9d73b365dca28af200de7c)。
当时 `storage.json` 切换到该版本并移除 pending 标记，146 个 HTML 页面及结果 JSON
使用该固定版本。本节为历史记录，现行版本见本文开头。

以下命令保留用于离线审计或中断后的重试，正常情况下无需再次执行删除：

```bash
python scripts/prune_hf_models.py          # 离线核对并列出删除范围
python scripts/prune_hf_models.py --apply  # 执行 HF 删除、校验并更新本地官网
```

已使用 `.build/hf-trajectories-without-glm/` 和
`.build/hf-model-removal-2026-11-04.json` 完成 `search-swe/trajectories` 的更新，
删除了 GLM 的 **47 个 trial 目录、15,183 个文件，约 539.06 MiB**。
同一提交中更新了 `README.md`、release 的 `snapshot.json` 和 `publication.json.gz`；
其余 141 份轨迹逐字节保留，不重复上传。

脚本复用 `hf auth login` 或 `HF_TOKEN`。提交以
`4ad9ff8ac4c70eefa3d5f6781df3692d81adfc7b` 为父提交；远端发生其他变化时会拒绝
自动删除。中断后重跑 `--apply`：若同一提交已经成功，则验证结果并继续接入网站。
校验包括保留文件哈希、删除目录缺失、匿名下载和 CORS。

执行回执为 `.build/hf-model-removal-2026-11-04.applied.json` 和
`.build/hf-trajectories-without-glm-uploaded.json`。
本地备份、删除计划、公开包和回执保存在 `.build/`，不会随官网发布。
脚本不会 add、commit 或 push 网站仓库，也不会删除本机原始评测记录。

HF 删除作用于当前版本，历史提交保留旧文件，不重写仓库历史。

## 历史记录：2026-10-31 两题撤销（已执行）

2026-10-31 撤销 `deletion-resilient-vector-search` 和
`resource-bounded-multivector-search`。当时更新为 47 题（24 CPU、23 GPU）、4 个模型、
188 份结果。两题不按零分计入，榜单、tokens 和时长均按剩余结果重新汇总。

以下为当时使用的命令，不用于本次模型下架：

```bash
python scripts/prune_hf_tasks.py          # 离线核对并列出删除范围
python scripts/prune_hf_tasks.py --apply  # 执行 HF 更新、校验并更新本地官网
```

已准备好 `.build/hf-trajectories-47/` 公开包和
`.build/hf-task-removal-2026-10-31.json` 精确操作清单，不需要重新导出。
脚本复用已有 HF 登录，或读取 `HF_TOKEN`。缺少依赖时运行
`python -m pip install -r scripts/requirements-hf.txt`；尚未登录时运行 `hf auth login`。

本次从 `releases/2026-10-30-3090361873/trials/` 删除上述两题对应的 8 个目录，
共 1,069 个文件、约 45.97 MiB。仅上传 README、该 release 的 `snapshot.json`
和 `publication.json.gz` 三个文件，其余 188 份轨迹逐字节保留，不重复上传。
删除与摘要更新放在同一次 HF commit 中，并限制父提交为原先验证过的
`966567209b031769d3fa024c42e43ac461739231`，避免覆盖并发修改。

中断后重跑相同命令即可：如果提交已成功，脚本核对新摘要及删除结果后继续
远端哈希、匿名下载和 CORS 校验，不重复删除。只有校验成功才改写
`content/leaderboard/storage.json` 并生成 194 个官网页面。
执行回执保存在 `.build/hf-task-removal-2026-10-31.applied.json` 和
`.build/hf-trajectories-47-uploaded.json`。不会执行网站仓库的 add、commit 或 push。

脚本执行前，本地页面使用已过滤的公开包预览，`--production` 检查会拒绝这个
尚未发布的配置。执行成功后改为固定的新 HF SHA，届时运行：

```bash
python scripts/build_leaderboard.py --production --check
```

删除针对 HF 当前版本；HF 的历史提交仍会保留旧文件。本脚本不重写仓库历史。
旧官网在本地变更发布之前仍会引用原来的固定 SHA。

## 旧版追加发布流程（不会清除旧轨迹）

以下用于后续新增评测的完整发布。先按下一节准备与本地结果匹配的新包，再运行：

```bash
python -m pip install -r scripts/requirements-hf.txt
hf auth login
python scripts/upload_hf_release.py --package .build/hf-trajectories-next
python scripts/upload_hf_release.py --package .build/hf-trajectories-next --upload
```

已经登录过 HF 时可省略 `hf auth login`。也支持通过环境变量 `HF_TOKEN` 提供
对目标 dataset 的写权限；不要把 token 写进脚本或网页。

不加 `--upload` 时只做离线检查，既不上传也不访问 HF。用 `--package` 指定
本次准备的包，避免误用早期的 `.build/hf-trajectories/`。文件较多，上传使用可恢复的 `upload_large_folder`；
中断后对同一份未修改的发布包重跑相同命令即可。默认 4 个 worker，可用
`--workers 2` 调低并发。脚本保留既有 release，不删除远端文件。

上传成功后脚本会自动：

1. 最后提交发布清单，取得实际上传 commit 的完整 SHA。
2. 按这个 SHA 校验所有远端文件的大小及 Git/LFS 内容哈希。
3. 匿名读取真实 JSON、较大 JSON 和 gzip，检查下载哈希及官网 Origin 的 CORS。
4. 写入 `content/leaderboard/storage.json`，将所有数据 URL 固定到该 commit。
5. 生成对应的官网页面，保存上传包旁的 `*-uploaded.json` 回执。

这一步只更新本地网站文件，不会 git commit、push 或部署官网。之后检查：

```bash
python scripts/build_leaderboard.py --production --check
```

上传完成但网络校验中断时，也可用上传日志中的实际 SHA 继续校验并接入官网，
无需再次上传：

```bash
python scripts/upload_hf_release.py --package .build/hf-trajectories-next --verify-revision FULL_40_CHARACTER_COMMIT_SHA
```

## 旧归档格式的重建流程（历史参考）

以下仅适用于旧版带 `traj-analysis/leaderboard-data` 的归档。当前归档使用上文的新导入器。历史命令：

```bash
python scripts/import_results.py --jobs /path/to/Search-SWE/jobs
python scripts/leaderboard_costs.py --usage /path/to/Search-SWE/jobs/traj-analysis/leaderboard-data/usage.json
python scripts/prepare_hf_release.py \
  --jobs /path/to/Search-SWE/jobs \
  --output .build/hf-trajectories-next
python scripts/prepare_hf_release.py --check --output .build/hf-trajectories-next
python scripts/upload_hf_release.py --package .build/hf-trajectories-next --upload
```

导出只使用 `final-trajectories/INDEX.csv` 的最终选择，并应用网站的 `selection.json`
模型排除规则，核对分析、轨迹和最终 reward 的源哈希。不会写入原始 jobs、重新解题或重新评分。

发布包结构：

```text
README.md
publication.json.gz                 # 完整文件清单、字节数、SHA-256、Git blob hash
releases/current/
  snapshot.json                     # 当前选中 trial 的评分、用量、模型及来源摘要
  trials/<trial-id>/
    manifest.json                   # 轨迹步骤索引
    steps-*.json                    # 阅读分片
    calls-*.json / text-*.json       # 超长内容和并行调用分片（按需存在）
    search.json
    trajectory.json.gz              # 公开 ATIF 下载
    evaluation.json
    files/index.json                # 各 tab 的目录树
    files/*.json / *.txt.gz         # 文件预览分片及对应完整文本下载
```

压缩清单和轨迹下载使用仓库已有的 `*.gz` LFS 规则。普通阅读分片仍是可直接
`response.json()` 的 JSON。源评测变化会生成新的 snapshot/entry URL；仅调整网站模型
选择时，snapshot URL 更新，保留模型的 entry/trial URL 不变。下架任务或模型时，
同步清理旧生成页面和包含已下架结果的公开 snapshot。

## 路径与公开数据边界

宿主机的绝对路径在分片之前转换成 `${BENCHMARK_ROOT}`、`${EVAL_ROOT}`、
`${WORKSPACE_ROOT}`、`${USER_HOME}` 等通用别名。别名表示来源环境，不是文件下载链接。
`/app`、`/tests`、`/logs`、`/tmp` 和任务数据路径保留，以便理解原始执行命令。
预览、搜索内容、原生会话日志、配置、异常和 gzip 下载使用同一套转换规则。

凭据模式、结构化凭据及环境变量值会被脱敏。只导出最终选择的轨迹和原有
允许预览的文本证据；隐藏文件、符号链接、完整 jobs、模型权重、索引及大型
二进制文件不上传。文件树中仍可列出不可预览产物的名称与大小。

源 SHA-256 仍对应未经修改的原始记录；公开文件哈希对应清理后的内容。
保持 HF 仓库现有的 `cc-by-nc-sa-4.0` 声明，第三方文件保留自身许可说明。

## 预览、验证和正式构建

上传前 `storage.json` 使用 `preview`，本地 7788 从准备好的公开发布包读取，
方便检查路径和排版。`--production` 会拒绝 `local`、`preview`、`main`、短 SHA
以及与本地结果摘要不匹配的配置，避免生成尚不存在或版本不固定的官网链接。
上传并验证成功后脚本自动切换到 `huggingface`。

```bash
PYTHONPATH=scripts python -m unittest \
  scripts/test_publication.py scripts/test_leaderboard.py scripts/test_trial_files.py
HF_PACKAGE=.build/hf-trajectories-pr3 NODE_PATH=/path/to/playwright/node_modules node scripts/test_hf_browser.cjs
```

浏览器检查使用另一个真实 HTTP origin 提供公开发布包，验证匿名跨域加载、
下载一致性、整个轨迹连续阅读、目录树、搜索、失败重试及手机布局。它会暂时
重建本地页面并在结束后恢复默认配置。真实 HF 文件的远端哈希和 CORS 检查由
上传脚本在上传完成后执行；上传前无法验证尚不存在的远端文件。

上传机制参考 [HF 大目录上传文档](https://huggingface.co/docs/huggingface_hub/guides/upload)。
