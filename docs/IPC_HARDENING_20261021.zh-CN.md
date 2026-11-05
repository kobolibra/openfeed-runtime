# Browser IPC reliability and input validation (2026-10-21)

## 实际完成
- 严格限制 worker 任务必须是 JSON object，并只接受 `id,url,wait_selector,submitted_at` 四字段。
- 对 URL/selector 的类型、时间戳有限数值条件进行校验；拒绝 NaN/Infinity/布尔值等异常时间戳。
- Worker 队列巡检不跟随符号链接；过期结果文件清理避免追踪符号链接。
- API 对来自独立浏览器 Worker 的响应字段、Base64 体积、错误数据类型进行校验，在读取和解码前施加边界。
- 新增请求/响应专项回归和真实异步文件任务注入测试，确认无效响应拒绝且临时文件清理。

## 安全范围
以上仅证明当前文件 IPC 协议在测试覆盖边界的校验行为。**没有**证明共享目录能抵抗同 UID 恶意进程，也没有证明 Docker 网络隔离部署或 Chrome 插件安装。完整运行前仍需在 Docker 环境验证：用户/目录权限、浏览器容器只接入 internal 网络、代理只能出站公网、资源限制、重启与恢复。

## 验证命令
`PYTHONPATH=. python -m pytest -q`

## 仍需独立环境验收
真实公网目标持续抓取、Docker Compose 浏览器隔离、Chrome MV3 扩展安装与消息链路、Reader 云端订阅。不可把本地模拟响应当作真实网站成功。
