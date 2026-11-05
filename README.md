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

## 自动化

`.github/workflows/daily.yml` 每天 06:17（北京时间）在 GitHub Actions 上跑一次，把日报和数据库提交回仓库。GitHub 的 runner 在海外，所以 Google News、Reddit 这类从国内不稳定的源不受影响。手动触发在 Actions 页面点 `Run workflow`。简报和邮件见下面"每天的流程"。

## 每天的流程

1. **06:17 北京时间**，GitHub Actions（`daily.yml`）抓取全部信源，提交 `digests/YYYY-MM-DD.md` 和数据库。
2. **06:45**，一个 Claude Code 定时任务开一个新会话：拉仓库，用 `newscollector brief-input` 读当天条目，写 `briefs/YYYY-MM-DD.md`，用 `newscollector brief-link` 把编号变成链接，提交并推送。不用 API key，用的是 Claude 订阅。
3. 简报推上来触发 `email.yml`，把简报加日报发到邮箱。

简报的结构：今日要点（5 到 8 条）、每个类别 3 到 6 条、值得深挖（2 到 3 条），每条引用条目编号 `[n]`，`brief-link` 之后编号就是原文链接。

给 Claude 会话用的两个命令：

```bash
newscollector brief-input --date 2026-11-05   # 打印编号清单（每类最多 100 条，不含 URL），保存编号到 URL 的索引
newscollector brief-link --date 2026-11-05    # 把 briefs/2026-11-05.md 里的 [n] 替换成链接
```

某天 Claude 任务没跑成功，就不会有邮件；在 Actions 页面手动跑 `email` 工作流可以只发日报。

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
