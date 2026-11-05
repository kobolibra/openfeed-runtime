# 出站代理目标 URL 安全审计（2026-10-21）

## 本轮修复

对 HTTP absolute-form 目标先做严格的 `validate_http_target()` 校验，再进行 DNS 与网络连接。拒绝 URL userinfo（账户密码）、片段标识、反斜杠、控制字符、非 ASCII 原始目标、百分号编码换行/NUL、非法端口及非公网地址。不再在未经完整校验目标和转发 Header 之前拨号。

新测试 `tests/test_egress_target_hardening.py` 覆盖不安全目标、正常查询 URL 与此前存在的协议层回归测试。当前本地全套自动化结果为 **134 通过**。

## 仍未验收

这不是整个代理的生产安全认证。仍需 Docker 构建、Chrome/Chromium 容器、实际网络隔离、DNS 重绑定模拟、并发/资源压力、完整 MV3 安装、真实金融网站多轮获取和 Readwise Reader 云端订阅。该源码不能仅凭测试数字宣称生产可用。
