# 出站代理安全审计与验证（2026-10-21）

## 本轮已实现

- 对 HTTP 代理的普通 GET/HEAD 请求实施严格单行 Header 校验；拒绝畸形字段名、折行、控制字符以及超量 Header。
- 丢弃来自客户端的 Host、Content-Length、Transfer-Encoding、Connection、Upgrade、TE、Trailer、Expect、Proxy-Authorization 等影响路由、消息边界或代理授权的字段；代理重新生成目标 Host 和 Connection: close。
- 保留正常的 Accept、User-Agent 与自定义追踪头。
- 普通 GET/HEAD 不再转发请求头之后的额外客户端字节，阻止意外的第二个上游请求；修正无其他 Header 时的换行终止符。
- 新增真正通过 localhost TCP 流连接模拟上游的代理集成测试，不需要外网即可验证源站收到的请求头。

## 本轮可复验结果

`PYTHONPATH=. pytest -q`：123 passed；Python 编译和项目 JS 语法检查通过。

## 尚未通过的发布门槛

1. 当前容器无 Docker 命令，不能声称 `compose.browser.yaml` 的实际网络隔离已通过运行验收。
2. 真实外网金融站点周期性抓取尚需可用 DNS/网络环境和站点访问授权。
3. 完整 Chrome/Edge MV3 扩展安装及 Service Worker 验收尚未通过。
4. Reader 云端真实订阅需要可公开访问的 RSS 地址与实际订阅测试。
5. 仍需对代理实现做独立安全评审、资源滥用与压力测试；本轮的协议加固不代表获得正式安全认证。
