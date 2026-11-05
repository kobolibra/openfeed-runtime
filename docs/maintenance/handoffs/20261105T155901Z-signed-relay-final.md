# 签名自动接续已实跑，生产切换未完成
维护者：当前agent，2026-11-05
部署状态：public feeds workflow commit1bccaf28d8121a520401f0cad6ef8d86679c2259逐字核对，固定private app b9516dab；OPENFEED_RELAY_HMAC已按用户明确授权加密配置。runtime private；旧private写workflow disabled。Mac仍生产、云shadow/publish_enabled=false，没有收费资源。
验证：8项签名/篡改/越权/重复generation/并行root/截止专项通过；全部inline Python编译。parent42056964516完整success，十分钟后由github-actions[bot]自动发起child42058671579。child HMAC guard、generation1 claim、实际抓取、private checkpoint真实通过，非本机重复dispatch。child4源3成功、Cantor HTTP403，历史保留。child DB commit54cc0c2d6006083e98b000cecfffb08dcfd28fc9独立下载4194条，旧4189身份无损/171 source_url、recipe、interval、phase完整保留/SQLite ok。
未完成：原生event=schedule仍未观察，不把bot workflow_dispatch冒称cron。生产切换未完成。branch coverage24/171；合并单源历史矩阵28观察（23非空、3空、2 HTTP403），143未观察；不是长期通过。两12小时周期、Pages云发布/HTTP和故障恢复、最终Mac停写与在线备份、离线验收均未完成。Mac当前快照只是运行观察，不等于逐源验收。
下一步：让已验证自动relay继续有限影子覆盖143源与两个周期；复核CEPR/VoxEU和Cantor403，不降质量或清历史。补生产发布显式Pages build/deploy（GITHUB_TOKEN推送不自动触发Pages），校验原地址。满足门禁后才最终Mac在线备份、单写者切换与回滚演练。
期限：北京时间2026-11-07 20:09:45固定，到期自停，不擅自延长；间隔600秒、queue:max、同一并发组+私有cursor防旧链重放。当前child抓取完成后等待下一slot是正常现象。
授权：用户明确“允许，直接部署并验收”，专指新增HMAC Secret与签名自动接续，保持既定48h、单写入者、不收费。不要重复询问相同授权，也不要把它解释成允许提前停Mac。
证据：本chat work/cloud-evidence/relay-acceptance.json、relay-deployment.json、state-verification.json、cloud-validation-matrix.json；source docs/maintenance/cloud-relay内代码/测试/已脱敏证据，ops/public-wrapper.yml是实际部署文件。所有本地密钥在本chat work/cloud-auth，禁止公开、打印、打包。源private main文档更新不会改变公开workflow固定的b9516dab。
回滚：停用feeds runtime-cloud.yml即可停止relay；保留Mac生产。不用影子库覆盖Mac。

23:59北京时间补验：首个bot child42058671579整项workflow已success，并自行发起第二个bot child42060360129，generation2 claim已推进。已连续观察两次自动接续；第二自动轮抓取仍进行，未冒称其checkpoint完成。原生schedule仍未观察。Mac快照UTC15:56：Cantor当前error（last_success UTC11月4日17:58），CEPR/VoxEU当前healthy（last_success UTC11月5日05:41），与云403观察不同时间，不能据此断言403根因或云端已恢复。
