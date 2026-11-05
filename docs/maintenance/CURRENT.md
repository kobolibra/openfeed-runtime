# 当前接手状态｜2026-11-05｜Stage19

**本轮首要任务：完整迁移规划与真实资料交接。下一位从CLOUD_HANDOFF.md / TASKS_CLOUD.json的M1继续，不重读整段聊天。** 用户希望以GitHub长期承担核心运行，尚未实施生产迁移。

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
