# OpenFeed Studio 本轮工程验收（2026-10-22，Asia/Shanghai）

## 结论

**原始源码已真实取得；6 个真实页面源已生成 111 条 RSS；本轮本地验收有真实证据，仍不具备生产放行条件。**

原始 `OpenFeed-Studio-Source.zip` 与 `openfeed-studio-batch-cancel-183.zip` 字节一致，均为 194,851 字节，113 个成员，CRC 校验通过，SHA-256 为 `f8e8cfa09f8cb31bc407321140371f7917b5f7d5dda6ca586470fae066f076a1`。解包前检查路径穿越和符号链接；原包单独保留。没有使用记忆重建替代原工程。

原始测试在 Python 3.12.14 的清洁环境中实际执行：**177 通过、2 失败、4 跳过**，合计 183 项。失败/跳过来自 Linux Chromium 路径和检测方式。首次并行验证因默认数据库共用而出现锁冲突，随后为验证进程设置独立数据库，结果以上述完整重跑为准。

修复后：**194 项 Python 测试全部通过，无跳过；4 项 JavaScript 弹窗测试通过；真实 Uvicorn/Chromium/SQLite 的 19 项本地管理与恢复检查通过。** 这些数字是不同范围的检查，不相加宣传为完整外网端到端验收。已另外从 6 个真实站点页面快照生成 111 条 RSS，并通过独立解析和真实 HTTP 接口核验；完整 MV3 工具栏点选、Docker 运行网络、默认抓取器在线更新和 Readwise 云订阅仍未通过。详见 RSS_RESULTS_20261022.zh-CN.md。

## 已修复问题与证据

| 问题 | 影响及改动 | 主要代码 | 失败与修复证据 |
|---|---|---|---|
| 批任务取消后继续执行后续抓取 | 每项执行前检查持久化状态；提交进度失败即停止循环；已经进行中的一个抓取允许结束 | `openfeed/app.py:process_batch` | `evidence/audit-before.log`、`evidence/final-tests.xml` |
| 单页 100 条上限未暴露为截断 | 达到上限时完整性未知，完整招聘清单拒绝推进失踪状态；PDF/Pattern 输入截断同样标记 | `openfeed/pagination.py` | `tests/test_intake_audit_regressions.py`、`evidence/audit-before.log` |
| 质量校验丢弃条目后仍视为完整招聘库存 | 完整库存有被拒条目即失败，保留最后良好内容与岗位状态 | `openfeed/app.py:run_feed` | `evidence/inventory-before.log`、`evidence/final-tests.xml` |
| PATCH 显式 null 造成 500 或损坏 recipe | 区分省略与 null，明确返回 422，不写入数据库 | `openfeed/app.py:Update` | 四个失败前用例及最终回归 |
| IPC FIFO 导致阻塞 | 读取描述符时使用 O_NONBLOCK，然后验证普通文件、大小、链接和内容 | `openfeed/browser_ipc.py`、`openfeed/sandbox_worker.py` | 两个进程级超时复现及最终回归 |
| 浏览器测试无法跨平台复现 | 支持显式路径、PATH、Playwright 管理的 Chromium；异步测试调用发现函数也可运行 | `tools/browser_support.py`、四个浏览器测试文件 | 原始测试日志、最终 194/194 |
| 清洁 dev 安装漏装浏览器测试依赖 | 声明 Playwright/独立 RSS 校验器；记录完整锁定版本；CI 安装 Chromium | `requirements-dev.txt`、三个 lock 文件、CI | `evidence/install-python312-retry.log`、`evidence/lock-install.log` |
| 移动端品牌、列表列位溢出和批量按钮缺样式 | 隐藏紧凑导航文字与次要列；统一控件样式；不削弱 CSP | `static/styles.css` | `evidence/http-ui-final/04-mobile.png`、19 项 HTTP/UI 检查 |
| macOS 基准内存单位错误 | macOS 的 ru_maxrss 以字节计算，分别换算 MiB | `tools/benchmark_local.py` | `evidence/benchmark-150.json` |

## 按指定顺序的验收矩阵

| 阶段 | 通过标准 | 实际结果 | 证据 | 状态/下一步 |
|---|---|---|---|---|
| 源码接收 | 原包可读、CRC/成员/哈希可核对 | 两个原包完全相同，113 成员真实源码与测试 | `evidence/intake.json`、`original-source.zip` | 通过 |
| 清洁安装与测试 | Python 3.12 新环境、依赖一致、全套执行 | 初次包下载 DNS/传输超时后重试成功；第二个新环境从本地缓存按锁安装，依赖检查/导入通过；最终 194/194 | install、lock-install、final-tests 日志/XML | 通过（macOS；Linux 构建未验证） |
| 完整 Chrome MV3 | 安装、真实工具栏 activeTab 授权、真实点选、runtime/storage 回传、Studio 导入 | 安装 service worker/弹窗实测通过；内容点选→RSS 的原测试使用 Chrome API 仿真；另建真实 MV3 人工点击脚本已进入待点击状态，但原生工具绑定到另一个 Chromium 进程，未完成 | `extension-install.log`、`extension-live.log`、`extension-live-final.log`、`tools/verify_extension_live.py` | 部分通过；需在可操作工具栏的浏览器运行脚本，不能报完整通过 |
| Docker Compose 隔离网络与动态抓取 | 三镜像构建、worker 仅 internal 网络、公开源可抓取、私网/元数据/旁路不可达 | 只有离线结构检查与模拟网络/IPC 回归；本机 Docker 命令为指向不存在 Docker.app 的失效链接 | preflight、环境记录、网络相关测试 | 阻断：需要 Docker Engine；本轮锁定的镜像依赖也未构建验证 |
| 安全与故障注入 | SSRF、重绑定、畸形代理请求、IPC 文件、失败留存、批任务恢复 | 单元/集成安全回归通过；FIFO 进程级阻塞已修复；真实 HTTP 未认证返回 401；短时持久性工具有崩溃/WAL 回滚与任务 interrupted 验证 | audit-before、inventory-before、final-tests、http-ui-final、durability | 本地范围通过；容器逃逸/生产网络未验收 |
| 九个真实来源 | 合规、抓取到正确文章、标题链接日期、翻页去重、生成 RSS、重复轮次稳定 | 真实应用 HTTP 客户端请求 robots 阶段，九域全部被非公开 DNS 返回值拦下；随后按固定白名单系统网络取得 6 站真实快照，明确规则生成 111 条 RSS；两条网络链路分开记录 | `live-sources/results.json`、`dns.json` | 阻断：本机返回 198.18.*；需要真实公网 DNS/适当部署网络 |
| RSS 与 Readwise | XML/RSS 解析、GUID 稳定、HEAD/ETag、公网 Reader 实际拉取 | 独立 feedparser 解析合成 RSS；真实 HTTP GET/HEAD/304 通过；数据库恢复后 RSS 字节一致；没有 Reader 拉取证据 | `http-ui-final/results.json`、合成 RSS/OPML | 6 站真实快照 RSS/HTTP 校验通过；公网稳定 HTTPS origin 和 Reader 操作环境缺失 |
| 专业管理 UI | 鉴权、搜索、诊断/历史、暂停恢复、导出备份、窄屏 | 真实本地 HTTP/Chromium 19 项通过；桌面/编辑器/迁移/移动截图；错误控制台为空 | `http-ui-final/` | 已列本地闭环通过；实时站点规则创建和云端订阅仍受上述限制 |
| 部署、备份、稳定性 | 可复现部署、在线备份、离线恢复、故障后稳定、持续运行 | 真正下载 SQLite、integrity_check、恢复/重启并确认 RSS 不变；150 源 10 轮存储基准；另有 120 秒短时耐久记录 | `http-ui-final/`、`benchmark-150.json`、`durability/`、部署指南 | 本地恢复通过；120 秒不是 7×24 或长期在线证明 |

## 九个来源逐项记录

九域的应用侧结果均为 `robots_unavailable`，错误为 `DNS returned a non-public IP address`。因此默认应用抓取器没有继续请求其内容，也没有设置该链路成功标记。后续系统网络只读采集取得真实页面并验证 6 份 RSS，见专门 RSS 报告；下表保留默认抓取器的失败证据。DNS 返回地址逐项如下：

| 来源 | 原始/核对地址 | 返回地址 | 附加观察 |
|---|---|---|---|
| Oaktree Memos | https://www.oaktreecapital.com/Insights/memos | 198.18.0.194 | 外部网页读取工具也未取到该页；不是应用抓取证据 |
| BofA Institute | https://institute.bankofamerica.com/transformation.html | 198.18.0.195 | 网页读取工具能看到公开列表；应用客户端仍未成功 |
| Gold.org | https://www.gold.org/industry-insights | 198.18.0.196 | 网页读取工具能看到行业文章；应用客户端仍未成功 |
| KKR | https://www.kkr.com/insights | 198.18.0.197 | 网页读取工具返回部分页面，不能证明动态列表已抓取 |
| Morgan Stanley | https://www.morganstanley.com/insights | 198.18.0.198 | 官方 `/ideas` 页面重定向至 `/insights`；未验证应用提取 |
| Capital Group | https://www.capitalgroup.com/institutional/insights.html | 198.18.0.199 | 官方页面要求美国机构投资者资格与条款声明，未代用户作声明 |
| CEPR | https://cepr.org/voxeu/columns?title=China | 198.18.0.200 | 网页读取工具也未取得内容 |
| Citi Careers | https://jobs.citi.com/search-jobs/China/287/2/1814991/35/105/50/2 | 198.18.0.201 | 网页读取工具也未取得内容 |
| 猎聘 | https://www.liepin.com/company-jobs/8652522/ | 198.18.0.202 | 网页读取工具跳转 `safe.liepin.com` 验证码；没有绕过 |

外部网页工具只用于核对公开网页与访问限制，与应用实际请求严格分开。原工程的 `tools/pilot-sources.csv`、`samples/pilot_sources.csv` 是候选名单，不是已经验证的 150+ 源清单。

## 最少剩余条件

1. 带 Docker Engine/Compose 的目标机器，用于构建与实际隔离网络/动态 worker 验收。
2. 返回真实公网地址的抓取网络；不能把允许 198.18.* 加入 SSRF 保护作为修复。资格、登录、验证码须由相应服务允许的方式处理。
3. 能实际操作安装扩展工具栏的 Chrome/Chromium 会话，完成 `verify_extension_live.py` 中尚未完成的真实权限与回传验收。
4. 稳定公开 HTTPS RSS 地址及可用的 Readwise Reader 操作环境，才可证明云端订阅成功。
5. 上述网络部署完成后，继续多周期/长时间观察；本轮短时本地测试不能代替长期生产运行。

归档中的历史报告保留原样用于追溯；本报告、当前 README、实际日志与验收矩阵优先用于理解本次状态，不沿用旧“183 已通过”作为证据。
