# OpenFeed Studio v0.3 — 工程验收与下一步发行门禁

日期：2026-10-21。状态：**可运行工程原型；未达到互联网生产部署门槛**。

## 已实现并已验证

| 模块 | 当前实现 | 验证方式 |
|---|---|---|
| 普通 HTML → RSS | CSS、XPath、Feed43 子集；按稳定链接 GUID 去重 | 自动化提取与接口测试 |
| 非典型重复卡片 | 静态 DOM 的重复兄弟容器评分，输出有匹配数量、样本标题的候选规则；如 `div.insight-card` | 本地复杂静态 HTML 回归 |
| 可视化选择 | 安全 HTML 快照点击卡片、标题、链接、日期；生成相对 CSS；显示跨卡片的匹配覆盖率 | 真正 Chromium DOM 和点击交互测试 |
| 全流程 UI | 创建源 → 侦察和结果预览 → 网页点选 → 保存 → FastAPI/SQLite → 公共 RSS | Chromium 中执行真实产品 JS，以本地 ASGI 桥接真实后台；**源网页数据使用测试样本** |
| 原生 Feed 发现 | RSS/Atom/JSON Feed `rel=alternate`；可在 UI 一键使用原生 RSS URL | 解析器及界面逻辑，外部站点未验收 |
| JSON Feed | 1.0/1.1、RSS2/Atom | XML/JSON 回归 |
| 规则迁移 | OPML、Bundle v1/v2；Bundle v2 保留 Feed ID 与启停状态 | FastAPI/SQLite 回归 |
| 原子批量导入 | 整批事务，一条规则写入失败不留下之前的部分记录 | 故意制造数据库写入错误的回滚测试 |
| 完整备份 | `/api/export/database`：SQLite 在线一致性快照，包含内容历史、日志和永久 Feed ID | SQLite integrity_check、鉴权与接口回归 |
| 浏览器获取能力 | 可选 Playwright；针对目标 URL 和页面网络请求进行策略检查；默认关闭 | 禁用门禁测试和 Chromium 对离线动态 DOM 的脚本执行测试；**没有通过真实目标网站的浏览器联网抓取** |
| SSRF 防护 | HTTP 公共地址解析与连接验证、跳转验证、响应上限；浏览器路径仍需独立出站防火墙 | URL、DNS、坏目标单测；未完成专业渗透测试 |

当前 `python -m pytest -q` 结果：**40 passed**（在本次执行环境，Chromium 可用）；`node --check`、Python 编译均通过。没有 Docker 命令，故尚未验证 Docker 构建。Readwise Reader 实际云端添加 RSS 也尚未验证。

## 为什么没有把所有工具都直接融合

现有 Python FastAPI + SQLite 是真正可用的端到端竖切片。原版 PolitePol 旧开源仓库、html2rss、RSSHub、RSS-Bridge、OpenPicker 等适合继续按「单项能力胜过自建、许可证可行、可独立部署」三个门槛验证，而不是贸然引入多种语言和运行时。真正可维护的核心资产是跨引擎 Recipe、来源历史、稳定 GUID 和公共 Feed 地址。

当前可视化模块是项目自有 `static/picker.js`（无额外框架依赖）。下一步才对 OpenPicker 做独立的跨网站扩展实测。RSSHub 与 RSS-Bridge 的现成规则不应直接复制进产品仓库，优先通过标准公开 Feed 接口集成。

## 系统边界与技术风险

1. **动态浏览器抓取是实验性路径。** `OPENFEED_EXPERIMENTAL_BROWSER=0` 为默认。将其打开前，需要单独部署非 root Chromium worker，在宿主层禁止访问 RFC1918、loopback、link-local、云元数据地址，限制 DNS、WebSocket 和出站连接。应用级 `route`/DNS 检查只是纵深防御，不能替代网络级阻断。默认 Docker 镜像不带浏览器依赖，不能直接打开开关就宣称支持。
2. **网页规模上限：** 单次正文为 2.5 MB；抽取上限 100 条；候选容器上限 500 个匹配。多页列表、AJAX 搜索、分页、增量游标尚未实现，可能漏抓高频网站。前端应显示限额和告警（后续改进）。
3. **内容访问边界：** 不尝试绕过验证码、站点准入条款或付费墙；针对猎聘优先使用允许的官方职位提醒或数据来源。职位新增、变更、下线尚无完整状态模型。
4. **数据模型：** v0.3 是单管理员 / 单进程 / SQLite 系统。扩大至多 worker 时，必须把来源调度租约和域名限速从内存迁移到数据库或队列，不允许直接增加多个 Uvicorn worker。
5. **订阅链接：** `/rss/<id>.xml` 向所有知道 URL 的人公开。不要存储非公开付费文章全文、敏感 Cookie 等内容。数据库备份包含文章来源与历史，下载和存储要保护。
6. **页面兼容：** 静态快照不是 PolitePol 全功能在线可视化浏览器；iframe 同源规则不可绕过。跨网站真实实时点选和网站动态登录功能未交付。

## 建议正式产品的附加机制

- Recipe 测试系统：保存 HTML 样本，回归条目数与字段准确率，检测网页改版导致的字段错位；在候选变更后需明确人工审核。
- 文章生命周期：`first_seen_at`、`published_at`、`updated_at` 分离；职位以职位平台给出的稳定 job ID 为主键，消失需连续确认。
- 调度治理：来源级时间预算、域名 Token Bucket、Circuit Breaker、指数退避、连续失败阈值告警；跨实例改用持久化租约。
- 数据质量：自动去除跟踪 URL 参数的可配置白名单、跨栏目去重、文章发布时间置信度、相对日期时区、PDF 明确识别。
- 站点适配：原生 RSS 优先，再 JSON、CSS/XPath，最后独立浏览器 Worker；外部 RSSHub/RSS-Bridge 使用标准 Feed URL。
- 运维：审计日志、备份恢复演练、受控数据库迁移、夜间低频抓取、连接指标和磁盘阈值。
- 产品体验：动态浏览器取样与调试面板、错误原因和诊断建议、键盘可访问编辑器、多语言、一键批量迁移和版本化规则回滚。

## 下一批必须通过的 Gate

**Gate 1：真实来源连通性。** 使用用户给出的 Oaktree、BofA Institute、World Gold Council 等站点，实际记录 HTTP 状态、HTML 或 JSON 结构、选择器、文章数、发布日期与二次抓取去重结果。不应仅根据网络检索材料声称已经跑通。

**Gate 2：动态网页隔离。** 在可独立限制出站网络的非 root 容器中部署 Playwright；用模拟私有地址和 DNS 改变测试网络边界，再测试 KKR 等真实网站。

**Gate 3：真实 Reader 订阅。** 在合法 HTTPS 域名上部署，并实际让 Reader 抓取 RSS、验证更新、GUID 稳定与文章去重。

**Gate 4：生产可靠性。** Docker 构建、镜像扫描、48–72 小时运行、SQLite 在线备份恢复演练、并发请求与内存基准、可访问性与移动端测试。

**Gate 5：完全迁移。** 用户全量 URL 先去重、分类、制定 Recipe，逐条给出成功/受限/需动态/不可采集四种状态。不得用已配置 URL 数量冒充有效 Feed 数量。
