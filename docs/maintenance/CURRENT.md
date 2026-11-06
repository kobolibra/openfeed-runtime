# 当前运行：已切换GitHub云端生产（2026-11-06T08:54:43.857375+00:00）

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

费用保护复核：私库三个Actions入口现全部disabled_manually（包含旧手动regression），生产及后续必要回归均使用已批准的公开标准runner；此前旧私库历史运行不作账单返还承诺。
