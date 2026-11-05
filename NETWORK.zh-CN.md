# 本机独立抓取出口（2026-11-03 核查）

当前 Mac 本地栈的 API 与隔离浏览器均通过专用宿主代理访问公网；宿主代理只监听 `127.0.0.1:8900`，连接绑定物理接口 `en0`，不读取个人 VPN 的端口、账号或配置。浏览器仍在 Docker 内部网络，通过公共地址校验代理出站；TLS 校验及私网、元数据阻断保持开启。

当前宿主配置为 `OPENFEED_DIRECT_INTERFACE=en0`、`OPENFEED_PHYSICAL_DNS=encrypted`。加密解析固定连接 AliDNS 引导地址，验证 `dns.alidns.com` TLS 证书；验证返回问题、别名链、公开 IPv4 地址和 TTL。仅 CNAME 的 SERVFAIL 可尝试 DHCP 别名提示；地址仍需加密解析并由原站 HTTPS 主机名验证证书。不会退回个人代理，也不会固定写死网站 IP。宿主依赖见 `requirements-host-egress.txt`。

`OPENFEED_PHYSICAL_DNS=dhcp` 是未设置时的实现默认值，当前 Mac 已显式使用 `encrypted`。`OPENFEED_DNS_MODE=auto` 适用于未配置专用物理出口的通用部署，不等于当前 Mac 的实际解析链路。物理接口方案目前限 macOS、物理 en 接口与 IPv4；不是跨平台通用方案。

独立出口避免依赖某一款个人 VPN，但**不能保证底层网络对所有域名可达**。物理路由、系统网络过滤器、目标网站访问限制仍可能影响连接。没有执行用户 VPN 开/关对照验收，不能声称已经完全验证无影响；本轮没有更改用户 VPN 或系统网络设置。

2026-11-03 独立物理接口测试中，AQR 的 TCP 连接超时，Capital Economics 与 Brookings 的 TLS 连接被重置；DNS 单独解析约 0.38–1.34 秒。因此不能把这些失败简单归为 CSS 规则失效、空列表或 DNS 慢，更不能未经证明归因于个人 VPN。需要独立于本机网络的抓取能力时，应使用稳定的远端抓取运行环境；GitHub Pages 只托管 RSS，不负责抓取。

出口为 DNS 等待和连接过程设置总上限；日志只记主机、阶段、耗时及错误，不记 URL 查询或账号信息。CONNECT 成功后失败直接关闭隧道，禁止注入明文 HTTP 错误。DHCP 查询超时作为可处理网络错误返回。`ops/runtime_health.py` 的端口探测仅说明进程在监听，不代表全部目标网站可达。

HTTP 403/405/429、浏览器进程失败、出口 502/504、选择器等待失败分别记录。错误不会清空历史 RSS。浏览器容器启用 init 回收子进程，避免 Chromium 僵尸进程耗尽进程上限。网站限流应尊重 Retry-After；不绕过验证或登录限制。
