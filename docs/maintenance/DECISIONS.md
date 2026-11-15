# 有效决定与禁止反复讨论事项

来源：用户在本项目聊天中的明确要求；日期不明的旧决定不虚构具体时间。新指令覆盖时追加替代说明。

- 产品：网页/公开API/原生Feed/PDF转RSS，面向金融研究与招聘，供Readwise Reader订阅。不是岗位消失监控产品；不要无故扩展需求。
- 技术：FastAPI/SQLite，CSS/XPath/Feed43/JSON/PDF、分页去重、规则历史、MV3点选、隔离Playwright worker+IPC+egress、OPML、持久化队列。维持已有质量与安全约束。
- 本地试用优先尽量免费；Apple TV不是部署目标。Mac开机联网才能抓取；静态RSS托管GitHub Pages。Reader导入用户选择自行操作，未验收其账号订阅。
- 原12小时错峰刷新及北京时间08–22点每小时最多一次发布仍有效。曾提过10分钟/2小时推送的旧方案已被取代。
- 不依赖、询问或修改用户经常更换的个人VPN。专用物理接口出口并不保证不受系统过滤和ISP影响；不把未经证明的故障归因于VPN。
- 删除：Houhu、Gresham、Balfour、桥水中国招聘、两个Pantheon、格隆汇。旧报告中的这些失败不得重新计入待修复。
- BofA七个旧技术专题已合并到总栏目，不重建七个订阅。Jefferies和Broadridge曾授权使用实际跳转页面，但最新要求Broadridge暂缓，不继续扩展。Carlyle暂缓。
- Brookfield招聘仅中国大陆；不得换成全球列表冒充修复。
- Julius Baer来源 https://www.juliusbaer.com/en/insights/；Guggenheim来源 https://www.guggenheiminvestments.com/perspectives/ 。实际抓取端点以当前配方为准。
- 猎聘曾跳过，后来用户授权恢复通过项，跳过不是最新整体禁令。仅有其他公司推荐职位不能导入本公司RSS；需区分官方空列表与加载/访问失败，不能凭结构相同替代实际验证。
- 旧源码缺失时不得以记忆重构冒充原工程。目前有实际源码，权威目录见 LOCAL_RUNTIME；不要再要求重复上传旧ZIP作为例行步骤。
- 公开GitHub feeds仓库只放静态发布物；不得向其上传管理后台、源码、数据库或令牌。

- 2026-11-05例外授权：公共feeds仓库可新增并执行一次Brookings公开页面诊断工作流；随后用户要求对其他持续失败源全面跨环境排查，增加一次20源诊断。未授权全部来源持续GitHub迁移，后续须基于结果确定。工作流只含公开URL/公开请求数据，无OpenFeed应用源码、数据库或管理凭据。

- 2026-11-05最新推进指令：用户要求以GitHub长期运行方向继续推进，因额度可能耗尽，本轮优先完成细节齐全、含真实文件的迁移规划与多agent交接。后续可在既定免费/私密约束内继续开发和影子验证，不必重复询问是否可以开始；尚未授权公开应用源码/数据库、启用收费或未验收即停用Mac生产。权限不足时只询问具体缺项，不让用户重讲背景。

- 2026-11-05用户明确允许公开feeds仓库新增薄运行workflow，源码/SQLite/配方/运行日志保持私密，按免费标准runner方案继续。随后用户将openfeed-runtime改为public；已检测并就其中既有SQLite/配方的处理方式询问，答复前暂停私密上传。不默认把可见性修改解释为对私密数据公开的知情授权，也不擅自撤销用户新设置。

- 最新：用户明确“恢复私有，继续免费方案”，随后确认已亲自改回private。继续公库薄workflow免费compute，源码/状态/日志不公开；有限48小时影子验收后再决定切换，Mac仍生产。

- 用户再次确认关注private Actions额度。保持源码/SQLite私密、compute在公库标准runner；此前private测试计入额度，当前private无活动任务，不再把runtime公开。不要擅自启用收费、更大runner或私库高频定时。

- 2026-11-05用户明确答复“允许，直接部署并验收”：允许新增feeds加密Secret OPENFEED_RELAY_HMAC以及通过签名校验的Actions自动接续同一私有状态；仍十分钟间隔、既定48小时截止、单写入者、不收费。该授权不等于允许提前停Mac或将影子库作为最终生产库。

## 2026-11-06T08:08:28.159217+00:00 明确删除、不得重建
用户要求Man和Eurasia不要做并删除，Cantor无法解决就删除。Cantor正常HTTP/原隔离浏览器反复403且无验证修复，因此执行删除：
- Man Group · Insights：4eb10889d95da4ae84cfe4ab1d46
- Eurasia Group · China Search：95d1c47e63b41f814f17d344646a
- Cantor · Insights：132114da2be6a7af5f9cb6f59af3
Mac、云端权威state、公开OPML/RSS已删除；私密完整备份保留。此用户指令优先于旧171源身份约束；剩余168源继续完整保护。云端deleted-sources.json为明确墓碑清单，禁止从旧预演/备份重新引入。

## 2026-11-06T08:54:43.857375+00:00 云端生产、本机管理与长期免费运行
用户要求尽快部署切换、管理界面保留本机，并明确选择“长期免费自动运行”。据此移除临时48小时截止；标准公共Linux运行，私有源码/状态/日志，既有Secret，未启用收费。Mac自动抓取/发布停止，云端首次真实RSS发布和Pages已成功。管理桥不得disable云workflow；必须以配置基线与Git CAS保护最新云历史，Mac离线不能阻断云端。

## 2026-11-06T15:36:38.594329+00:00 Actions效率与可靠接续优化
# 当前状态：云端生产与Actions效率优化已验收（2026-11-06T15:36:38.594329+00:00）

云端生产持续运行，本机 http://localhost:8765/ 保留管理界面；本机不自动抓取或发布。原RSS/OPML地址、来源范围、GUID/首次发现时间与12小时刷新相位均不变。用户授权长期免费运行；源码/SQLite/配方/日志私有，计算仍用公共标准ubuntu-latest，未启用收费，私库三个Actions入口全停用。

本轮实际部署：公开workflow bf568e72fcf9a59f8384140a924592dd9d81cc79，抓取源码固定14d068b0cf3fa3239c3862bec10bd048d13664be。独立authorize/runtime/interval任务；平台环境openfeed-publication-interval等待10分钟后才给interval分配运行机。实测waiting时runner_id=null，释放后签名自动接续，已连续运行数小时。原生cron实测有长延迟，因此只保留每小时兜底，不能退回纯cron并宣称可靠。

- 旧4个样本每轮空占225–459秒；新完成样本平均运行机时间181.3秒，旧样本595.8秒，观察样本下降69.6%。批次不同，此数不承诺所有负载均有同样降幅。等待阶段已确认不占运行机。
- 标准库只读预检：无任务直接退出，不安装依赖、不建容器、不写DB checkpoint；只有发布任务时跳过抓取容器。HTTP批次按需启动隔离浏览器；13个browser源保留原安全隔离，提前覆盖本轮可能到期的浏览器任务，避免漏准备。
- 仅缓存公开PyPI依赖，不缓存私有应用镜像/源码/数据库/日志。授权任务只取relay-cursor.json，不重复下载SQLite；触发Actions写权限仅给独立interval任务，抓取任务仅contents/pages写权限。没有新Secret，沿用已授权HMAC；移除计时规则或过早释放会拒绝接续，防止运行风暴。
- Git全局并发组、快进CAS、源身份/phase/GUID保护均保留；游标遇管理修改竞争只重置未被接受的本地元数据副本，不回盖远端DB。失败证据只写独立私有诊断分支，无公开日志artifact。
- Linux完整测试524通过；首次附加Docker smoke发现YAML缩进错误，未部署，修复后独立Docker实测42200002379通过（HTTP计划15.199秒、浏览器额外47.968秒、零真实来源请求/输入不变）。配置/计划/生命周期13项、环境时钟/签名权限30项专项通过。Mac宽回归519通过/6个浏览器受系统权限限制，另外3个mock响应测试通过；以Linux实际结果为跨平台验收，不能隐去本机限制。

最新数据：{'feeds': 168, 'items': 4106, 'status': {'error': 2, 'healthy': 166}, 'original_4102_guid_first_seen_preserved': True, 'scope_phase_unchanged': True}。本机同步：{'status': 'synced', 'checked_at': '2026-11-06T15:35:42.391751+00:00', 'cloud_run_id': '42243184972', 'database_sha256': '1fa361faa6187f99901aac6707c985bfcc34927fabe8741e871575cb9bef6c23'}。Julius、CEPR403继续单列，保留历史；Man/Eurasia/Cantor已删除，不得从旧171源包恢复。真实管理编辑->云提交未用测试性生产改动验收，原隔离测试和实际读取同步仍有效。

证据：/Users/time/Documents/Codex/2026-11-05/users-time-documents-codex-2026-10-3/work/optimization-20261106；final-receipt.json、live-efficient.json、baseline-times.json、linux-full-524-42198839355.log、linux-probe.log、environment.json、privacy-cost-storage.json。正式交付：/Users/time/Documents/Codex/2026-11-05/users-time-documents-codex-2026-10-3/outputs/OpenFeed-cloud/Actions优化验收-20261106.json。

回滚只换工作流/代码并保留最新云DB；已知可用旧签名relay可暂时恢复，代价是恢复空等。纯cron实验不作为可靠回滚点。用户本机管理桥、个人VPN和Reader订阅无需改动。长期平台可用性及用途规则仍受GitHub约束，本轮优化不构成永久托管承诺。
下一步：持续正常周期质量观察，独立研究两源403；不重复迁移、不启用私库高频计算、不为省时削弱来源质量或浏览器隔离。


## 2026-11-06T16:46:30.154354+00:00 用户要求20分钟试运行（当前有效）
现有openfeed-publication-interval环境wait_timer已从10改20，并独立GET验证20。没有修改workflow、应用pin、数据库、每轮6源上限、来源12小时相位或RSS地址；等待仍不分配运行机。原生cron每小时兜底保持。已有等待轮可能仍使用进入时的旧计时，后续新等待按20分钟；完整20分钟自动接续效果尚待正常运行观察，不能仅凭配置读回声称完整新周期已验收。原脚本/工作流内10分钟为最低防风暴门槛，实际等待由环境20控制；以后维护不得用旧prepare_environment脚本或旧10分钟记录恢复环境。理论每日约72轮，实际受队列与启动开销影响；关注积压、429重试及源新鲜度，不能承诺432理论容量就是实际吞吐。回滚仅将同一环境wait_timer恢复10，不回滚任何DB。
证据：/Users/time/Documents/Codex/2026-11-05/users-time-documents-codex-2026-10-3/work/interval-20m-20261107/environment-before.json、environment-after.json。


## 2026-11-15｜用户指令：直接合并（代码进入 main，不触发生产发布）
- 用户对 openfeed-runtime 的修改要求为“github 提供 PAT、认真分析思考、直接合并、顶级交付”。
- 本轮按指令将访问受阻页识别代码合并进 main；明确不改 Actions pin、不做任何生产部署宣称，云端仍运行 pin 源码；本机管理镜像与快照属本机，需用户本机完成 check_handoff 门禁（sandbox 无权限）。
- 未经本轮指令不得扩大改动到 workflow、数据库、来源配置、调度相位、GUID/历史；既有来源删除决定不受影响。

