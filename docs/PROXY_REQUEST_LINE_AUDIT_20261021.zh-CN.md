# HTTP 出站代理请求行加固（2026-10-21）

## 变更

- `openfeed/egress_proxy.py` 新增 `validate_request_line`，要求 GET/HEAD/CONNECT 使用唯一 ASCII 空格分隔，严格的 HTTP/1.0 或 HTTP/1.1 版本，禁止请求目标包含控制字符及任意空白。
- 对 CONNECT 请求也运行 `safe_forward_headers` 验证。虽然这些字段不向 TLS 上游转发，非法字段仍会在连接前被拒绝。
- 新增 `tests/test_proxy_request_line.py`，覆盖不规范空白、控制字符、非法 HTTP 版本、方法、CONNECT 头部折行和正确请求。

## 验证

- `PYTHONPATH=. pytest -q`: 144 passed。
- 本测试是应用层协议与离线自动化验证，并**不**代表 Docker 真实网络隔离或公网安全审计通过。

## 仍需生产验收

- Docker 构建、内部网络无法直连公网与内网的实际验证。
- 浏览器扩展完整安装；金融网站多轮实时抓取；Readwise Reader 云端订阅。

## 同轮追加：Worker 强制使用专用内部代理

`openfeed/sandbox_worker.py` 新增 `validate_internal_proxy`，只允许 `http://egress-proxy:8899`，拒绝外部/本机代理、附带用户信息、查询参数等变种。新增 `tests/test_browser_proxy_destination.py`。这属于应用层误配置防护，不能替代 Docker 运行期网络隔离验证。

合并后的回归结果：`154 passed`。
