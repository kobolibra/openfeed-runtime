# OpenFeed Studio v0.7 — Live Website Picker

## 已实现
- `extension/`：Chrome/Edge Manifest V3 扩展。使用 `activeTab` 和 `scripting`，点击图标后才向当前页面注入选取脚本；不请求广泛的永久站点权限。
- 在真实页面点击文章、标题、链接、日期、摘要，推导重复项和相对 CSS 规则。命中项高亮、字段覆盖率统计。
- `Open in Studio` 将来源地址和规则通过 URL fragment 带回 Studio 编辑抽屉；密钥不在 URL 内；不会自动保存/抓取，用户需要先执行 Test extraction。
- `Copy recipe` 可以手工备份规则；`Stop` 退出当前页面选择模式，Esc 也可退出。

## 安装方法
1. 启动 OpenFeed Studio (README 中的启动步骤)，浏览器访问 http://localhost:8765。
2. Chrome/Edge -> 扩展管理 -> 开发者模式 -> 加载已解压的扩展 -> 选择项目中的 `extension/` 文件夹。
3. 打开目标网页；点击扩展按钮，先选择 Article，再依次选择 Title/Link/Date/Summary，返回网页点击对应元素。
4. 再次打开扩展弹窗，填写 Studio URL，点击 Open in Studio。
5. 在 Studio 管理页检查选择器和来源地址，点击 Test extraction 验证，最后保存。

## 已验证
- 原有 pytest: 63/63。
- `node --check`：popup、content、background、Studio app 通过。
- 使用真实 Chromium 页面执行扩展的 content script（独立模拟 chrome.runtime 消息桥）：4 个重复 `<article>` 均被识别并高亮，标题选择器覆盖 4/4。

## 未验证与限制
- Chromium 无头模式未成功加载完整 MV3 扩展 service worker，因此真实扩展弹窗、安装与导航回传仍需 Chrome/Edge 图形界面人工验收。
- Browser extension 在登录网站上可视觉选取，但 Studio 后端并不继承浏览器登录态；遇到受认证/风控限制的站点仍可能抓取失败。
- 规则启发式算法不保证跨网页改版有效；Shadow DOM、跨域 iframe 和 SPA 页面切换可能需要进一步适配。
- 不应将 Studio 管理服务直接无保护暴露公网；动态抓取仍是实验能力。
