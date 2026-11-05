# 持久化批量刷新队列：实现与运行约束

## 已实现
- `POST /api/feeds/batch-jobs` 创建后台作业（最多 30 个 Feed）。要求管理员令牌；任何 Feed ID 无效时整体拒绝。
- `GET /api/feeds/batch-jobs/{id}` 返回进度、按请求顺序记录的逐源结果。
- `POST /api/feeds/batch-jobs/{id}/resume` 仅允许恢复 `interrupted` 作业。
- SQLite 持久化 `batch_jobs`，每处理完一个来源事务式保存进度；服务重启把原 `running` 任务标为 `interrupted`，由管理员决定是否继续。
- 服务生命周期内运行队列消费者，队列执行复用 `run_feed` 原有来源锁、域名访问间隔及内容校验。管理界面创建作业后轮询进度，页面刷新后从 `sessionStorage` 找回作业 ID。

## 已验证
- `tests/test_batch_jobs_durable.py` 覆盖重启恢复、重复进度拒绝、失败隔离、认证、API 进度和非法恢复。
- 全套单元/集成回归通过，前端 JavaScript 语法校验通过。

## 尚未宣称完成
- 单实例设计，不能运行多个 API/调度副本；多个进程同时消费同一队列不是受支持配置。
- 作业目前串行执行；适合降低域名压力，但大量慢源完成耗时较长。需要在性能实测后设计有限并发与公平性。
- 旧同步 `/api/feeds/bulk-refresh` 仍保留兼容性，管理界面已改用新的持久化接口。
- 进程异常退出可能发生来源抓取成功、但进度结果尚未保存的短暂窗口；恢复时可能重复执行该来源，依赖现有 GUID 去重，而非严格 exactly-once HTTP 抓取保证。
- 未做多日真实站点、Docker 多容器与 Reader 公网集成验收。
