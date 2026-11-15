# 维护日志（追加记录）

## 2026-11-03｜历史基线整理
- Stage13/14已部署；446项测试通过仅指代码回归，不是来源全部验收。
- 连续失败、403及浏览器等待失效仍未全部解决。详情见CURRENT、ISSUES及stage13/14证据。
- 本轮建立AGENTS入口、用户决定、当前状态、问题台账、只读快照及交接检查工具。
- 本轮未修改抓取配方、刷新间隔、数据库或部署；交接工具实际验证结果在本日志末尾补充。

## 2026-11-03｜交接规范落地与验证
- 用户补充要求：每个接手agent在维护期间及再次转交时都必须继承本规范。
- 已创建源码与工作区两级AGENTS入口；源码内维护记录随工程移交。
- 已实现只读快照与交接检查脚本。2026-11-03T15:41:44Z真实API采样：171启用，153healthy、18error、0paused。
- 快照不输出完整配方、URL查询、令牌或原始错误正文；源码指纹仅覆盖openfeed/ops Python，并非全部工程或镜像证明。
- 当前没有私有源码仓库CI强制规则；本地门禁依赖agent遵守入口。不得宣称能技术上强制任意外部agent。
- 本轮仅文档及维护工具修改，没有抓取逻辑/服务部署；未运行与此无关的446项完整回归。

## 2026-11-04｜稳健性改进进行中
- 目标REL-001：针对当前仅单来源Retry-After处理，增加SQLite持久化的同主机冷却，所有刷新入口共享；保持正常相位与RSS历史。
- 修改前证据：app.run_feed仅对本来源defer，兄弟来源仍可访问；参考Scrapy按域限速及RFC9110 Retry-After。计划修改storage.py/app.py并添加持久化与隔离回归。

### Stage15实现与验证
- CEPR错误已演变为质量门槛；body误选只取1条，改精准结果卡后保存刷新12条成功，保留China筛选与原门槛。
- 同主机冷却SQLite持久化、所有run入口共享；451项回归通过、模块哈希匹配、在线历史/相位保护通过。
- 其余来源连接复验仍运行；最终以本轮交接记录为准。未公开源码、数据库；没有放宽网络安全。

### 2026-11-04最终交接
- 复验结束：155healthy/16error/0paused，CEPR与ANU本轮成功；其余失败如实保留。
- 451项测试、171RSS及4118GUID保护验证完成；Stage15已部署，REL-002/003/004仍未实现。
- 证据work/stage15；未运行Reader账号验收，未声称16项恢复。

## 2026-11-04｜专业抓取故障方案调研进行中
- 用户要求全面对照成熟爬虫和服务对拒绝/限流、连接/TLS、响应超时的专业处理。
- 本轮仅技术调研与源码差距审阅，不进行付费服务试用、账户创建、网络配置修改或抓取逻辑部署。
- 审阅发现：每次HTTP新建会话、每次浏览器新建上下文；DNS等待8秒与物理连接总10秒存在嵌套预算风险。是代码事实/设计风险，不证明全部来源根因。

### 专业故障调研交付
- 交付官方机制比较、源码差距、分层故障决策及实施/验收顺序；未更改抓取逻辑、未部署、未购买服务或测试商业抓取成功率。
- 明确单会话冷启动、嵌套DNS/连接时间预算、逐地址回退、浏览器业务就绪、单出口等设计风险；不将假设冒充全部来源根因。
- 新增REL-005/006/007供接手；本轮不重复451项回归。

- 调研结束采样UTC2026-11-04T03:00:12Z：154正常/17错误；新增Brookfield与Citi连接错误，J.P. Morgan Private Bank Asia · Insights状态恢复。本轮仅只读核对，不声称已修这些变化。

## 2026-11-04｜Stage17改造进行中
- 基线154正常/17错误；本轮目标REL-002受控持久化恢复，以及REL-005抓取总截止时间。
- 计划：storage.py新增恢复状态并合并到调度候选，不改正常相位；仅GET临时错误，每周期最多两次恢复；security.py增加含重定向/即时重试的总预算。证据work/stage17。

### Stage17已部署与验证
- 持久化恢复（临时GET、每周期连续失败最多两次追加）、HTTP含重定向/即时重试总时限落地。458项完整+2项截止测试通过，真实模块哈希一致。
- 在线4124GUID无损、171RSS正常，Citi恢复、Brookfield原范围官方空确认。最终156healthy/15error，API有12个待恢复任务，未声称其已到期成功。
- 人工复验结束；既有自动调度与恢复计划继续。证据work/stage17；Stage17前镜像及备份保留。

## 2026-11-05 Brookings专项
- 实读来源：连续28次失败、最后成功10月26日；独立连接分层探测证明当前地址TCP8秒仍超时、历史候选TLS被重置。
- 多DoH返回不一致/端点不可达；不把地址差异直接定性为特定来源污染，不改个人VPN。
- 外部web可读China页；本机仍未取到页面，本轮未改规则、代码或部署。增加BRK-001；证据work/brookings-20261105。

## 2026-11-05 Stage19共享出口检查进行中
- 用户要求继续修复，区分Brookings单站与整个OpenFeed共享链路。
- 已有证据：Brookings未进入HTML阶段；当前地址TCP超时、旧候选TLS重置，不是全部来源同根因的证明。
- 目标：共享连接总预算与多地址公平回退、DNS/TCP阶段错误可见；保持公共IP/证书校验，不改个人VPN。证据work/stage19。

### Stage19已部署及远端证据（任务继续）
- 共享出口预算/多地址公平回退与DNS/TCP阶段诊断已部署；466项回归通过，171RSS正常。Brookings本地保存刷新明确stage=tcp仍失败。
- 用户授权一次Brookings GitHub诊断，已执行成功：run41965774214，HTTP200/0.122秒，原规则提取4条有效内容。未开启持续远端抓取。
- 用户未确认持续单源方案，转而要求全面排查其他持续失败源是否同样需要GitHub；当前授权下一步为同请求跨环境诊断，不等于全部源持续迁移。
- 证据work/stage19；先前API写工作流404，改用GitHub连接器写入成功。最初空文件提交立即修正后才dispatch，唯一诊断run如上。

### 20源对照与全云可行性
- 跨环境一次性诊断run41966397327完成：远端20请求HTTP200，原规则首屏17通过；2猎聘browser及Eurasia内容未通过。本地3项HTTP内容通过，14远端候选，非全部需迁移。
- 用户转而考虑全项目长期GitHub运行。已核查官方runner、schedule、Pages与计费限制；形成迁移设计，未实际迁移或停止Mac，也未创建私有仓库/付费资源。
- 待补全分页、浏览器、权威状态持久化及完整RSS闭环验收。

## 2026-11-05｜额度接续专项规划交接
- 用户最新要求优先完整规划、所有必要真实文件与细节，供不同agent交替继续GitHub主运行迁移。
- 已创建CLOUD_HANDOFF阶段合同、TASKS_CLOUD任务依赖、RESOURCE_INDEX和根NEXT_AGENT_START入口；AGENTS强制读取当前迁移文档，check_handoff检查相应文件和依赖图。
- 在线SQLite备份171源/4189条，integrity_check=ok，完整配置与ID/GUID/phase校验基线已保存；没有导出管理令牌或GitHub凭据。
- 首次包校验通过：383个文件（约20MB未压缩）；含真实源码/私密状态/精选证据与研究。最终打包前再次验证；最终结果在本轮交接记录。
- M0交接完成后下一项M1；本轮不修改抓取逻辑、不停Mac、不启用云调度、不创建付费资源。私有仓库、认证、云端runner与171源闭环尚未实现。

- 已找到并纳入原始用户需求/来源列表及188项历史矩阵，明确历史状态不覆盖当前约束。

- 最终私密ZIP已实际解压复验：393文件、SQLite/ID/GUID/phase一致；篡改源码与删除数据库均被检测。约4.7MB压缩包，实际管理员令牌值扫描未进入包。结果outputs/OpenFeed-迁移总交接-20261105/VALIDATION.txt。M0完成，下一实施项M1。

## 2026-11-05 M1实现进行中
- 用户要求继续推进。目标ops/run_cycle.py：只读计划、全新私密scratch副本、原run_feed处理、离线fixture可重复验证、无生产写入和无发布。
- 不import app直到显式设定scratch DB与关闭调度；独立CLI进程避免模块全局状态串库。证据work/m1。

- M1 shadow入口与四项专项已实现通过；真实Brookings捕获页用原pipeline写影子库成功。输入未变、4189历史GUID无损。完整回归根cwd四项路径失败，已按source cwd重跑，保留失败记录。尚未满足M1全部验收，不提前进入生产迁移。

- source cwd完整回归470项通过、1条第三方警告。最终快照148healthy/23error；M1未部署，生产Stage19未变。M1剩余验收保留在任务表。

## 2026-11-05 M1接续开工
- 维护者：当前接手agent；目标：补完整分页/browser替身、取消与重复执行验收，修正计划报告并提供导出清单/下一计划。涉及ops/run_cycle.py、tests/test_shadow_cycle.py；证据work/m1-continuation。仅影子副本，不部署。
- 假设：沿用原pipeline可保持GUID/phase；需用故障注入验证。最初只读快照被环境网络权限阻断，已获本轮网络权限后重试。

### M1接续验证结果
- 修正报告选中集合，新增延后原因、计划及RSS校验清单；仅在影子SQLite保存启动记录，不改production Store。
- tests/test_shadow_cycle.py：8 passed；完整最终469 passed/6 failed/1 warning，浏览器启动Permission denied，日志full-tests-final.log保留。第一次完整回归与编辑有时间重叠，仅最终重跑为最终验证依据。
- 真实Brookings捕获复演成功；原始交接manifest 393文件全部一致。未部署/未发布/未启用云调度。
- 同域节流仅在以上一轮影子DB为下一轮输入时连续；独立从旧基线分叉不具备跨分支锁，禁止当云权威状态方案。

## 2026-11-05 GitHub实际迁移推进
- 用户指出私有仓库已存在；实测kobolibra/openfeed-runtime private=true/admin+push=true，main仅README、无workflow/run。旧TASKS私库字段过时，立即更正。
- 开工M2/M3基础设施：在既有私库导入白名单源码；shadow-state保留私密基线、shadow workflow单一并发组与CAS git push，无生产发布/无schedule。M1未完成项保留，不冒称其done。

### GitHub真实部署结果
- 私有源码main已导入、shadow-state已初始化，三类实际云端抓取及checkpoint回写成功。workflow权限通过新连接的GitHub插件解决，未重复创建仓库。
- 云端SQLite已下载验证4189历史身份无损/相位保留/完整性ok；保持Mac生产和单公共发布者。
- clean Linux回归首轮474通过/1缺dns依赖，已加入项目已有固定dnspython重跑。原宿主6项Chromium权限失败在Linux上均通过。
- 新增cloud_tick有限批次/身份门禁/覆盖矩阵，修复candidate hash校验；11项专项通过。数据库直接静态导出及语义校验2项通过。
- 用户待答复公开薄工作流或私有额度方案；不擅自突破公共仓库约束、不启用收费。

- 后续Linux477项完整通过、171RSS校验通过；4源真实批次run42008521595全部success/新增2，checkpoint与身份门禁通过。新增SIGTERM中断/重启与DB直接导出后本地14项通过；尚未公共发布或生产切换。

## 仓库可见性变化
- 用户已批准公开feeds薄工作流方案；随后将runtime改public。匿名实测两repo均public，暂停私密上传与新dispatch。已向用户提出恢复私有/代码公开而状态另迁两种具体处理；当前没有配置新的deploy key或Secret。
- GitHub连接器读调用出现transport失败/权限自动审核超时，已用匿名REST核实可见性，不将其误报仓库不存在或权限全无。

## 免费云入口实跑
- runtime已恢复private；最小repo部署密钥和公库加密Secret已配置，旧私库写workflow disabled。公库固定ref、显式shadow+期限入口首轮run42025905503成功，第二轮42034400400进行中。
- 完整定时自动停用配置已准备；工具反复transport失败未提交成功。精简/缺自停版本自动审批明确拒绝，已补完整护栏，不绕过拒绝。用户已被请求提交完整文件这一个具体步骤；cron未启用。

独立下载最终补验：直接HTTPS到GitHub API（仅维护下载、不改变生产出口）成功；最新云库4194条，原4189身份零丢失/phase保留/integrity ok。代理下载失败日志保留。

## 2026-11-05 21:31北京时间｜定时提交已解除阻断
- 连接器持续transport失败，随后CUA原生Chrome恢复可用。已通过用户已登录的GitHub编辑器直接提交完整受限版本，commit3f71d1462cec8171bfefe18b0ec267f01e35dd79。无需用户增加权限或手工提交。
- 匿名REST读取实际文件，与审阅的outputs/OpenFeed-cloud/runtime-cloud-48h.yml逐字一致；blob20c1f62cf997d4d250b80db29414ee758961aa09。cron每小时7/17/27/37/47/57分钟，单一并发组；期限后先disable该workflow并跳过全部private checkout。
- 当前已配置schedule，尚未观察第一条event=schedule，不能把两轮workflow_dispatch成功算作定时触发成功。两轮免费run42025905503/42034400400均成功，共8个来源原pipeline success；实际job耗时257/266秒。
- 独立云库校验4194条、原4189身份无损/phase保留/SQLite ok。影子结果不等于全部171源或两周期验收；Mac仍生产、云不公开发布。

补充实测：两轮免费job分别耗时257/266秒，每轮4源全success，低于10分钟tick间隔；原12小时phase不变。矩阵现为14源非空单次成功、2源原空列表契约单次观察，155源尚未云端观察，不等于16源长期验收。

### 计费与调度验收边界
- 实查private runtime Actions in_progress=0/queued=0；当前fetch在public feeds标准ubuntu-latest runner，官方规则为public标准runner不消耗私有included compute。早前private验证会计入额度，不虚构账户剩余额度。当前未新增Actions artifact/cache。不要为免费把runtime再公开。
- 截至北京时间21:57尚未取得首条event=schedule。已排查workflow active、default main、实际文件逐字匹配、owner提交且actor有效；GitHub官方允许schedule延迟/高负载掉队，不能以配置成功冒称自动抓取已验收。后续查询使用认证API，匿名API已遇到共享IP限额403，不将403当无scheduled run的证据。
- 完整新guard手动run42039962109已经通过截止护栏与两个checkout，批次仍进行；本次只有public compute，无private runner。

## 2026-11-05 22:41北京时间｜最终明确状态
免费云入口三轮workflow_dispatch已成功，生产仍Mac。完整定时首次commit3f71d14，后经disable/enable及owner原生Chrome重写cron为8/18/28/38/48/58，最新commit470a836494442145079cbdba4fe26749d6106d84。期限、10分钟间隔、固定source b9516dab、owner和private数据限制不变。经过认证API与原生GitHub Actions页面核查，尚无event=schedule记录；不能把调度配置active或三轮手动成功当自动调度验收。此项仍未完成，不停Mac，不声称完成GitHub切换。
到期前/到期后/停用API失败三条边界已在无网络stub中验过，所有private checkout均受active护栏约束。当前问题收敛到实际schedule事件未产生；不要再反复做已通过的fixture或私库配额核查。新agent先核对实际schedule事件与active/default branch/actor，若仍不触发，提交明确平台限制或受控替代触发方案，不隐瞒失败。

## 2026-11-05 23:42北京时间｜已授权签名自动接续部署
用户明确允许在feeds增加OPENFEED_RELAY_HMAC加密Secret，并允许签名通过的Actions自动接续同一私有状态。已配置独立随机HMAC密钥（非个人PAT），公开workflow提交1bccaf28d8121a520401f0cad6ef8d86679c2259；REST读取与本chat outputs/OpenFeed-cloud/runtime-cloud-signed-relay.yml逐字一致（SHA256 073c63356c733b73465d04c53643300f842e372de894de4c9c98eb74e188a604）。
- 8项签名/篡改/越权/重复generation/并行root/截止测试通过，全部inline Python编译通过。
- 每轮slot起点后600秒由GitHub自己的临时token签名dispatch下一轮；原cron作补充。queue:max+同concurrency组；私有relay-cursor持久化generation并先CAS push，防止重复/旧链覆盖。非owner/bot拒绝，bot在检出私库之前必须验HMAC。所有截止仍为2026-11-07T12:09:45Z，到期自停，不收费。
- bootstrap run42056964516已通过guard、private checkout、generation0 claim；当前抓取运行中，自动child尚待实际验收，不能以bootstrap声称无人值守已通过。原生event=schedule仍未观察到，签名relay是明确的替代触发机制，不能冒称原生cron恢复。
- Mac仍生产、publish_enabled=false。生产切换前仍需171源矩阵、两个周期、最终Mac在线备份/停写证据、原Pages地址发布验收。现有cloud_publish只push Git分支，尚须明确触发Pages build并验收HTTP；GITHUB_TOKEN推送不能默认触发Pages。
证据：本chat work/cloud-evidence/relay-{predeployment,deployment,status}.json；本地key在work/cloud-auth，禁止公开、打包、打印。

23:49实测：root42056964516抓取/checkpoint/自动dispatch全部success，自动child42058671579由github-actions[bot]发起，HMAC guard和generation1 claim通过，正在抓取。不是本机再次调用dispatch。root4源原pipeline成功，长期coverage已观察20/171；独立下载root云DB仍4194条，原4189身份零丢失，171条source_url/recipe/interval/phase逐字保持，SQLite ok。历史缓存矩阵另含单源试验：24源曾观察（20非空、3空、1 CEPR/VoxEU HTTP403），不能以branch coverage20混为已全部通过；147源未观察。矩阵只报告历史观察，未给无时间戳report按hash排序伪造最新恢复。

## 2026-11-05 23:54北京时间｜签名自动接续真实验收通过
- parent42056964516已完整success；GitHub自己的github-actions[bot]在十分钟后自动发起child42058671579，无本机再次dispatch。child的HMAC guard、generation1 claim、真实抓取、私有checkpoint都成功，checkpoint.run_id=42058671579；当前等待下一接续slot属正常。验收记录relay-acceptance.json。
- child实际4源：3成功、Cantor Insights HTTP403（历史保留、不伪装空列表）。私有branch累计coverage24/171；历史单源+批次矩阵28源曾观察（23非空成功、3原空契约观察、2失败CEPR/VoxEU与Cantor），143源尚无云观察。均非两周期长期验收。
- child状态commit54cc0c2d6006083e98b000cecfffb08dcfd28fc9已独立下载，4194条；原4189身份零丢失，171源URL/recipe/interval/phase逐字保持，SQLite integrity ok。
- 明确边界：自动relay已验证，原生event=schedule仍未观察；Mac仍唯一生产、云publish_enabled=false；未完成生产切换，不把机器人workflow_dispatch冒称原生cron成功。不启用收费，runtime保持private。既定11月7日20:09:45北京时间到期自停，未延长。
- Pages只读预检：legacy main根目录，最新build built且commit1bccaf2，原地址现状正常；这不是云RSS发布验收。生产发布前须补GITHUB_TOKEN显式Pages构建/发布并核验HTTP，完成全源/两个周期及最终Mac停写/快照。
下一步：保持单云写入者，完成剩余143源历史矩阵与两个12小时正常周期；针对403做跨环境原配方复核，不降质量；补Pages完整发布与故障恢复，最后才能单写者切换和Mac离线验收。

23:59北京时间补验：首个bot child42058671579整项workflow已success，并自行发起第二个bot child42060360129，generation2 claim已推进。已连续观察两次自动接续；第二自动轮抓取仍进行，未冒称其checkpoint完成。原生schedule仍未观察。Mac快照UTC15:56：Cantor当前error（last_success UTC11月4日17:58），CEPR/VoxEU当前healthy（last_success UTC11月5日05:41），与云403观察不同时间，不能据此断言403根因或云端已恢复。

## 2026-11-06 11:12北京时间｜实际加固与复验（覆盖昨日未观察cron状态）
- 原生event=schedule已观察两条success；自动relay仍运行。调度历史不是连续无故障：run42060360129抓取步骤失败（私密输出未持久，具体原因未知）；42061613847 claim的git push rc1；42128035866接续API两次500后失败。之后由新root恢复，不掩盖断链。
- 已部署API最多5次有限退避；403等永久错误不重试；截止前检查；claim push失败时核对remote HEAD，已被服务端接受则确认成功，其他提交变动拒绝覆盖，否则最多3次重试。12项签名/重放/截止/500恢复/403拒绝/歧义push与并发拒绝测试通过。公开首次加固3783f78，当前runtime workflow内容来自b18f0ed7，固定private app5c7a42e807083cf4993252ca9f9c5365d0989602。
- 找到迁移配置遗漏：Mac原有OPENFEED_MAX_FETCH_BYTES=8000000，云端未设置导致默认2500000。已恢复同一8MB原硬上限，未改来源URL/范围或放宽既有安全上限。owner定向复验run42152294936：Atlantic成功100条、6新增，原4个失败仍失败，私有checkpoint成功。
- 正常批量4→6，仍330秒总预算、全局60秒/同域300秒持久间隔，原phase保持。23项相关测试通过（含6源虚拟时钟/保留历史/输入不变、原SIGTERM等）。实际bot run42153367307在app5c7a42e上完成6源全部success、1新增并回写checkpoint。当前branch coverage110/171（106success、4error、61未观察），不是长期验收；还需两个正常周期。
- 剩余4源：Julius/Cantor/CEPR-VoxEU原隔离browser返回403；Man原配方云端0条。Man只读HTTP probe42153637418保存到private probe-42153637418，DB hash不变；云响应182462字节、地区/投资者提示页无文章；Mac实际HTTP321848字节、原selector提取18条。不是selector已坏，不通过cookie/身份伪装跨越提示。3源普通HTTP对照probe42154768081已发起，结果待收，不擅自改原配方。诊断ref独立，不写shadow-state或生产DB。
- 公库private-source-probe.yml是owner-only、无定时、同48h截止的只读诊断薄入口。源码/配方/DB/响应/日志都在私库，标准public runner，不产生private compute；无public artifacts。脚本最多5源、源ID参数化、固定fetch安全策略，保留真实非零退出码并先上传私密证据。
- Pages生产代码已补ops/pages_build.py并接入cloud_publish：明确请求构建、等待期望commit、拒绝错误source/旧commit/失败/超时，内容未变也能补偿上次构建失败。5项新测试包含上述路径；已用真实API只读确认当前legacy main根站点已built commitd4fa0e20。生产所需临时Pages API token及public checkout写权限尚未接入当前shadow workflow，因此不能称云RSS发布已验收。
- Mac继续生产，未停/未改；runtime保持private；截止仍北京时间11月7日20:09:45，未延长。

## 2026-11-06最终接续记录
# OpenFeed 当前实际状态｜2026-11-06

生产仍为Mac Docker卷；未停Mac、未启用云生产发布。runtime仓库private；只有公开feeds标准runner执行计算，没有启用收费。

## 已实际完成
- 自动接续已反复运行；原生schedule也已两次success：42110509165、42144750189。历史曾有3次失败，未宣称连续无故障。
- 当前runtime workflow c22524a1，固定private app9cc98c0d。Linux完整498 passed/1 warning（公开runner run42156230430，详细日志private probe分支）；另12项接续测试、24项相关源码测试通过。
- 普通批次4→6；run42153367307真实6源全success、1新增/checkpoint成功。仍330秒预算、全局60秒/同域300秒持久间隔。新队列先处理不同host，再在预算允许时等待满300秒处理同host第二项；虚拟边界已验，全量Linux通过，已部署，真实同域二次启动仍待记录。
- API500等暂态最多5次有限退避；403不重试。claim推送遇响应丢失先核对remote HEAD，拒绝覆盖别人的提交。
- Atlantic迁移配置遗漏已修复：恢复Mac原8MB上限。run42152294936真实100条、6新增。

## 当前质量与阻断
- 截至2026-11-06T03:41:43.455926+00:00，128/171源曾在branch观察：最近123成功、5失败、43未观察。这不是两周期验收。
- Julius/Cantor/CEPR原隔离browser403，普通HTTP对照42154768081也403；无可用响应，不改范围凑成功。
- Man云响应是地区/投资者提示页、无文章，Mac原selector18条；证据private probe-42153637418。
- Eurasia原China查询返回Solr搜索服务不可访问的错误页（private probe-42155403671）；不能视为官方空列表。
- 云库独立下载已验4226条、旧4189身份无损、171原scope/recipe/phase保留。实时云库仍会增加，不把旧下载叫实时。

## 发布与切换准备
- Pages显式构建/等指定commit/错源和失败超时已实现与测试；当前原地址171 RSS+OPML已HTTP校验（仍由Mac发布）。云端首次实际发布尚未验收。
- 生产接线候选文件本chat outputs/OpenFeed-cloud/runtime-cloud-production-candidate.yml已准备，包含临时public内容/Pages token接线和Mac停写/最终快照护栏，仍保留既定截止；未部署。
- 新在线Mac备份4219条，对比云下载4226：Mac独有16、云独有23、14项first_seen不同。ops/prepare_cutover.py及4项测试完成；本地合并预演4242 GUID全保留、Mac first_seen保持、冲突云时间留存私密ledger，输入库不改。171原地址RSS/OPML导出离线通过；不是最终停写快照，不可直接覆盖生产。

## 接下来
继续自动覆盖43源和两个正常周期；复核5个外部阻断；满足M3/M5后才停Mac写入、重新在线备份并合并最新两边数据，做原地址首次云发布/HTTP语义/失败恢复与Mac离线验收。截止仍北京时间2026-11-07 20:09:45，不擅自延长。

权威任务见TASKS_CLOUD.json；详证在本chat work/cloud-evidence及docs/maintenance/cloud-relay/evidence。以前CURRENT完整保存于handoffs/20261106-before-current-consolidation.md。私钥禁止打印、打包、公开。

## 2026-11-06 15:06北京时间｜全源观察与审批阻断
只读GitHub实测171源均已有观察，最近165成功/6失败；checkpoint42177907077/source9cc98c0d、身份保护通过，该轮抓取success后等待接续。仍shadow/publish=false/Mac writer未停，未完成生产切换。GitHub标准macOS对照也未恢复Man/Julius。新增发布冻结候选、推送应答丢失与Pages失败恢复及合并等本地相关31项通过，但这些新改动尚未完成本轮私库同步/新Linux完整回归，不冒用先前498项完整结果。
自动审批报workspace out of credits，新的Amundi复验调度与后续代码同步未执行；没有换工具绕过同一审批。现有云端任务仍运行，GitHub计算额度不是这次阻断。当前代码变化后的Mac快照/handoff gate尚未刷新执行，明确不宣称完整交接已通过；额度恢复后继续。

## 2026-11-06T08:08:28.159217+00:00 用户明确删除三个来源
生产权威仍为Mac，GitHub云端仍是shadow，生产切换未完成。用户明确要求删除Man、Eurasia，并在Cantor无法恢复时删除；三者在Mac API、云端shadow-state、公开OPML和RSS均已删除。当前168来源，云端覆盖166最近success、2error（Julius、CEPR），0未观察。删除不计作故障修复。

- 私有状态删除提交8960f17e3afe3cc2c9723fe833beb06ee337dcb1；公开删除提交236b0d2a3fff0f74dea43995a989fa32a432c9c2。其他来源配置/phase/GUID/first_seen集合逐项保持。完整删除前历史仅私密备份保留，禁止重建三个已删来源。
- 云端写入临时停用后已enable并owner restart；Pages预检已重新发起，结果须看实际run，不能将dispatch当完成。
- 公共Pages预检171改168，诊断默认来源Man改Julius，避免旧入口重试已删来源。
- 当前部署源码e1054f460fa20002d204704aa8554efa59fddd70，Linux完整505通过。发布失败恢复相关31项通过。此前自动审批workspace out of credits错误经用户要求重试后已恢复执行；不能推断是GPT/GitHub账单或要求充值。
- Amundi冷却后复验已恢复15条/1新增。原地址Pages/token仅现有提交预检通过，不代表云端新内容发布已验收。
- 截止仍为2026-11-07T12:09:45.802208+00:00，未延长，未启用收费。源码/数据库/配方/诊断保持private。

证据：/Users/time/Documents/Codex/2026-11-05/users-time-documents-codex-2026-10-3/work/cloud-evidence/removed-20261106/status.json、verification.json；私密mac-before.sqlite3/cloud-before.sqlite3保留完整删除前状态；cloud-after.sqlite3为删除后状态。
下一步：验收删除后实际云checkpoint/Pages；集中Julius精确/en/insights/和CEPR原China查询。开源RSSHub/RSS-Bridge代码搜索未发现对应专用实现；changedetection.io的最终主文档响应追踪可供诊断参考，但未据此证明403可修复，不引入验证码/TLS/访问控制绕过。生产切换前必须重新取168源双边快照合并；旧171源预演仅归档，不可直接部署。


## 2026-11-06T08:54:43.857375+00:00 正式切换完成、管理留本机
生产抓取/持久状态/原RSS发布已切换到GitHub。管理界面保留本机 http://127.0.0.1:8765 ，本机不自动抓取或发布。用户明确授权长期免费运行，原48小时停止时间已移除；只使用公共openfeed-feeds的标准ubuntu-latest计算，源码/SQLite/配方/日志仍在私有openfeed-runtime。未启用付费资源。

## 已实际验收
- 最终停写Mac快照ad300098edcc78a6eb3bc2eacf64bf886469ee544f1d98503a4d1c097801c62a。cloud-final dd2820ec；合并保留Mac独有2/云独有30，4102 GUID，Mac first_seen完整保留，49处cloud时间provenance私密归档。合并7391条run/4934条event；所有168源配置与phase相同。
- 私有生产状态提升5ec9f816，公开生产workflow ceebd79d，运行源码固定e1054f460fa20002d204704aa8554efa59fddd70（完整Linux505通过）。生产首轮42187231139成功，真实云发布15bb6f58316e47965bbc71c6cd6e4d894666c597，Pages built于2026-11-06T08:29:39Z；非预检空提交。
- 自动签名下一轮42188445685成功，第三轮42189658246已回写生产checkpoint。常规600秒接续+原生cron兜底；北京时间08–22每小时最多一个发布槽，无语义变化不提交。
- 公开168份RSS/OPML有效，原地址不变；原100条/源窗口4028公开GUID与最终导出一致。私库保留完整4102条，不能把RSS窗口上限之外74条误报为DB丢失。Julius/CEPR失败仍保留原RSS内容。
- 用户明确删除Man 4eb10889d95da4ae84cfe4ab1d46、Eurasia 95d1c47e63b41f814f17d344646a、Cantor 132114da2be6a7af5f9cb6f59af3：Mac/云/OPML/RSS均删除，原URL实际HTTP404；不得从旧171源预演复活。168活动源，166最近云success/2error。
- 本机仅管理：派生镜像openfeed-local-cloud-ui，ops/local_cloud_ui.py阻止本机run/batch/spread，停用原lifespan调度，保留来源编辑。同步桥ops/local_cloud_sync.py用既有health启动项保持；已拉取最新云DB，实际UI 168/4102/166healthy/2error、/api/cloud-status=synced。
- 管理修改会先等当前云批次结束，再校验配置基线、保留最新云历史并用Git快进CAS提交。桥**从不disable云workflow**，Mac关闭不会因配置等待而停云；发生版本竞争拒绝覆盖并保留本机修改。镜像恢复前停本机UI并复核配置，避免吞掉刚保存的编辑。
- 本轮28项隔离测试通过（含relay20、管理桥6、UI2）；源目录两项管理适配器共8测试通过。生产主代码仍为已验证e105，不能把新本机适配器误报为同一Linux505范围。

## 限制与剩余事项
- Julius精确/en/insights/、CEPR原China查询云端仍403；不扩大范围、不清历史、不绕验证码/TLS/访问条件。RSSHub/RSS-Bridge未检索到专用实现，changedetection.io最终主文档响应追踪仅为待验证诊断参考。
- 自动审批拒绝临时改真实来源再恢复的管理端到端测试，未执行任何测试性真实来源改动。以隔离数据验证创建/编辑/删除ID、冲突拒绝、GUID保留、重放幂等及不disable云；真实编辑->云提交链路尚未用生产编辑实测，不能宣称已验收。
- 短期生产闭环与自动接续已验收，长期可用性/所有来源两个正常周期质量不是本次即时验收可证明的。Reader账号导入由用户自行验收。
- 本机服务重载CLI受系统权限限制，已通过活动监视器正常退出旧桥进程16451；新桥PID17207在更新源码后启动，最新UI同步成功。未停止其他Python或个人VPN。

证据目录：/Users/time/Documents/Codex/2026-11-05/users-time-documents-codex-2026-10-3/work/cloud-evidence/production-cutover-20261106（final-status.json、first-cloud-publication.json、public-rss-validation.json、final-union-validation.json、production-state-receipt.json、完整私密快照与provenance）。已删除来源备份在同级removed-20261106。

回滚：先停云runtime workflow并等当前工作完成，取得**最新**云DB/配置/历史；写入本机后再恢复scheduler/publisher。不能恢复旧Mac快照覆盖新云历史。原compose/publisher脚本保存在证据目录*.before；先移除cloud-production.json门闩才能恢复本机发布，严禁双发布者。
下一步：独立处理两源403；观察12h正常周期质量、发布新鲜度及管理编辑实际使用反馈。不要再把主迁移当未部署重新做。


费用保护收尾：停用未使用的私库Cloud regression and state integrity；复核三个私库workflow全部disabled_manually，公共生产入口保持active。证据：outputs/OpenFeed-cloud/上线验收-20261106.json。

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


## 2026-11-15T11:40:10+00:00 第10轮·访问受阻页识别扩充（源码合并，未部署）
- 背景：rssweball 剩余问题订阅全量复核（60 条重测）实证多类 200 状态阻断页无法与空结果区分，交给本仓库做一项精准改动。
- 修改：openfeed/access_barriers.py 新增 access_denied（Akamai Edgesuite“you don't have permission to access”/ CloudFront“The request could not be satisfied”，均需显式标题 + 特征句双证据）与 waf（Aliyun WAF 指纹 + aliyun≥5；Akamai/OpenEdge“The requested URL was rejected” 且整页 < 5000 B）；Vercel Security Checkpoint 与 Cloudflare“Attention Required”纳入 challenge；challenge/captcha/login_wall 行为不变。护栏不变：页面 ≤ 300,000 B、去脚本后可见文本 ≤ 2000、无 ≥ 250 字真实 article。
- 测试：tests/test_access_barriers.py 增加 13 项（生产形状正例 + 长文/内容页/空结果页负例）；full suite 525 passed，仅 2 个浏览器（Chromium 未装）失败，与Linux 524基线等价；专项 25/25。
- 真实验证：40+ 份平台抓取逐一过签名函数——阻断页全分类正确，内容页零误判；详见 CURRENT 2026-11-15T11:40:10+00:00 段落。
- 门禁：sandbox 无法刷新 latest-snapshot.json（无 127.0.0.1:8765 管理服务与令牌），check_handoff 预计 FAIL（快照过期 + 指纹不符），未伪造快照；请用户本机复核。合并 main ≠ 生产部署：生产 Actions pin 不变，新签名随下次发布生效。
- 未做：未动 workflow/pin/DB/调度/来源/GUID/发布地址/RSS；未部署；Scholar/nginx 页维持原分类；docs 目录前置损坏测试未擅动。

