# 产品完成度：可复现验收矩阵

| 能力 | 代码状态 | 本地证据 | 尚缺什么 |
|---|---|---|---|
| CSS/XPath 静态 HTML、RSS/Atom/JSON Feed | 实现 | API/SQLite/RSS 自动化测试 | 各真实站点连续抓取 |
| Feed43 全局/重复捕获、模板化输出 | 已实现兼容子集 | 真实 API 端到端及异常模式测试 | 旧 Feed43 全语法兼容测试集 |
| JSON API → RSS | 已实现 | 数据路径、无效链接、HTTP API 测试 | 特定金融网站公开 API 实测 |
| PDF 列表 → RSS | 已实现 | 路径/MIME 标注、API 测试 | 附件格式及 PDF 正文的合法处理 |
| 职位新增、变化、疑似关闭 | 实现 | 持久数据库状态、事件 API、误报保护测试 | 猎聘/Citi 实际数据及是否允许抓取 |
| 单机调度、同域名限速、去重与质量闸门 | 已实现 | 离线/本地数据库回归 | 7×24 实际运行、跨进程调度 |
| HTML 快照可视化高亮 | 原型完成 | DOM / Chromium 网页脚本测试 | 动态真实页面跨站编辑验收 |
| Chrome/Edge MV3 扩展 | 代码已有 | 内容脚本/规则回传模拟测试 | 浏览器实际安装、Service Worker 与弹窗完整验收 |
| 独立 Playwright Worker、出口代理、IPC | 代码完成 | mock Worker、代理隧道、私网拒绝、静态 Docker 结构测试 | Docker 实际构建、私网出口渗透测试、真实 Chromium |
| Rule Diagnostics、修改历史与回滚 | 已实现 | API 测试；只读修复建议 | 网页改版后的真实修复成功率 |
| 中英文 UI | 基础实现 | 文本资产/JS 语法测试 | 全量动态文案与完整浏览器可用性 |
| 300 源 SQLite/RSS 性能 | 本地通过 | 900 次 Store.finish 和 RSS 基准 | 抓取容量/连续负载/浏览器成本 |
| HTTPS Feed → Readwise Reader | 标准 XML 格式已实现 | XML 格式校验 | 公网部署、Reader 云端拉取实测 |
| Docker 生产部署 | 配置完成 | YAML/Compose 静态结构检查 | Docker Engine 构建、网络隔离、备份恢复、长期监控 |

**发布结论：NO-GO（生产发布）。** 不能将模拟上游数据成功理解为真实外部网站已通过。
