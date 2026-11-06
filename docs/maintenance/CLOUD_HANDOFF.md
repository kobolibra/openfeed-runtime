> 最新：Actions优化已上线并连续自动实跑；先读CURRENT。平台环境计时不占运行机，应用pin14d068b，原生cron只作小时兜底。

> 当前事实更新：2026-11-06T08:54:43.857375+00:00：云端生产切换已完成，原地址真实云发布/Pages/自动接续成功；管理界面留本机。先读CURRENT.md及TASKS_CLOUD.json。下文旧分阶段描述为历史合同，不是当前部署状态。

> 2026-11-05当前部署：免费公库薄workflow已通过Chrome提交3f71d14并REST逐字校验，固定私库source b9516dab、私有state分支；两轮免费8源通过。每10分钟schedule已配置、Nov7 20:09北京时间自动停用。首条schedule事件尚未观察，生产仍Mac；不要重复让用户公开runtime/增加权限/手工提交。GitHub connector可transport失败，原生Chrome CUA现可用。

> 最新事实覆盖下文规划时态：已有私库kobolibra/openfeed-runtime，main为源码、shadow-state为私密影子SQLite；cloud-shadow/cloud-batch手动工作流已实跑成功，cloud-validate完整477项及171RSS通过。公开薄工作流待用户选择；无生产schedule/无公共发布/未停Mac。继续TASKS_CLOUD当前状态，不重复创建仓库或远端连通性诊断。

# OpenFeed GitHub主运行迁移：接手主文档

更新：2026-11-05。用户最新要求：先完整规划与交接，便于额度耗尽后由不同agent持续完成迁移。**当前Mac仍是生产写入者；GitHub私有源码/影子状态及三类云运行已落地，尚未生产切换。** 本文件随源码携带；同机以实际源码为准，交接ZIP是有时间戳的检查点，不能覆盖更新的工程。

## 0. 下一位前15分钟

1. 读根AGENTS、CURRENT、DECISIONS、ISSUES及本文件。不重读全部聊天，不向用户重复索要旧183测试ZIP。
2. 同机定位LOCAL_RUNTIME所指真实目录；检查source与当前镜像/状态。读取最新snapshot，必要时重新采样。新机器先校验交接包manifest和private-state数据库，**不要调用当前Mac脚本去启动第二生产栈**。
3. 看下方阶段任务及TASKS_CLOUD.json，领取第一个尚未完成项，记录维护者/时间；一次只允许一个生产写入者。先在scratch/影子状态副本开发。
4. 第一个实施目标是 M1：实现不依赖常驻Mac后台的单轮批处理入口及无副作用试运行，不能先把全部171源投入新的定时任务。
5. 当前测试基线466通过；修改代码再跑对应测试，必要时完整回归。本轮交接文档不要求重跑全部测试。

## 1. 事实、授权与范围

- 产品是网页/公开API/原生RSS/PDF转RSS，保留原Readwise Reader固定地址。完整约束见DECISIONS，不另造“岗位监控”需求。
- 用户希望以GitHub长期承担核心运行，先要求全面规划交接；有源在Mac可用，不得以旧失败总数推断都要迁移。
- 仅两个一次性远端诊断已执行；没有持续远端抓取、私有源码仓库或云端权威数据库。不要把诊断工作流当生产runner。
- 公共仓库kobolibra/openfeed-feeds保留静态RSS/OPML；用户仅为公开请求诊断授权了工作流例外。**不得把OpenFeed应用源码、完整数据库、配置凭据或本交接包推到该公共仓库。** 实际迁移需私有代码/状态位置及最小权限发布通道。
- 不开通付费资源或付费额度，不关闭本地任务，直到相应方案/验收满足。私有源码位置、账户额度与发布凭据尚未配置，不能说已具备。
- 保留所有source ID、URL GUID、first_seen_at、历史条目、规则版本、查询范围、12小时相位与错误保留旧RSS语义。
- 原本地可视化管理/点选可按需保留；Actions不是常驻FastAPI服务器，Pages不能承载写入API。用户若以后要全在线管理，再单独设计认证后端。

## 2. 当前实际代码与运行组成

真实Mac源码：工作区work/local-trial/source；**不是outputs历史source副本，也不是源码旁openfeed.sqlite3**。
权威运行库：Docker卷openfeed-live_openfeed-data，/data/openfeed.sqlite3。
API与worker在Docker/Colima；宿主专用出口127.0.0.1:8900绑定en0。GitHub Linux runner上不可照搬en0/macOS socket选项或host.lima.internal代理。

| 代码/文件 | 复用点与迁移注意 |
|---|---|
| openfeed/app.py run_feed | 原获取、质量检查、store.finish、失败/Retry-After路径。当前import会根据环境变量打开Store/BatchJobs；必须先设DB路径，防止误写源码旁默认库 |
| openfeed/pagination.py | CSS分页及JSON offset最多3页、来源范围/偏移回显契约。仅首屏成功不能代替完整collect_pages |
| openfeed/extract.py、quality.py | 原规则、访问页识别、有效条目、官方空列表契约；不放宽来做迁移演示 |
| openfeed/storage.py | SQLite WAL、历史、规则版本、相位、冷却、recoveries。云批任务重用语义，不另造URL hash导致GUID改变 |
| openfeed/security.py | SSRF/URL验证、GET即时有限重试、HTTP fetch总截止；配置代理只接受现有固定值，不能随手塞任意URL作为“远端代理” |
| openfeed/egress_proxy.py、physical_network.py | 公共IP pinning、专用出口；Stage19共享预算、公平多地址回退及DNS/TCP阶段。Mac DNS假设不能直接移到runner |
| openfeed/browser.py、browser_ipc.py、sandbox_worker.py | 现为独立容器+文件IPC；保留隔离、公开地址验证与生命周期限制。runner可用适配Compose，非简单把API中直接启动无隔离浏览器 |
| openfeed/scheduling.py | phase、北京时间发布窗口；run_feed内部finish安排下一正常相位。批任务应按到期运行，不启动常驻scheduler无限循环 |
| ops/export_static.py | 当前从localhost API导出；可改为直接复用render_rss/Store的库级导出，或在同任务临时启动loopback API，需测试统一URL/ETag语义 |
| ops/publish_static.py | 独占发布锁、语义差异、不变不提交、失败保留旧公开文件；不要丢失现有功能 |
| work/stage6/run_auto_publish.py | Mac专用包装器，会启动Colima/本地栈，**不能作为GitHub runner入口** |
| work/stage3/compose.live.yaml/live_stack.py | 当前绝对路径与Mac代理配置；完整副本在交接包runtime；需新建适合runner的相对路径配置，不改坏Mac生产栈 |

## 3. 已做与不可重复工作的证据索引

- Stage13：出口时限/错误边界、TLS隧道不注入明文HTTP错误、诊断分类；Value Partners浏览器模式实际成功。证据work/stage13。
- Stage14：GET临时连接最多即时重试一次，1–3秒随机间隔；完整446通过。
- Stage15：SQLite同主机Retry-After冷却，所有run入口共用；CEPR原body误选修精确卡片，保存12条；完整451通过。
- Stage17：SQLite recoveries、原周期连续失败最多两次延迟恢复（5–15分钟、30–60分钟），不改原正常phase；HTTP fetch重定向/重试总时限默认45秒上限125秒。完整458+2专项通过。
- Stage19：连接共享剩余预算及多地址公平尝试、DNS/TCP诊断；466通过。171个实际RSS验证有效，最后该轮输出4128条（不是实时值）。旧的183/213测试、healthy总数均不代表当前验收。
- Brookings本地当前解析地址TCP超时，历史候选TCP可连但TLS重置；不证明哪款VPN致因。一次远端run41965774214取200/约0.12秒、原规则4条。**已经做过，不要再只提出“需要一个远端试试”。**
- 一次20源run41966397327：远端20个原请求全部200；原规则首屏17通过。HTTP/POST方式与数据保留，但Mac/GitHub curl与TLS平台不同，非完全同二进制对照。
- 本地同请求：Woodmac/世界银行/道富3项已通过，保留本地可用事实；两个猎聘browser不能用curl取代；14项是远端候选，不是已迁移。
- 未通过内容：摩根大通上海公司猎聘12155477、国泰基金猎聘8224343、Eurasia。两猎聘本地browser探测：没有预期left-list-box；请求数未达到70，不能臆断被70请求上限截断。一个现场触发captcha初始化API，禁止绕过。细节在liepin-browser-probe.json；未保存完整DOM的失败路径在liepin_browser_probe_detail.py已准备但未执行。
- Woodmac只是offset第一页（原3页），需补分页；世界银行原24指标；猎聘公司推荐职位不得混入本公司。

GitHub两次诊断工作流只有workflow_dispatch，没有schedule；不得误报已每12小时运行。现有公共Pages发布工作流与Mac发布仍存在，迁移时处理单一发布者。

## 4. 分阶段实施合同

### M0 交接检查点（本轮完成）
真实源码、在线SQLite、完整配置、状态/GUID/phase基线、关键测试/跨环境证据和任务表全部可取得；无管理令牌/个人浏览器/GitHub密钥。私密包不能上传公共仓库。迁移最开始再导出新基线，不能把本轮备份当最终切换库。

### M1 无副作用单轮runner（下一位第一项）
建议新增ops/run_cycle.py和可测试的生命周期封装。输入：明确db路径、public_base、当前时间、最大任务数/预算、dry-run或shadow模式；输出：每源结果与下一计划、状态快照、静态RSS目录/语义清单。默认不得写生产目录或发布。
- 设置OPENFEED_DB为scratch库；若借用app，先设置环境再import；关闭内置常驻scheduler，避免在同任务偷偷运行两套调度。
- 基于当前时间选due及recoveries；同源互斥、同域冷却/启动间隔、总并发、截止时间均有边界。到期任务留到下一次tick处理，不让runner原地等几十分钟。
- 打断/重试不能重复提交或清空状态。不要把非零退出等同全部来源失败；分源失败继续其他来源，保留历史。
- 使用私密基线副本；三类代表源：静态Brookings、JSON POST分页Woodmac、浏览器猎聘（只正常访问，不绕验证）。前两者有现成远端快照可离线复用，之后才做受控live。
验收：受控断网/429/慢响应/中断/重复执行/recipe变化，ID/GUID和正常phase保护；本地生产没有写入。

### M2 私密状态与权限
选择私有源码/状态存储位置。当前GitHub连接器无create_repository能力，REST/keychain写workflow曾404而连接器可写；不要据此误判账户全无权限。需要创建时可用已登录GitHub或明确所需的最小步骤，不索要聊天明文token。
SQLite要用online backup/关闭进程后的完整快照，不提交WAL/SHM孤立文件；不能拿普通cache或会过期的artifact作为唯一权威库。
原子状态checkpoint含上个状态hash、当前run ID、DB hash、源码ref、配置hash、发布manifest。单一写入者，并发控制同时覆盖手动与定时workflow；禁止两个runner各取旧SQLite再互相覆盖。保存失败则不发布新内容。
最小权限只给私有代码读取/私密状态写入/公共发布写入，不能把凭据放前端或artifact。控制私密状态历史增长及备份轮转。具体认证渠道尚未配置，不假设默认GITHUB_TOKEN可跨仓库写。

### M3 无发布影子运行
在新云工作流跑候选小批次，读取基线副本、只写影子状态；默认workflow_dispatch，尚不启用生产schedule。所有外部动作先准备成可审阅文件；不改公共源代码边界、不擅自开付费预算。
对171源建立一源一行验收矩阵：平台/请求方式、完整页数、提取与日期契约、空列表、GUID连续性、捕获证据、最后成功时间。现有20行表只覆盖部分首屏，不允许其余151源默认通过。
浏览器需要中国网络/登录前提的例外单列；不能承诺GitHub节点对所有猎聘均可用。若有无法迁移源，向用户提交具体例外与方案，不暗中换成别家公司或全站Feed。

### M4 批次和成本验证
每来源仍12小时相位分散；发布北京时间08–22每小时最多一次。不把171源每12小时同时突发，也不每小时全抓。
现有全局60秒启动间隔若照搬，仅每天342次正常启动就约342分钟/日，约10260分钟/月（吞吐估算，不是账单；另有安装/浏览器/同域等待）。私有仓库额度未核查，**不能承诺免费**。
公共标准runner计算免费是官方平台规则，但私密代码/状态可见性和artifact存储另算；公共薄包装访问私密代码/状态是可评估方案，需凭据/日志/PR隔离，尚未实现。不得为省分钟公开完整项目或数据库。
调度应按主机分散、有限批次和足够tick容量设计；例如53个同主机来源每12小时两次需要平均4.4次/小时，若只每15分钟tick且每域每tick一个，则容量不足。要测批次容量、积压和公平性，不照抄示例cron。
Actions有延迟/跳过风险，按实际时间补抓；公开repo60天无活动定时会停用。22点发布边界要测试：当前publication_slot仅22:00分钟有效，不能设22:17 cron却声称包含22点发布。允许晚点还是跳过需保留既定截止语义。
验收：实际运行耗时/含安装分钟、容量、每源延迟、同域最大并发、月成本估计、存储规模与预算封顶；未授权不启用付费。

### M5 原URL静态发布
使用原Pages base：https://kobolibra.github.io/openfeed-feeds；保留rss/<原ID>.xml与subscriptions.opml。pub manifest包含所有该保留旧Feed，失败源输出旧RSS而不是删除；用户明确删除的源不能重新出现。
先shadow比较语义变化与GUID；模拟Git push/Pages部署失败、重入、GitHubAPI暂时失败，重试不重复刷Reader。公开发布只带静态白名单文件，禁止SQLite/配方/后台/日志凭据进入。
至少两个正常周期端到端通过：远端获取→原质量→历史接续→静态文件→GitHub Pages实际HTTP/RSS。Reader账号验收单列，用户此前选择自行导入，不能假设已代验收。

### M6 切换生产与回滚
1. 保留Mac现状直到影子验收通过；切换前停调度并等在途写入结束，导出最后一次权威online snapshot及manifest；只允许一个云写入者从该版本接手。
2. 停用本地自动publisher；API可保留手动维护但OPENFEED_ENABLE_SCHEDULER=0。同步检查health LaunchAgent：它可能在Mac唤醒后自动用旧compose启动scheduler=1，必须一起改为只读/停用自动启动，不能只停当前进程。
3. 云调度启用，验证Mac关闭/离线后仍出现新RSS内容，地址/GUID不变。记录切换时间/来源覆盖/最后Mac DB hash/首云DB hash/回滚点。
4. 回滚时先停云调度与发布，取**最新云状态**，再单一恢复Mac；禁止用切换前旧库盖掉新历史。仅切换代码可使用镜像rollback，但保持DB前向兼容。
所有启动项动作只针对com.time.openfeed.*与本项目，不动用户VPN/其他服务/TimeMachine。

## 5. 已知资源、权限和操作坑

- 当前Mac空间有限；不再重复解压大VM或浏览器。已有Colima/Chromium/venv；移机环境不包含在源码包中，要按lockfile重建。
- 同机项目根不是标准独立git checkout；公共publish-repo是另一个仓库。别在根目录直接git add全部，尤其不能提交.private-state。
- CLI keychain凭据能读GitHub/调度workflow，但创建workflow REST返回404；GitHub连接器create_file/update_file成功。不要打印credential fill输出。创建文件时直接读非空YAML，曾有空文件提交随后修正，不要重复这个操作。
- CUA浏览器入口本轮超时，已终止fallback；不要把它当成功登录或已创建私有repo。
- 诊断artifact仅保留3天；关键正文已下载本地，交接包含必要body和metadata，不用等待/重新执行诊断。
- 外部GitHub artifact签名URL下载要用无Authorization的新客户端，不能把GitHub token转发到blob域名。ZIP解压验证路径、大小与总量，现成脚本已做。
- 一次诊断成功不代表计划执行；当前生产Mac仍是权威；“GitHub运行全部内容”尚未实施。

## 6. 同机最短命令（从工作区根运行）

```sh
work/venv312/bin/python work/local-trial/source/tools/maintenance_snapshot.py
work/venv312/bin/python work/local-trial/source/tools/check_handoff.py
work/venv312/bin/python work/stage3/live_stack.py ps
```

修改代码的完整测试cwd必须是source，Python用绝对路径：
```sh
cd /Users/time/Documents/Codex/2026-10-22/referenced-chatgpt-conversation-this-is-an-3/work/local-trial/source
/Users/time/Documents/Codex/2026-10-22/referenced-chatgpt-conversation-this-is-an-3/work/venv312/bin/python -m pytest -q
```

现有collect_comparison.py/validate_comparison.py读取已下载证据可复用；**remote_probe.py/dispatch_comparison.py带外部写入/dispatch动作，不为“查看结果”重跑它们**。读取结果只运行collect脚本或直接读已缓存JSON。

## 7. 每次交接必须更新

TASKS_CLOUD任务状态/负责人/产物、CURRENT、ISSUES、CHANGELOG、最新snapshot及handoffs/latest。每个任务写实现路径、实际命令、结果、证据、部署状态和下一步；中断也保留半成品/运行进程，不把planned改成done。
执行check_handoff.py；再检查迁移交接资料完整性与manifest。本地门禁不能强制忽略文件的agent，用户转交时必须给“从AGENTS和本文件开始”的明确指令。不要要求用户重复讲背景。

## 8. 原始需求追溯
私密包保留原用户两版需求/两版源列表和188项历史矩阵，见RESOURCE_INDEX。这些是历史资料，旧交接中自称测试通过/交付完成的文字不作当前证据；当前171源配置与DECISIONS中的合并、删除、暂缓、SCOPE-001必须一起对照，不因为数字不等就补建重复源。
