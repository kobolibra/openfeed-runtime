# 真实网页到 RSS 的本次结果

## 已实际生成的 RSS

| 信息源 | 项目数 | 完整发布日期 | 规则范围 |
|---|---:|---:|---|
| Oaktree Memos | 36 | 36 | `/insights/memo/` 正文链接；XPath 读取原页带 `>` 前缀的 datetime；未覆盖全部旧 PDF/脚本链接 |
| BofA Institute Transformation | 24 | 0 | `.aem-wrap--tile` 内的标题、文章链接与摘要；月份没有补成具体日期 |
| Gold.org Industry Insights | 20 | 0 | `article.m-blog-card` 的正文链接；明确排除作者页链接；相对日期未转成猜测日期 |
| KKR Latest Insights | 4 | 0 | 静态 `.teaser` 正文卡片，已去重；不是动态全列表/全站归档 |
| Morgan Stanley Insights Articles | 4 | 0 | 首屏 hero 和文章正文卡片；排除主题分类、视频入口和导航 |
| 猎聘华泰柏瑞基金公开职位 | 23 | 0 | `.job-detail-box` 中职位名称、地点、链接及薪资摘要，原页没有完整日期 |
| **合计** | **111** | **36** | **6 份有效 RSS 2.0** |

文件在交付包 `feeds/`。每个 XML 均经过独立 `feedparser` 校验，标题与链接和实际提取结果相符；去重 GUID 数量与条目数一致。SQLite 中重复提取新增数为 0，注入抓取失败后原 RSS 保留。另通过真实 Uvicorn HTTP 服务读取全部 6 份 Feed 并核对 111 条内容、唯一 GUID 与 ETag 304，见 `evidence/real-rss-http/`。

猎聘一个实习职位链接携带随搜索变化的 `d_ckId/d_headId/d_posi` 等追踪参数，会使同一职位产生多个 RSS GUID。本次只在猎聘的明确职位详情路径移除已知追踪参数，保留其他内容参数和其他站点 URL。修复前复现与回归分别见 `rss-identity-before.log` 和最终测试报告。

## 证据链与边界

1. `evidence/public-captures/` 保存真实网页和 robots、抓取状态及页面 SHA-256；网络请求仅限指定公开域名白名单，遵守 robots，遇到禁止和门槛停止。
2. `source/tools/build_captured_rss.py` 定义逐站核对的明确规则，以原工程 `extract_articles`、`validate_items`、`Store` 和 `render_rss` 生成 RSS。
3. `feeds/reviewed-recipes.json` 可导入规则，`feeds/captured-feeds-backup.sqlite3` 可恢复规则及文章历史。均保持暂停，防止在尚未修复的部署网络上误报自动更新可用。
4. `feeds/results.json` 给出每站数量、日期覆盖、页面哈希、样本、规则及校验状态。
5. `evidence/real-rss-http/results.json` 证明实际 HTTP RSS 接口能输出本轮真实内容；不代表从该 API 完成实时联网抓取或 Reader 云端成功拉取。

本机默认保护抓取器被假 IP DNS 条件阻断，依然拒绝 198.18.*。系统只读网络可以按域名取到页面，本次以此采集真实内容核验提取和 RSS，未修改系统 DNS、没有放宽应用 SSRF。这个差异已单独记录，不能描述为默认自动更新通过。

## 其他三源

- Capital Group：取到页面，但有机构投资者资格与条款门槛，未代用户作声明或越过门槛生成 Feed。
- CEPR：robots 可检查，内容请求返回 HTTP 403。
- Citi Careers：robots 检查禁止所请求路径，停止内容抓取。

猎聘在不同读取方式下分别出现过验证码与可公开访问的职位 HTML，本次 23 条来自后者的实际原文；遇到验证码时应停止，不使用绕过手段。

## 使用方法

只查看本次内容可直接打开 6 份 XML。要通过本地 RSS 接口访问，按部署指南将提供的 SQLite 备份复制到一个新的数据库路径，设置 token 和 `OPENFEED_DB`，启动单进程服务。每个固定 Feed ID 可在 `reviewed-recipes.json` 中查到，RSS 路径为 `/rss/<id>.xml`。

持续更新需要真实公网 DNS/抓取网络，并重新测试规则、分页与日期覆盖。Readwise Reader 需要能从公网访问的固定 HTTPS origin；本轮没有提供或假装完成公网订阅。
