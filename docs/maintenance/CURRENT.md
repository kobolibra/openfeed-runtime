# 当前接手状态｜2026-11-05｜Stage19

**最新：GitHub私有源码、私密影子状态和三类代表源云端运行已落地；Mac仍为生产。以TASKS_CLOUD.json及本页末尾最新进展为准。**

## 当前生产与最新证据

- 权威运行仍为Mac Docker SQLite；本地调度/发布没有停。源码真实目录work/local-trial/source，当前API/出口Stage19。
- 本轮私密在线备份UTC04:28:06Z：171源、4189历史条目、151正常/20错误，integrity_check=ok；ID/GUID/phase与DB校验和见private-state/state-baseline.json。之后服务可能变化，以latest-snapshot时间为准。
- Stage19最新代码完整466项回归通过；171RSS XML/GUID/ETag检查通过。日志/备份基线不是云端验收。
- 已部署：Stage14 GET即时有限重试；Stage15同主机持久化冷却；Stage17延迟恢复/HTTP总时限；Stage19共享连接预算、多地址公平回退及DNS/TCP错误阶段。未完成全任务/分页/browser统一deadline、自动现场归档、长期成功率指标、会话池、云权威状态。

## 不要重复的诊断

Brookings远端run41965774214：200/0.122秒，原规则4条有效；本地TCP失败。一次20源run41966397327远端全200、17首屏内容通过。捕获正文已下载，不必重跑。
本地Woodmac/世界银行/道富3项原HTTP内容已通过；两猎聘browser不能用curl替代；Eurasia远端200仍0内容；Woodmac3页只测第一页。不同TLS/curl平台，不能证明所有差异纯属路由。
猎聘12155477、8224343本地browser缺预期left-list区域；未达到70请求上限，一个访问captcha初始化API，不绕过。下一位读现场，不猜它们必须迁远端。

## 已准备的接手资料

本轮私密包包含真实源码、在线DB、完整配方、状态hash、精选测试/两地响应证据、运行模板、调研资料和可执行完整性校验。包有时间戳，同机不要覆盖更新工程。详情RESOURCE_INDEX。
AGENTS、CLOUD_HANDOFF、TASKS_CLOUD和问题台账是持续维护入口；新agent每轮必须维护它们。

## 下一项及边界

M1先实现scratch库上无副作用单轮runner，后续M2私密状态/M3影子运行/M4成本容量/M5原地址发布/M6单写入者切换。不能先对所有源开新cron。
保持ID/GUID/原范围/12小时错峰/北京时间08–22发布，公开仓库不放应用源码或DB；费用、私有repo及认证尚未配置。Actions不提供常驻FastAPI管理后台。未经验收不停止Mac；最终切换还要处理health自动重启旧scheduler的风险。

## 验证边界

本轮没有变更抓取逻辑/部署，只增加交接材料和工具校验要求。不重复466项测试；包文件/SQL基线及门禁的实际结果见handoffs/latest。若包/门禁未通过，不宣称交接完成。

## 2026-11-05 M1继续实施
已新增ops/run_cycle.py：默认plan，fresh output内SQLite online snapshot，调用原run_feed并输出私密RSS，无生产写入/发布。fixtures模式按精确URL+POST body匹配，无live fallback；shadow-live需显式选用，目前未执行。每次只处理同host一个，限制数量/运行预算，不是最终批吞吐方案。
Brookings已捕获页面离线复演：4条、3条新增，原4189GUID零丢失、ID/相位不变，输入DB hash相同。四项专项通过；完整回归第一次根cwd4项路径失败，正从source cwd重跑，保留原日志。M1仍in_progress，未部署/未云端执行，不可把它标done。证据work/m1。

M1最终验证：source cwd完整470通过、1第三方警告。首次根cwd4项路径失败不是代码修复，不删除日志。最新API快照UTC08:06:26Z：148正常/23错误，非本轮全源复验。生产仍Stage19；M1代码只在开发源与影子副本，未部署。

## 2026-11-05 M1接续检查点
- 接手核对：完整包393清单文件SHA256全匹配；M1包ZIP CRC通过。以同机源码继续，未用ZIP覆盖工程。
- 新增：实际selected/deferred原因、RSS字节校验manifest、下一计划/恢复/冷却状态；shadow_cycle_starts持久60秒全局/300秒同域启动间隔，串联下一批副本可保留节流。每次仍全新输出；不是生产checkpoint。
- 八项专项通过：三页合成POST/重复执行GUID与first_seen保护、browser精确wait_selector替身、分页0.1秒取消保留历史，以及原四项与同域报告。真实隔离浏览器/猎聘未验收。
- 最终完整回归469通过、6失败、1警告；失败全部为当前宿主Chromium启动权限拒绝（mach bootstrap/Crashpad），未删除或跳过测试。不能沿用上轮470通过作为本轮全绿证据。
- Brookings旧捕获响应复演4条/副本新增3，输入hash未变；无live抓取或发布。证据source/work/m1-continuation。生产仍Stage19 Mac；M1保持in_progress。
- 下一步：具备Chromium启动权限的环境复跑6项；补真实browser、进程SIGTERM/硬中断恢复、规则变更与deadline边界；持续状态单写者与原子checkpoint在M2。默认间隔保守、无等待，短周期通常仅启动一源，容量需M4验证。

## 2026-11-05 GitHub切换实际推进
- 用户纠正私库事实：kobolibra/openfeed-runtime已存在。实测private/admin/push成立；核对当时仅README。已导入224个源码文件与shadow-state私密基线，GitHub连接后创建cloud-shadow工作流。
- 三类真实云端run均成功回写checkpoint：Brookings4条/3新增；Woodmac原3页9条/0新增；隔离浏览器Value Partners100条/0新增（触及提取上限，非无限范围完整性验收）。未发布。
- 实际下载云库核验：原4189 GUID+first_seen身份零丢失、171源相位保留，当前4192条，integrity_check ok。不是最后切换数据库。
- Linux完整回归首轮474通过/1失败，缺dnspython固定依赖；已加入requirements-host-egress.txt重跑，最终结果另记。不跳过测试。
- 新增有限批次tick（4源/330秒）、跨批启动间隔、候选DB hash校验、171行逐源覆盖记录；11项相关专项通过。源码私库main 9afb4c1。
- 原地址发布准备：数据库在线副本直接导出RSS/OPML，失败保留旧内容、白名单、字节及语义hash；2项专项通过，尚未部署到公共发布。
- 免费长期方案：公开仓库只运行通用薄工作流，源码/状态/配方/日志仍私密；文件ops/public-wrapper.yml已备好。因旧约束仅静态/诊断workflow，已向用户询问明确允许新增运行workflow，答复前不部署该公开入口。尚未启用云schedule或收费，Mac未停。
- 新证据在本chat工作区work/cloud-evidence；源码内备份work/cloud-switch。下一步先确认Linux完整回归，再按用户选择配置有限影子持续调度和171源矩阵，不能宣称切换完成。

### 后续实测
- Linux run42007778140在源码9afb4c1完整477 passed/1 warning，171RSS/GUID及私有DB不变性检查全通过。
- run42008521595多源tick实际处理4个到期来源全部success，新增2条，历史/phase门禁与私有checkpoint通过。不是全171源验收。
- 新增SIGTERM分页中断/重启验收及数据库导出专项后，本地相关14 passed；这些新增项尚未包含在上述477计数。
- 猎聘上海公司浏览器真实云任务已dispatch，结果待收；不绕验证、不替换推荐职位。

## 2026-11-05可见性变化（优先于上文私库描述）
用户告知将仓库改public。匿名GitHub API实测openfeed-runtime private=false/visibility=public，openfeed-feeds仍public。runtime的shadow-state含SQLite/配方；已暂停私密上传和新云任务，不擅自改变用户刚设的可见性。已询问是否恢复runtime私有并继续已授权feeds薄工作流，或保留代码公开、另迁私密状态并处理公开历史。答复前不可继续把私密数据库推到公开仓库。
- 用户此前已明确允许公开feeds薄工作流免费方案，授权仍有效；这不等于明确允许SQLite/配方公开。
- 新发布接线保存在本机ops/cloud_publish.py、cloud_tick.py，16项相关测试通过，尚未部署；公开薄工作流与最小权限Secret脚本均准备好，未上传新密钥。

## 2026-11-05恢复私有及免费入口落地（覆盖上文阻断状态）
- 用户明确选择恢复私有并继续免费方案，且亲自改回private。已用认证API确认private=true、匿名404。
- repo级deploy key 168864386已配置到runtime；公库Secret OPENFEED_RUNTIME_KEY为加密私钥，不是个人PAT。原cloud-shadow/cloud-batch写入workflow已disabled；单一公库concurrency组继续，Mac生产不变。
- shadow-state/runtime-control.json：shadow/publish_enabled=false，截止UTC2026-11-07T12:09:45.802208Z（北京时间11月7日20:09:45）；不启用生产发布。
- 私库main b9516dab已包含固定入口、期限护栏和发布保护，16项专项通过。公库runtime-cloud.yml已成功部署（ca6155d），固定源码b9516dab，首轮免费run42025905503成功。第二轮手动run42034400400已在执行。
- 定时尚未启用：GitHub工具持续transport失败。自动审批曾拒绝未验证脚本版本及缺少workflow自动停用的版本，均未部署；完整含期限/到期先disable再禁checkout的版本已备好，但提交仍遭连接工具故障。已请求用户在GitHub编辑页提交本chat outputs/OpenFeed-cloud/runtime-cloud-48h.yml，不要求聊天明文token。不得把手动成功写成cron已开。
- 恢复后云库下载校验遇到代理响应incomplete chunked read，正在用有限GET重试与新连接补核；未把截断数据保存成成功证据。此前已证4194条/4189身份无损，首轮免费后最新条数待验。

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
