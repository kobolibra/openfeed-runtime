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
