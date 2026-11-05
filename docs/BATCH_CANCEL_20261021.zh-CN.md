# OpenFeed Studio 批次取消功能

## 已完成
- `BatchJobs.cancel()` 将 pending/running/interrupted 持久化转换为 cancelled。
- cancelled 状态不能 claim、resume 或继续写入批次进度。
- 管理 API `POST /api/feeds/batch-jobs/{job_id}/cancel` 有管理员鉴权，404/409 行为明确。
- UI 展示 Cancel batch，关闭进度监控并清除浏览器保存的批次 ID。
- 添加数据库重启与 HTTP 接口专项测试。

## 边界
取消属于**停止后续批次调度和进度记账**，不保证正在进行的单条上游 HTTP 抓取立即中断。
生产环境仍须验证 Docker 网络隔离、Chrome MV3 实际加载和外部金融机构抓取及 Readwise 订阅。
