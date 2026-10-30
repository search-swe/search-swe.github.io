# Leaderboard：从本地预览发布到 Hugging Face

官网保持静态 HTML/CSS/JS。榜单及任务分数随网站发布，轨迹、日志和文件预览
从公开的 HF Dataset [`search-swe/trajectories`](https://huggingface.co/datasets/search-swe/trajectories)
匿名按需读取。浏览器不需要 HF Token。

## 当前准备好的上传命令

在网站仓库根目录运行：

```bash
python -m pip install -r scripts/requirements-hf.txt
hf auth login
python scripts/upload_hf_release.py
python scripts/upload_hf_release.py --upload
```

已经登录过 HF 时可省略 `hf auth login`。也支持通过环境变量 `HF_TOKEN` 提供
对目标 dataset 的写权限；不要把 token 写进脚本或网页。

不加 `--upload` 时只做离线检查，既不上传也不访问 HF。默认读取已经生成的
`.build/hf-trajectories/`。文件较多，上传使用可恢复的 `upload_large_folder`；
中断后对同一份未修改的发布包重跑相同命令即可。默认 4 个 worker，可用
`--workers 2` 调低并发。脚本保留既有 release，不删除远端文件。

上传成功后脚本会自动：

1. 最后提交发布清单，取得实际上传 commit 的完整 SHA。
2. 按这个 SHA 校验所有远端文件的大小及 Git/LFS 内容哈希。
3. 匿名读取真实 JSON、较大 JSON 和 gzip，检查下载哈希及官网 Origin 的 CORS。
4. 写入 `content/leaderboard/storage.json`，将所有数据 URL 固定到该 commit。
5. 生成 202 个官网页面，保存 `.build/hf-trajectories-uploaded.json` 回执。

这一步只更新本地网站文件，不会 git commit、push 或部署官网。之后检查：

```bash
python scripts/build_leaderboard.py --production --check
```

上传完成但网络校验中断时，也可用上传日志中的实际 SHA 继续校验并接入官网，
无需再次上传：

```bash
python scripts/upload_hf_release.py --verify-revision FULL_40_CHARACTER_COMMIT_SHA
```

## 重建公开发布包

这次已准备好，无需在上传前重跑。以后评测数据更新时，指定一个新的空目录：

```bash
python scripts/prepare_hf_release.py \
  --jobs /path/to/Search-SWE/jobs \
  --output .build/hf-trajectories-next
python scripts/prepare_hf_release.py --check --output .build/hf-trajectories-next
python scripts/upload_hf_release.py --package .build/hf-trajectories-next --upload
```

导出只使用 `final-trajectories/INDEX.csv` 的最终选择，并核对分析、轨迹和最终
reward 的源哈希。不会写入原始 jobs、重新解题或重新评分。

发布包结构：

```text
README.md
publication.json.gz                 # 完整文件清单、字节数、SHA-256、Git blob hash
releases/<date-selection-hash>/
  snapshot.json                     # 196 个 trial 的评分、用量、模型及来源摘要
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
`response.json()` 的 JSON。现有页面 URL 中的 release ID 保持不变，保留已分享链接。

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
NODE_PATH=/path/to/playwright/node_modules node scripts/test_hf_browser.cjs
```

浏览器检查使用另一个真实 HTTP origin 提供公开发布包，验证匿名跨域加载、
下载一致性、整个轨迹连续阅读、目录树、搜索、失败重试及手机布局。它会暂时
重建本地页面并在结束后恢复默认配置。真实 HF 文件的远端哈希和 CORS 检查由
上传脚本在上传完成后执行；上传前无法验证尚不存在的远端文件。

上传机制参考 [HF 大目录上传文档](https://huggingface.co/docs/huggingface_hub/guides/upload)。
