# Leaderboard：从本地预览发布到 Hugging Face

官网保持静态 HTML/CSS/JS。榜单及任务分数随网站发布，轨迹、日志和文件预览
从公开的 HF Dataset [`search-swe/trajectories`](https://huggingface.co/datasets/search-swe/trajectories)
匿名按需读取。浏览器不需要 HF Token。

## 当前更新：加入 Kimi K3.1 Pro，四个模型共 188 条轨迹

2026-11-12 版本增加 `kimi-k3.1-pro`，47/47 道题（24 CPU、23 GPU），
平均分 26.5999307981。Provider 全部为 **Moonshot AI**，由评测操作者确认；
使用 **Claude Code 2.1.309 / max**，版本与主仓库默认配置一致。
原有 Sol、Terra、Luna 的结果和轨迹文件保持不变。

数据源仍为
`/data/Search-SWE-Workspace/Search-SWE/run-eval-release/Search-SWE/jobs/final-trajectories`。
新包为 `.build/hf-trajectories-luna-terra-sol-kimi`，共 83,214 个公开文件
（约 2.91 GiB），包含 188 条 ATIF 和
196 个原始会话文本（141 个 Codex、55 个 Claude Code 主/子会话）。

本次上传及全量校验已完成，固定 HF 版本为
[`baa8b4fa26a87b781b0f8594305933bd61d973a1`](https://huggingface.co/datasets/search-swe/trajectories/commit/baa8b4fa26a87b781b0f8594305933bd61d973a1)。
83,214 个文件通过远端大小、哈希以及匿名 JSON/gzip 下载和 CORS 校验；
生产页面固定到该版本，网站由 `main` 分支的 GitHub Pages 发布。

```bash
python scripts/publish_final_results.py \
  --base-package .build/hf-trajectories-luna-terra-sol --upload
```

不带 `--upload` 只生成和检查本地预览。增量脚本逐文件确认旧 payload 不变，
通过当前 Hub SDK 的 `upload_folder` / Xet 自动分批续传接口，仅上传 Kimi
的 47 个新 trial 目录，验证全部远端 payload 后一次提交 snapshot、
README 和 publication 清单。最终全量哈希、大小、匿名下载与 CORS 校验通过后，
写入固定 SHA 并生成 194 个 HTML 页面和结果 JSON。物理 release 目录沿用原目录，
新 snapshot ID 独立更新；旧 SHA 链接继续有效。脚本不执行 Git add、commit、push。

上传中断后从固定包续传：

```bash
python scripts/append_hf_trajectories.py \
  --base-package .build/hf-trajectories-luna-terra-sol \
  --package .build/hf-trajectories-luna-terra-sol-kimi --upload
```

校验完成的 SHA 见 `content/leaderboard/storage.json`，本地回执为
`.build/hf-trajectories-luna-terra-sol-kimi-uploaded.json`。若远端元数据与基线或
新包均不匹配，脚本中止以免覆盖其他发布；所有旧文件保留。
已提交而未完成本地激活的发布也可通过同一命令恢复。

Kimi 的 40 个任务使用已保存的累计用量计数；另外 7 个采用回退策略，
将归档响应去重后的合计作为最终展示的 token 数和费用估算依据，未记录的
用量不作估算。网页和 `/leaderboard/results.json` 采用这一口径，已验证的
HF 原始快照及其中的历史说明保持不变。费用按官方标准美元价估算，
不使用 Claude Code 对未知模型猜测的 costUSD；缓存与 reasoning 不重复收费。

仓库查询使用现有 HF 登录，公开下载不携带凭证。429 遵守服务端等待头，
分页只重试当前页。只读元数据及匿名下载遇到临时连接错误或 HTTP 500/502/503/504
时最多短暂重试三次；不自动重放结果不确定的写请求。
依赖：`python -m pip install -r scripts/requirements-hf.txt`。

## 本地重建与审计

```bash
python scripts/publish_final_results.py --base-package .build/hf-trajectories-luna-terra-sol
python scripts/import_final_results.py --check
python scripts/leaderboard_costs.py --usage .build/hf-trajectories-luna-terra-sol-kimi.usage.json --check
python -m unittest discover -s scripts -p 'test_*.py'
python scripts/build_tasks.py --check
```

公开包、原始用量回执和网站备份位于 `.build/hf-trajectories-luna-terra-sol*`，
不会进入 Git。若源归档已经变化，应指定新的 `--package` 路径，不覆盖旧包。
本地预览重建会切换 storage 配置；已上传版本可用完整 HF SHA 重新验证并激活：

```bash
python scripts/upload_hf_release.py --package .build/hf-trajectories-luna-terra-sol-kimi --verify-revision <FULL_HF_SHA>
python scripts/build_leaderboard.py --production --check
```

评分沿 `FINAL_RESULT.json` 的最终 reward 指针读取，原生 reward × 100 必须
与索引分数相符。Codex 用量来自原始 coding session 中按 response ID 去重的
`token_usage_record`，并与最终 thread 累计计数核对。ATIF 汇总落后时使用完整
请求回执，具体说明保存在 Agent tab。重评分不会重复计入解题用量；
缺少原始结束时间的三条既有轨迹仍显示缺失时长。

Sol 使用 OpenAI 直连，Luna/Terra 使用 OpenRouter；provider 和 session ID
均与原生会话元数据核对。Sol 的 `large-scale-formula-retrieval` 原始会话位于
`agent/original-codex-sessions/`，其余会话位于 `agent/sessions/`，两者均按归档
文件清单验证并导出。qualification 标记和限制保留在 Verifier tab 和结果下载中。

Cost 使用 `official-pricing.json` 保存的官方标准处理 USD 价格，包含缓存读写及
逐请求长上下文档位。Sol 价格和 2026-09-29 发布日期来自
[模型文档](https://developers.openai.com/api/docs/models/gpt-6.1-sol)及
[官方更新日志](https://developers.openai.com/api/docs/changelog)，核实日期为 2026-11-11。
Kimi 使用上述官方平价 USD 费率和独立的 Claude Code 会话计数口径。
费用是按官方费率估算的解题开销，不是账户账单，
不包含 verifier、任务内 API 或基础设施。仅更新价格可单独重算，不必重传轨迹。

Pareto 图横轴可选 Cost、Tokens、Time，默认 Cost，没有 Release Date 选项。
三项均汇总当前 All／CPU／GPU 范围内的任务；Time 使用已记录的 Agent 耗时，
缺失时间不作补算，图例和提示显示时间记录覆盖数。切换横轴会重算前沿，
并通过 `x=cost|tokens|time` 保存到链接，刷新和从模型详情返回时保留。

公开包包含全部 188 个 ATIF 下载及 196 份原始会话文本导出；预览与下载
使用相同的脱敏文本。主机路径替换为别名，凭证和环境值脱敏。
二进制索引、权重等只列名称、大小和不可预览原因，不上传其内容。

## 历史记录：2026-11-09 Luna/Terra 替换

此前的两模型版本已完成上传、旧轨迹清理和校验，HF 固定提交为
[`1f675a76e0eb10ca5dfb514287c836904c923f18`](https://huggingface.co/datasets/search-swe/trajectories/commit/1f675a76e0eb10ca5dfb514287c836904c923f18)。
当时共 94 条轨迹、32,470 个公开文件，旧 `releases/2026-10-30-3090361873/`
目录从 HF 当前树移除，历史提交保留。该过程由 `replace_hf_trajectories.py`
和 `.build/hf-replacement-luna-terra.json` 记录。之后加入 Sol 使用新增 release；本次 Kimi 使用增量追加，
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
releases/<date-selection-hash>/
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
HF_PACKAGE=.build/hf-trajectories-luna-terra-sol-kimi NODE_PATH=/path/to/playwright/node_modules node scripts/test_hf_browser.cjs
```

浏览器检查使用另一个真实 HTTP origin 提供公开发布包，验证匿名跨域加载、
下载一致性、整个轨迹连续阅读、目录树、搜索、失败重试及手机布局。它会暂时
重建本地页面并在结束后恢复默认配置。真实 HF 文件的远端哈希和 CORS 检查由
上传脚本在上传完成后执行；上传前无法验证尚不存在的远端文件。

上传机制参考 [HF 大目录上传文档](https://huggingface.co/docs/huggingface_hub/guides/upload)。
