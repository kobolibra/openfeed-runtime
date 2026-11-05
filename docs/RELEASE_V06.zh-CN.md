# OpenFeed Studio v0.6 — Visual Coverage

## 本轮实际交付

- Visual Picker 新增跨文章卡片匹配高亮：点选一条后显示所有匹配的文章容器。
- 标题、链接、日期、摘要选择器在所有匹配卡片中高亮，并展示逐字段覆盖数量（例如 `title: 4/4`）。
- 将高亮 CSS 注入已净化的 iframe `srcdoc`，确保样式在浏览器隔离文档中真正生效，而不是只在父页面定义。
- 新增真实 Chromium 测试，验证文章容器识别、字段覆盖率及 DOM 高亮类。

## 验证证据

命令 `PYTHONPATH=. python -m pytest -q`：63 passed；`node --check static/app.js` 和 `node --check static/picker.js` 通过。

## 明确未完成

当前仅支持静态 HTML 快照点选；尚无真实跨站浏览器扩展，动态 Playwright 抓取仍为实验功能且缺少独立安全隔离。未完成联网金融源、Docker 构建、Readwise 在线订阅或长期负载验收。对 XPath / Pattern 模式，当前可视化选择器不直接生成规则。

## 推荐下一工程重点

1. 浏览器扩展在真实网页中以用户授权方式点选，采用消息传递，不尝试跨域 iframe DOM 访问。
2. 规则保存前强制在真实 fetch 输出上进行字段覆盖与链接有效性验证。
3. 独立网络隔离的 Browser Worker 与真实网站连续刷新测试。
