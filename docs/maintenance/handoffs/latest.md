# M1接续交接
维护者：接手agent，2026-11-05 Asia/Shanghai
部署状态：未部署；Mac Stage19仍为生产，未发布或启用云调度。
验证：八项shadow专项通过；完整最终469通过/6失败/1警告，六项均Chromium宿主启动权限拒绝；不宣称完整回归通过。393文件交接manifest一致；M1 ZIP CRC无误。Brookings旧响应复演4条/3新增，输入不变，历史身份及相位校验见work/m1-continuation/preservation.json。最新快照见latest-snapshot.json。
未完成：M1仍in_progress；真实隔离browser、进程硬中断/重启、recipe变化与deadline边界、M2原子checkpoint与单写者；M3-M6尚未完成。短批次保守启动间隔影响容量，留M4测量，不放宽既定约束。
下一步：在可启动Chromium环境复跑六项，并补M1剩余验收；不要重复一次性远端连通性诊断。以前轮shadow.sqlite3为输入可串联节流，禁止当生产权威持久化方案；从旧基线分叉不共享锁。
改动：ops/run_cycle.py、tests/test_shadow_cycle.py及维护记录；输出清单是RSS字节SHA256，非语义清单，后续M5补语义差异发布。
证据：source/work/m1-continuation；没有临时生产写入者，测试已结束。回滚：仅回退上述开发代码，生产无需回滚。
