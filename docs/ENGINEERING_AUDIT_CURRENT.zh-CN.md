# OpenFeed Studio：本次集中工程审计与验收边界

日期：2026-10-21；基线：v0.9（不因版本号而宣布完成）。

## 已执行且得到证据的工作
- 逐文件检查 Python API、网络抓取、实验性浏览器、浏览器扩展（Manifest v3）、Compose 和 Dockerfile。
- 增加双重浏览器安全闸门：`OPENFEED_EXPERIMENTAL_BROWSER=1` 和 `OPENFEED_BROWSER_NETWORK_ISOLATED=1`，缺一则拒绝启动浏览器。**后一配置只是一项声明，不会自动建立网络隔离**；必须由部署者先用 OS / container egress 网络策略实际落实。现有 Compose 强制关闭两项，所以默认部署不会启动实验浏览器。
- 增加独立、只读来源审计器 `tools/audit_sources.py`，读取 `tools/pilot-sources.csv`（20 个用户提供的代表性来源），对每个源保存网络、原生 Feed 发现、可选文章规则、候选提取数量、日期异常和失败详情；不自动修改/创建正式 Feed。
- 新增 4 项回归测试（浏览器两项 + 来源审计两项），69/69 测试通过。
- 尝试用 xvfb + 系统 Chromium 加载 Manifest V3 扩展，启动过程超时，未获得完整 MV3 Service Worker 安装验证。
- 实际运行来源审计器前 4 个源，全部在 DNS 解析时失败；未声称任何在线真实网站被本应用成功抓取。具体结果见 `openfeed-live-audit.json`。
- 外部网页检索能阅读 Oaktree / BofA / WGC 研究条目，而 KKR 公开静态视图主要是筛选 UI；这些是外部网页阅读结果，不是产品抓取成功或生成 Recipe 的证据。

## 当前未关闭的阻断项（不可宣传 Production Ready）
1. **VIS-01：完整 MV3 浏览器扩展安装、popup、点选、回传、Studio 保存并在真实来源抓取的集成测试。** 网页注入脚本和离线 API 链路此前经过测试，不等同浏览器扩展安装验收。
2. **SEC-01：Playwright 的独立服务、受约束的 Linux 权限、真实出站 ACL 和无法触及内网/云元数据的渗透测试。** 当前默认关闭，不允许在任意来源可输入的公网部署中开启。
3. **LIVE-01：Oaktree、BofA、WGC、KKR、Citi 等真实来源联网、可稳定提取的 Recipe 和连续多周期更新。** 当前环境 DNS 无法解析，批量审计器已如实记录失败。
4. **DEPLOY-01：Docker 实际 build/up、持久化卷重启、恢复备份和长期运行测量。** 当前命令行没有 Docker，无法在此环境实测。
5. **READER-01：公开 HTTPS 地址的 Readwise Reader 实际订阅、刷新、去重和日期表现。** 需要公网部署与可用 Reader 账户或由用户协助验证。
6. **PRODUCT-01：严格筛选页、登录/授权页、职位生命周期、PDF 元数据、JSON API 规则、Feed43 完整语法、智能修复。** 尚未全功能开发或验收。

## 不能通过“更多单元测试”替代的验收
- 在真实 Chrome/Edge 手工安装未打包扩展并保存可复现录屏/自动化结果。
- 使至少 5 个真实站点稳定 3 个以上采集周期，并检查日期、唯一 GUID、漏抓、去重、重试。
- 使用真实网络隔离运行浏览器 Worker，测试 DNS rebinding、重定向、子资源、WebSocket 与本地元数据 URL。
- 完成 Docker 部署、数据库一致性恢复和 Reader 的完整链路。

## 复现命令
```bash
cd openfeed-studio
PYTHONPATH=. pytest -q
PYTHONPATH=. python tools/audit_sources.py --input tools/pilot-sources.csv --output /tmp/openfeed-source-audit.json --limit 20
node --check static/app.js
node --check extension/popup.js
node --check extension/content.js
node --check extension/background.js
```

建议先在能连外网、能运行 Docker 和图形化 Chrome 的正式工作环境进行上述验收；除非报告中各阻断项得到真实证据，否则保持 NO-GO。
