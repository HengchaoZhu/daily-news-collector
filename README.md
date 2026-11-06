# daily-news-collector

每天抓一批 RSS/Atom 源和 Google News 搜索，去重后存进 SQLite，输出一份按类别分组的 Markdown 日报。

覆盖六类：美国经济金融政治、海外媒体对中国的政经报道、游戏产业、数据科学与 AI 学界、AI 产业、情感与娱乐。源列表在 `sources.yaml`，直接改就行。

## 跑起来

```bash
pip install -e .
newscollector run            # 抓取 + 生成今天的日报
```

```bash
newscollector collect --only games    # 只抓一个类别
newscollector digest --date 2026-11-05
```

数据库在 `data/news.db`，日报在 `digests/YYYY-MM-DD.md`。

## 它做了什么

1. `config.py` 读 `sources.yaml`，把每条 Google News 查询也变成一个 feed。
2. `fetch.py` 带超时和 User-Agent 抓取，用 feedparser 解析，清掉 HTML。
3. `store.py` 去重：URL 规范化后（去 utm 等跟踪参数、去 www、排序 query）按指纹唯一；同一标题三天内只收一次，所以同一条新闻从多个源进来只留第一条。
4. `digest.py` 把当天新收的条目按类别写成 Markdown。

一个源失败不会中断整轮，日志里会标 `FAIL`。

## 每天的流程

所有日期都按北京时间计算（`DIGEST_TZ`，默认 `Asia/Shanghai`）。

1. **06:45**，Claude Code 的定时任务唤醒常驻会话"每日新闻简报员"（Opus 5.5，以这个仓库为 source，所以有推送权限）。会话读 [`BRIEFING.md`](BRIEFING.md) 照做：抓取全部信源，写简报，把日报标题译成中文，一次提交并推送。不用 API key，用的是 Claude 订阅。
2. 推送 `briefs/*.md` 触发 `email.yml`：正文是简报加每类前 15 条日报，附件是完整日报 PDF。

任务步骤都在 `BRIEFING.md` 里，定时任务本身只说"读它并照做"，所以以后调整流程只需要改这个文件。

`daily.yml` 现在只能手动触发，作为备用抓取。原来它定在 06:17 自动跑，但 GitHub 的定时任务实际晚了约 4 小时，06:45 的简报拿不到数据，所以改由会话自己抓。

定时任务开出的全新会话拿不到仓库的推送权限（已验证），所以必须是常驻会话；在 claude.ai 的定时任务页面点"立即运行"会新开会话而不是唤醒常驻会话，测试时不要用那个按钮。

简报的结构：今日要点（5 到 8 条）、每个类别 3 到 6 条、值得深挖（2 到 3 条），每条引用条目编号 `[n]`，`brief-link` 之后变成 `[来源名](链接)`。

给 Claude 会话用的三个命令：

```bash
newscollector brief-input --date 2026-11-05   # 打印编号清单（每类最多 100 条，不含 URL），保存编号到 URL 的索引
newscollector brief-link --date 2026-11-05    # 把 briefs/2026-11-05.md 里的 [n] 替换成 [来源名](链接)
newscollector titles-input --date 2026-11-05  # 打印日报条目（每类最多 40 条）供翻译，会话写 briefs/titles/2026-11-05.json
```

邮件正文是简报加每类前 15 条日报，附件是完整日报的 PDF（每类最多 40 条，Chromium 打印），标题用 `briefs/titles/<日期>.json` 里的中文译文，没有译文的保留原文。

某天 Claude 任务没跑成功，就不会有邮件；在 Actions 页面先手动跑 `daily`，再跑 `email`，可以只发日报。

## 邮件推送

邮件通过 SMTP 发，Gmail、163、QQ 邮箱都行，不需要第三方服务。

仓库 Settings → Secrets and variables → Actions，添加：

| Secret | 值 |
| --- | --- |
| `MAIL_USER` | 发信邮箱地址 |
| `MAIL_PASSWORD` | Gmail 用应用专用密码，163 和 QQ 用授权码，不是登录密码 |
| `MAIL_TO` | 可选，收件地址，不填就发给自己 |
| `SMTP_HOST` | 可选，默认 `smtp.gmail.com`；163 填 `smtp.163.com`，QQ 填 `smtp.qq.com` |
| `SMTP_PORT` | 可选，默认 `465`（SSL） |

- Gmail：开两步验证，在 https://myaccount.google.com/apppasswords 生成应用专用密码。
- 163：网页版邮箱 → 设置 → POP3/SMTP/IMAP → 开启 SMTP 服务 → 获取授权码。

没有配置 secrets 时邮件步骤自动跳过。邮件里每个类别最多 15 条，开头有完整日报在 GitHub 上的链接。本地手动发一次：

```bash
MAIL_USER=... MAIL_PASSWORD=... SMTP_HOST=smtp.163.com newscollector email --date 2026-11-05
```

## 测试

```bash
pip install -e ".[dev]"
pytest
```

测试全部用内置的 mock RSS，不联网。

## 源的状态

`sources.yaml` 里的源在 2026-11-05 验证过能返回正常 feed；标注 unverified 的两条在构建环境里被 403，正常网络下应该可用。没有官方 RSS 的源（Reuters、Bloomberg、Anthropic、机器之心、联合早报等）用 Google News 查询覆盖，或者自建 RSSHub 后把地址加进来。

## 下一步

- 用一个便宜的模型给每条打标签和打分，日报只留高分条目。
- 把 `store.py` 的条目当作 Document，按照 evidence / claim 的结构抽取事件。
- 接 Telegram bot 推送日报。
