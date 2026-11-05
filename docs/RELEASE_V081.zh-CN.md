# OpenFeed Studio v0.8.1 — 跨端可视化数据流验收

日期：2026-10-21

## 本轮实际修改
- 新增 `tests/test_live_picker_end_to_end.py`，用系统 Chromium 运行真实 `extension/picker.js` + `extension/content.js`，模拟扩展消息 API 后点击文章及标题、链接、日期元素。
- 验证 3/3 重复文章匹配；标题/链接/日期覆盖率分别为 3/3；URL 和日期属性规则分别有 `@href`、`@datetime`；所有文章被高亮。
- 将页面生成的 **实际选择结果** 编码成 Studio 当前支持的导入片段，并在 Chromium 加载真实 `static/app.js` 与真实 Studio HTML 结构，校验源 URL、文章规则与三个字段规则完整填入。
- 全部 Python 回归测试 64/64 通过；核心前端脚本 Node 语法检查通过。

## 明确测试边界
- 该测试通过注入脚本和模拟 `chrome.runtime` 消息桥模拟扩展选择；**没有**验证扩展在正式 Chrome UI 通过“加载已解压的扩展”安装、MV3 service worker 生命周期、浏览器弹窗的真实跨窗口权限及回传行为。
- 测试不访问真实金融研究机构，不验证动态站点、不连接 Readwise Reader，也不表明 Docker 已经完成实测。
- 因环境对 `file://` 和本机端口导航设置了浏览器管理限制，Studio 的 UI 环境测试使用 `page.set_content()` 与加载实际源码。仅对本地测试中的 `sessionStorage` 进行 stub。`history.replaceState` 在无源 `about:blank` 测试中会产生浏览器异常，但实际表单填充断言通过；它不对应部署到 HTTP(S) 后的正常行为。

## 正式发布仍需通过的硬门槛
1. Chrome/Edge 扩展安装和真实用户交互，实际公网网站点选。
2. Studio 后端抓取生成 XML、连续两次去重与 Reader 真正订阅。
3. Playwright 浏览器 worker 网络隔离与出站 SSRF 保护。
4. Docker 构建/重启持久化与并发、7x24 长稳验证。

## 运行
```
PYTHONPATH=. pytest -q
PYTHONPATH=. pytest -q tests/test_live_picker_end_to_end.py
```
本机需有 `/usr/bin/chromium` 供浏览器回归测试运行。
