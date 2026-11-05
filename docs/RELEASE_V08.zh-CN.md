# OpenFeed Studio v0.8 — Extension Transfer Hardening

## 本轮实际修改

- 修正扩展 popup 的 Studio URL 输入校验：拒绝 HTTP 公网端点，只有 HTTPS 远端地址或本机 localhost/127.0.0.1 HTTP 被允许；拒绝 URL 中的用户名、密码、查询、片段和非根路径。
- 扩展向 Studio 传送规则前增加 12,000 字符的大小限制，避免过大导航 URL。
- 增强 Studio `#import-picker` 的字段白名单验证，只允许 title、link、date、summary；拒绝异常的 URL 协议和过长 URL。
- 增加 Node.js VM 测试，直接执行真实 popup.js，覆盖本机/HTTPS 可用、HTTP 远端被拒绝、异常 Studio URL 被拒绝。

## 验证证据

- `PYTHONPATH=. pytest -q`：63 passed。
- `node --test tests/js/test_popup.cjs`：4 passed。
- `node --check extension/popup.js` 与 `node --check static/app.js`：通过。
- 尝试在无头 Chromium 使用 `--load-extension` 加载 MV3 扩展，但没有出现 extension service worker。故**扩展实际安装/弹窗/网页选择全过程仍未通过完整浏览器验收**。

## 未完成与发布阻断

- 在带 GUI 的 Chrome/Edge 实际安装扩展、完成 article/title/link/date 的逐项选择、关闭再打开 popup、回传并保存规则，再验证生成 RSS。
- 静态网站线上抓取、动态浏览器 Worker 隔离、Readwise Reader 云端测试、Docker 部署与持续运行。
- 不建议对任意不可信外部用户开放动态抓取。

## 本地运行

`PYTHONPATH=. pytest -q`

`node --test tests/js/test_popup.cjs`

复制 `.env.example` 为 `.env`，设置强令牌后执行 `docker compose up --build -d`（Docker 当前环境尚未做构建验证）。
