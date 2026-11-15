## 2026-11-15T11:40:10+00:00 第10轮·访问受阻阻断页识别扩充（代码已合并进 main，未部署）
本轮为代码级优化，非生产部署事件。改动仅限 openfeed/access_barriers.py 与 tests/test_access_barriers.py（+13 项实测签名/负例回归）；未改 workflow、Actions pin、数据库、来源配置、调度相位、RSS/OPML 地址。生产仍固定运行用户私有流程 pin 的源码（CLOUD 系列记录中的 pin），新签名要等用户按既有发布流程 pin 新 SHA 后才对云端生效。
- 动机：对已交付 rssweball 清单的全量剩余复核（2026-11-15 19:18 北京时间，60 条问题行全部重测）实证：Cloudflare“Attention Required”家族、Akamai Edgesuite“Access Denied / you don't have permission to access”、CloudFront“The request could not be satisfied”、Vercel Security Checkpoint、Aliyun WAF（meta aliyun_waf_aa）、Akamai“The requested URL was rejected”等 200 状态阻断页，此前全部落入通用“提取 0 条”失败，无法与内容空结果区分。
- 实现与护栏：扩展 reject_access_page，增加 access_denied 与 waf 两类 kind（challenge/captcha/login_wall 行为不变）；所有签名继续受既有强护栏约束——页面 ≤ 300,000 B、去脚本样式后可见文本 ≤ 2000 字、无 ≥ 250 字真实 article；Akamai/CloudFront/URL-rejected 均要求显式标题 + 特征句双证据；Aliyun 无稳定标题，只认 WAF 指纹（aliyun_waf_aa / --aliyun-zoom-ratio / aliyun_waf）且 aliyun 字样 ≥ 5 次；URL-rejected 还要求整页 < 5000 B。这些组合在真实文章页中不会出现。
- 真实抓取验证：将 2026-11-15 平台实际抓取的 40+ 份页面逐一过新签名函数——阻断页全部正确分类（challenge 16 份、access_denied 6 份、waf 5 份）；内容页零误判（Schroders SSR 230,798 B 列表、Hudson 107,302 B 职位卡、Workday 1,568,419 B、Broadridge 408,156 B 空结果页、BridgeWater 13,623 B、Bestblogs 229,945 B 登录骨架、Franklin 156,299 B React 壳）。Scholar 验证页（origin-trial 证据不足）与 nginx 5xx 壳页有意不收录，维持原分类，避免误伤讨论这些错误的真实文章。
- 验证：python3 -m pytest tests/ → 525 passed；2 failed 仅为 tests/test_live_picker_end_to_end.py 与 tests/test_picker_to_rss_full.py（Chromium 未安装，与改动无关）；4 skipped；access_barriers 专项 25/25。Linux 生产基线为 524，本轮等价（改动只增不改既有行为）。
- 门禁缺口（如实记录，未伪造）：本会话 sandbox 无法访问本机管理镜像 127.0.0.1:8765 与 .openfeed-local 管理令牌，docs/maintenance/latest-snapshot.json 无法刷新（仍为 2026-11-06T16:46:31Z，> 24h 且 source_sha256 与当前工作树不符）。tools/check_handoff.py 预计 FAIL 两项（快照过期、源码指纹不符），交接不得宣称完成；需用户本机服务在线时运行 python tools/maintenance_snapshot.py && python tools/check_handoff.py 复核，并确认生产 pin 的 SHA 是否切换。
- 观察项：docs/maintenance/optimization-20261106/test_environment_clock.py 存在前置损坏导入（from production_relay_logic import claim；该模块不在仓库中），任何环境下都会导入失败，与本次改动无关；建议用户在有权限的机器上单独核对该交付物，超出本轮范围，未擅改。

证据：/home/user/rssweball_audit/probe_r10_*.bin（平台 2026-11-15 实战抓取，40+ 份）；openfeed/access_barriers.py；tests/test_access_barriers.py。


## 2026-11-06T16:46:30.154354+00:00 用户要求20分钟试运行（当前有效）
现有openfeed-publication-interval环境wait_timer已从10改20，并独立GET验证20。没有修改workflow、应用pin、数据库、每轮6源上限、来源12小时相位或RSS地址；等待仍不分配运行机。原生cron每小时兜底保持。已有等待轮可能仍使用进入时的旧计时，后续新等待按20分钟；完整20分钟自动接续效果尚待正常运行观察，不能仅凭配置读回声称完整新周期已验收。原脚本/工作流内10分钟为最低防风暴门槛，实际等待由环境20控制；以后维护不得用旧prepare_environment脚本或旧10分钟记录恢复环境。理论每日约72轮，实际受队列与启动开销影响；关注积压、429重试及源新鲜度，不能承诺432理论容量就是实际吞吐。回滚仅将同一环境wait_timer恢复10，不回滚任何DB。
证据：/Users/time/Documents/Codex/2026-11-05/users-time-documents-codex-2026-10-3/work/interval-20m-20261107/environment-before.json、environment-after.json。

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
