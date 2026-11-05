# OpenFeed Studio — 集中工程交付与审计记录

本次基于已有工程连续实现、修复、回归，**没有**完成生产发布所需的全部外部验收。以下明确区分“代码已实现”“当前环境真实验证”“待在目标环境验证”。

## 已实现与已测试

1. **招聘生命周期**：独立的 `jobs` 模型标志；只有明确标记完整库存且抓取未触及分页/数量上限时，才推进连续缺失判定；连续两次完整抓取缺失标记 `possibly_closed`，重新出现标记为 `reappeared`，不自动删除。迁移增加 `availability`、`missing_count`，保留旧 GUID/数据。
2. **持久事件日志**：新建、标题/摘要修改、缺失一次、疑似关闭、重现均写入事务性 `item_events`，并通过认证 API 和管理界面查看；每源保留最近 1000 条事件记录。失败的抓取不得改变岗位状态。
3. **Feed43/RSSWebAll 风格规则**：全局 HTML 范围 `{%}`、重复条目 `{%}`/`{*}`、捕获组字段与 `{%1}` 模板；新增大栏目匹配、异常规则超时/长度保护、预览→保存→去重→RSS 实际 FastAPI/SQLite 集成测试。不宣称完全复刻旧版 Feed43 语法。
4. **独立浏览器执行通道**：主应用不再直接启动 Chromium；新增大小/时间限制的文件 IPC、独立 Worker、内部 Docker 网络、仅公网地址的 DNS 固定出口代理、代理 CONNECT 支持和 Compose 叠加配置。新增网络结构静态验证、内网/元数据地址拒绝、代理数据通路、FastAPI→IPC→模拟 Worker→RSS 集成测试；Browser 渲染进程的实际容器安全隔离仍需 Docker 环境验收。
5. **规则健康诊断**：提供只读 `/api/feeds/{id}/diagnose`，识别当前失效选择器并返回建议容器与有效条目数；管理界面可试用建议，明确要求先测试再保存，不自动修改正式规则。
6. **运行可观测性**：认证 `/api/monitor` 报告 healthy/stale/error/never_succeeded/paused；`tools/preflight.py` 检查主要依赖、鉴权、HTTPS 配置、DNS 与浏览器开关，**不会自行宣称生产 GO**。
7. **PDF 识别补充**：除了 `.pdf` 链接，还可以识别网页明确标注 `type=application/pdf` 的下载端点；不抓取或重新分发 PDF 文件。
8. **迁移/数据安全**：新增 SQLite 数据字段均通过迁移实现，不更改既有 Feed ID；读入 Worker 响应限制大小并拒绝符号链接；保留原有规则版本回滚、数据备份、RSS GUID、失败保留和质量门禁。
9. **中英文界面基础支持**：新增工作台语言切换，翻译主要导航、编辑字段和登录区域，不影响保存的 RSS Recipe。部分动态信息仍为英文。
10. **扩展测试运行脚本**：`tools/verify_extension_install.py` 可在可正常启动 Chromium 的环境检查 MV3 service worker 和 popup；已纳入 CI 安装验收作业，但此环境无法启动完整 Chromium，不能宣称通过。

## 当前环境已执行的检查

- Python 全套自动化回归（包括新增功能、真实 FastAPI/SQLite、模拟外部网页与模拟浏览器 Worker）：通过；最终具体数量见交付包外的 `openfeed-consolidated-tests.txt`。
- Python compileall、前端及扩展 JavaScript 语法检查、ZIP 完整性：通过。
- Chromium 启动测试：本环境完整扩展加载超时；基础空白页面 `chromium --headless=new --dump-dom about:blank` 也超时。
- 通用 DNS：失败；源站真实网络抓取不能以 mock 测试代替。
- Docker CLI/Engine：不可用；Compose 文件静态验证通过，但没有运行容器，也没有完成生产级 egress 防护的渗透验证。

## 不得标为“完成”的发布阻断项

- 完整 Chrome/Edge MV3 扩展的实际安装、弹窗、浏览真实站点、选择与回传全链路。
- Docker 三镜像构建、容器私有网不可越界验证、真实 Chromium Worker 抓取和资源/负载测试。
- Oaktree、Bank of America Institute、Gold.org、KKR、Citi、猎聘等目标网站的实时抓取、持续更新与规则准确性验证。
- 公开 HTTPS 固定 Feed 的实际部署及 Readwise Reader 云端轮询、日期和 GUID 长期去重验证。
- 多日不间断运行、重启和数据恢复演练、安全漏洞扫描及独立部署审查。

**发布裁定：NO-GO（对公网正式提供服务）；可供本地受信单管理员评估。**
