# 每日简报任务

这是"每日新闻简报员"常驻会话每天早上 06:45（北京时间）执行的步骤。定时任务只负责唤醒会话并让它读这个文件；要调整任务，改这个文件即可。

读者：生物统计与数据科学训练，现在做 AI 工程与数据系统；关注自适应与动态统计建模、多智能体系统与 AI 队友、游戏 AI、量化与波动率、结构与制度变迁、美国与中国的政经走向。

所有日期都用北京时间。之前几天的对话与今天无关，不要沿用旧日期或旧编号。

## 步骤

1. **准备仓库**：进入 `/home/user/daily-news-collector`（不存在就 `git clone https://github.com/HengchaoZhu/daily-news-collector /home/user/daily-news-collector`），运行 `git pull --ff-only origin main` 和 `pip install -e .`。

2. **抓取**：`DAY=$(TZ=Asia/Shanghai date +%F)`，然后 `newscollector run`。它抓取全部信源、去重入库、生成 `digests/$DAY.md`。日志里有 `FAIL` 的源不影响继续。

3. **写简报**：`newscollector brief-input --date $DAY > /tmp/items.txt`，读 `/tmp/items.txt`。清单按类别编号，每条是 `[n] (来源) 标题 — 摘要`，每类最多 100 条。写 `briefs/$DAY.md`：
   - 第一行 `# 简报 $DAY`。
   - `## 今日要点`：5 到 8 条，跨所有类别挑最重要的，每条一两句话说清发生了什么、为什么重要。
   - 每个类别一节 `## 类别名`：3 到 6 条，优先有实质进展的事件而不是评论；同一事件多条来源只写一次；学术类优先选方法上有新意的论文。
   - `## 值得深挖`：2 到 3 条和读者方向直接相关的条目，说明为什么值得花时间。
   - 每条都引用条目编号，形如 `[12]`，可以连写 `[3][7]`，只引用今天清单里有的编号。
   - 内容只依据条目的标题和摘要；可以用 WebSearch 为最多 3 条要点补充背景，补充的事实在句末附来源链接。
   - 语言简洁，不用套话和表情符号，总长 800 到 1500 字。

4. **链接**：`newscollector brief-link --date $DAY`，把 `[n]` 换成 `[来源名](链接)`。

5. **翻译日报标题**：`newscollector titles-input --date $DAY > /tmp/titles.txt`，每行是 `编码<TAB>来源<TAB>标题`，每类最多 40 条。写 `briefs/titles/$DAY.json`，内容是 `{"编码": "中文标题"}`，每一行都要有。译文简洁、像中文新闻标题；人名、公司名、产品名、论文方法名保留原文；已经是中文的原样保留。写完核对条数：

   ```bash
   python3 -c "import json,sys; d=json.load(open('briefs/titles/$DAY.json')); n=sum(1 for _ in open('/tmp/titles.txt')); print(len(d), n); sys.exit(len(d)!=n)"
   ```

6. **提交**：`git add data/news.db digests/ briefs/$DAY.md briefs/titles/$DAY.json`，`git commit -m "brief $DAY"`，`git push origin main`。不要提交 `briefs/.index`。推送会触发邮件工作流：正文是简报加每类前 15 条日报，附件是完整日报 PDF。

7. **报告**：一两句话，写清抓取的源数和失败数、输入条目数、要点数、翻译条数、推送是否成功。失败时写原因；整个任务重试不超过两次。不要做任务之外的改动。

## 例外

- `briefs/$DAY.md` 已经存在：说明今天已经发过，停下并报告，不要覆盖（覆盖会再发一封邮件）。
- 推送被拒（远端有新提交）：`git pull --rebase origin main` 后再推一次。
