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

`.github/workflows/daily.yml` 每天 06:17（北京时间）在 GitHub Actions 上跑一次，把日报和数据库提交回仓库。GitHub 的 runner 在海外，所以 Google News、Reddit 这类从国内不稳定的源不受影响。手动触发在 Actions 页面点 `Run workflow`。

## Claude 简报

`newscollector brief` 把当天的条目（每类最多 100 条，标题加摘要前 120 字）交给 Claude，写一份中文简报：今日要点、分类要点、值得深挖，每条带编号链接回原文。输出在 `briefs/YYYY-MM-DD.md`，邮件里排在日报前面。

需要一个 secret：`ANTHROPIC_API_KEY`，在 https://console.anthropic.com 创建，和 Claude.ai 订阅是两回事。没有这个 secret 时简报步骤自动跳过。

默认模型 `claude-opus-5-5`，请求开启了服务端 fallback，模型因安全策略拒答时会自动换一个模型重试。每天的输入约三四万 token，按目前价格大约 0.2 美元一天。想便宜一半，加 secret `BRIEF_MODEL=claude-sonnet-5-5`。

本地跑一次：

```bash
ANTHROPIC_API_KEY=... newscollector brief --date 2026-11-05
```

## 邮件推送

工作流跑完后可以把日报通过 SMTP 发到邮箱，Gmail、163、QQ 邮箱都行，不需要第三方服务。

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
