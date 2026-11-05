# OpenFeed Studio 集中开发与验收报告

本次完成：

- `Recipe.content_type=jobs` 与 `complete_inventory`：只有在用户明确认定抓取结果覆盖全部岗位时，才能使用缺失状态推断。
- SQLite `items.missing_count` / `availability` 增量迁移，不删除原有数据或改变 Feed ID。
- 成功的完整清单扫描中，连续一次缺失标记 `missing_once`，连续两次标记 `possibly_closed`，岗位重现自动复位；普通文章与未声明完整的职位源不作下线推断；抓取失败时不变更。
- 管理端 `GET /api/feeds/{id}/lifecycle` 接口与编辑器状态查看；该 API 使用既有管理员认证。
- UI 新增研究文章 / 职位类型、完整性选择、误判警告。
- 新增专项单元和 HTTP API 集成测试；必须以本次完整测试输出为准。

## 实际验证边界

测试使用可复现的模拟职位链接和真实 SQLite/FastAPI，不是猎聘或 Citi 在线抓取成功的证明。完整 Chrome MV3 安装、外部金融网站连续抓取、Docker 实际镜像构建、系统级 Playwright 网络隔离和 Reader 云端订阅仍须在拥有对应条件的环境验证。

## 下一步必须验收

1. 完整 Chrome / Edge 扩展安装到数据回传的实机测试。
2. 外网可达机器部署后，实测固定公网 HTTPS RSS 与 Reader 轮询。
3. 提取各类动态研究页面，并在真正隔离的浏览器 Worker 中运行。
4. Docker 构建、重启、数据恢复、外部网络阻断和连续运行压测。
5. 以用户提供的金融研究和招聘网址逐站验证选择器、分页、GUID、日期及合法访问策略。

**发布裁定：仍为工程原型，未达到生产 GO。**

## 浏览器执行隔离架构（本轮新增）

- 主应用 `openfeed/browser.py` 不再直接调用 Chromium；必须使用独立 Worker。
- `browser_ipc.py` 通过 `/browser-jobs` 共享卷传递短生命周期、大小限制的任务文件；Worker 不获得数据库目录。
- `sandbox_worker.py` 使用 Playwright，仅在网络内部的浏览器容器内运行，禁用持久 Service Worker、下载和 WebSocket，并限制页面资源类型、数量和 HTML 大小。
- `egress_proxy.py` 作为双网卡公网出口，CONNECT/HTTP GET/HEAD 的地址必须经域名验证、IP 公网性验证和连接时 IP 固定；拒绝私有网络、链路本地和元数据地址。
- `compose.browser.yaml` 将 Worker 只接入 `internal: true` 的私有 Docker 网络；代理同时连接私网和普通出口网，且均不发布主机端口。主应用与浏览器容器不共用网络，仅通过任务卷通信。
- 新增 IPC、代理 CONNECT、私有地址阻断、拒绝内网 DNS、Compose 静态网络结构和 API→Worker→RSS 流程测试。

**验收边界：** 以上为源码级和模拟连接测试，未完成 Docker 实际构建、容器间到内网目标的攻击模拟、动态真实站点抓取和长时间稳定性验证；不能标为生产安全。当前环境中全量测试通过不表示上述项目已通过。

## Feed43 / RSSWebAll 风格兼容增强

全局捕获模式、重复条目捕获模式和带 `{%n}` 的字段组合模板现已接入 UI/Recipe/后端；添加大文档全局匹配与 API→RSS 测试。非完全兼容版，具体规则仍应逐例测试。

## 部署预检与 CI

`tools/preflight.py` 检查鉴权配置、公网 HTTPS URL 形态、Docker CLI、Chromium、实验浏览器启用状态及 DNS；输出 JSON。`production_go` 始终为 false，防止把本地预检误当正式验收。GitHub Actions 新增 Compose 配置检查及镜像构建作业（尚未在远端 CI 实际跑通）。

## 事件日志与可解释的规则诊断

- 新建 `item_events` 表：记录 `new / updated / missing_once / possibly_closed / reappeared`，保持事务一致性；每来源最多保留最新 1000 条事件，不删除文章历史。API 为 `/api/feeds/{id}/events`，管理界面展示近期事件。
- `GET /api/monitor` 根据上次成功时间、预计更新时间和运行状态报告 healthy、stale、error、never_succeeded、paused，不能替代外部主动监控。
- `POST /api/feeds/{id}/diagnose` 是只读的，可在当前 CSS 选择器失效时推导新的候选文章容器、预览候选有效项目数和日期覆盖；需要人工测试确认才能修改持久 Recipe。
- 岗位清单仅在明确启用完整库存、且分页没有触及提取上限的成功抓取后推进缺失状态。普通 RSS 轮询和部分结果不得推断岗位下线。

## 完整 Chrome 扩展安装验证仍不通过

当前环境使用 Xvfb + 系统 Chromium 启动完整 Manifest V3 扩展时发生启动超时。纯 Chromium `--headless=new --dump-dom about:blank` 也超时，说明目前缺少能可靠驱动完整浏览器进程的环境。已添加 `tools/verify_extension_install.py` 及 GitHub Actions 的独立安装验收作业，用于有完整 Chromium 的运行环境；**本地不可声称通过**。

## 本地构建与真实网页边界

当前环境缺少 Docker Engine/Compose，无法在本机核实镜像是否能够完成构建、Compose 私有网络是否确实阻止绕过代理的请求。已提供 CI 配置验证/镜像构建作业，但未在用户 GitHub 仓库实际执行。一般 DNS 探测失败，金融研究机构的原始网页抓取、定时更新及 Readwise Reader 云端 RSS 拉取仍然属于线上必验收项目，不能以公开网页搜索或模拟响应替代。

## 中英文界面基础支持

顶部新增语言切换入口，主要导航和 Feed 创建/编辑器核心字段、提取测试及授权界面支持英文与简体中文，语言偏好保存在本浏览器本地存储中（无凭据）。部分运行提示、动态活动文字仍使用英文，不能宣称完整国际化验收。界面不变更后端 Recipe 或 RSS 数据。

## 本地 300 源容量基准（不涉及真实爬虫）

新增 `tools/benchmark_local.py`，基准在临时 SQLite 文件中创建 300 条 Feed，进行 3 轮合计 900 次真实 `Store.finish` 数据库提交，产生 2100 条唯一记录，并对部分 Feed 进行标准 RSS XML 渲染。此环境测得约 0.897 秒总耗时、单次数据库刷新平均 0.620ms、p95 约 1.142ms；Python 进程最高 RSS 约 103MB。数据仅供同机同负载参考，不包括 HTTP 抓取、DNS、网站限流、Chromium、PDF、持续运行。实际部署容量必须重新实测。

运行命令：`PYTHONPATH=. python tools/benchmark_local.py --feeds 300 --cycles 3`。基准在临时目录中运行，不改动用户真实 Feed 数据。
