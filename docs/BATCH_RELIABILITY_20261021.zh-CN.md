# 批量作业调度与恢复专项审计（2026-10-21）

## 修复

- **服务正常关闭时取消作业**：先前 `process_batch` 取消后维持 `running` 状态，只有再次初始化数据库才会标记 `interrupted`。现在在 `finally` 调用 `interrupt()`，即使未重启也可以显式恢复，保留已完成项目。
- **批次饥饿问题**：先前队列一次执行完所有来源，长批次会阻塞后续批次。调度循环现采用每批次每轮至多执行一条来源、未完成时 `yield_pending()` 重新排队。单独调用 `process_batch(job_id)` 仍保留执行整个批次的行为。
- 两项都有异步数据库测试，验证取消后恢复、处理位置保留和队列公平性。

## 注意

- 单进程队列，不是多实例分布式协调系统；不能部署多个未经协调的 API 实例。
- 故障恢复是“至少一次任务尝试”的语义；文章 GUID 去重不等于真实网络请求恰好执行一次。
- 浏览器 Worker 容器隔离、金融机构外网实测、完整 Chrome 扩展安装、Reader 云端订阅，以及 Docker 实际构建仍未通过生产验收。

## 复现

```bash
cd openfeed-working
PYTHONPATH=. python -m pytest -q
python -m compileall -q openfeed
```
