# M1影子运行原型交接
时间：2026-11-05 Asia/Shanghai
维护者：当前对话agent
部署状态：新增ops/run_cycle.py未部署；Mac生产Stage19未变，未启用GitHub持续任务。
验证：完整470项回归通过；首次根cwd4项路径失败已保留，并从source cwd重跑通过。四项shadow专项：计划/拒绝覆盖/缺fixture不回退网络/429仅写副本。Brookings离线捕获页原pipeline4条、3条影子新增，原4189GUID无损、ID/相位保留、输入hash不变。
未完成：M1仍in_progress。POST完整分页、browser、取消中断/重入、跨批次同域节流和可持续状态等未完成；M2-M6未实现。影子runner每次全新副本，不能当生产权威runner。
下一步：读取CLOUD_HANDOFF/TASKS_CLOUD，继续M1剩余验收；不要重做已完成远端对照。原完整M0包为检查点；最新源码与本轮增量包优先，旧包不能盖新源。
运行中任务：本轮测试均结束，无临时抓取进程；Mac既有生产调度继续。
证据：work/m1（影子SQLite与report、preservation、tests/full-tests-source日志）；本轮输出OpenFeed-M1影子运行-20261105。
最新快照：UTC08:06:26Z为148正常/23错误/0暂停；不代表本轮复验全源，也不把数量变化归因M1（未部署）。
