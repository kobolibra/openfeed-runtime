# 开源生态尽调与 Build-vs-Reuse 决策

**基线日期：2026-10-21**。以下事实依据项目公开 README、GitHub 仓库许可证与项目文档；并非全部进行了源码审计或本地 Docker 集成测试。仓库未来可能变更，正式集成时要固定提交、重新核查许可证并做依赖漏洞扫描。

| 项目 | 核心能力 | 可核实的许可/风险 | 决策 |
|---|---|---|---|
| [taroved/pol](https://github.com/taroved/pol) | PolitePol 原始公开源代码、可视化交互、下载器 | MIT；作者明确标记**旧代码** | 设计、字段模型与交互研究；不直接上线 |
| [projects-shelf/RSS_Generator](https://github.com/projects-shelf/RSS_Generator) | Go/SQLite，点击生成 XPath，Gemini 辅助 | MIT；规模较小，AI 需要自有 API Key | 对照实验，不纳入主应用核心 |
| [html2rss/html2rss](https://github.com/html2rss/html2rss) | 自动内容识别、HTML/JSON、配置/检查/测试流程 | MIT；Ruby 技术栈 | 自动侦察算法参考；未来可独立 adapter |
| [html2rss/html2rss-web](https://github.com/html2rss/html2rss-web) | 可直接部署的完整 Web-to-RSS 服务；动态可接 Botasaurus | 仓库有 LICENSE；部署成本、架构适配需验证 | **优先作为成品对照**，避免重复开发已有功能 |
| [usertour/openpicker](https://github.com/usertour/openpicker) | 跨站扩展点选、稳定 CSS、交互确认 | MIT；复杂 iframe/Shadow DOM 仍有限制 | 可视化第二阶段首选，但用户须安装扩展 |
| [RSS-Bridge/rss-bridge](https://github.com/RSS-Bridge/rss-bridge) | CSS/XPath + 大量网站 Bridge | 主程序 Public Domain，第三方组件各有许可 | 接入标准 RSS 输出，**不复制** Bridge 引擎 |
| [DIYgod/RSSHub](https://github.com/DIYgod/RSSHub) | 大量网站专用路由、活跃维护 | AGPL-3.0；公开服务部署合规要评估 | 外部 adapter；不嵌入主程序代码 |
| [RSSible](https://github.com/mhadidg/rssible) | 简化 CSS 与 Cloudflare Workers 路线 | 小型项目，静态页面为主 | 轻量 Serverless 模式参考 |
| [RSSAlchemy](https://github.com/Egor3f/rssalchemy) | Playwright 动态网页、代理、Cookie | AGPL-3.0；运行负载较重 | 浏览器执行参考，不直接复制 |
| [hFeeds](https://github.com/shafihuzaib/hfeeds) | Feed43 类文本规则，捕获/忽略 | 未核实明确许可；旧 PHP 输出 XML 实含可执行 PHP | **仅语义参考**，自主写限时解析器 |
| [feedless](https://github.com/damoeb/feedless) | 生成、聚合、全文、变更监控 | FSL-1.0-Apache-2.0（含使用限制及转换期），非即刻普通 MIT | 对照架构，不直接内嵌 |
| [changedetection.io](https://github.com/dgtlmoon/changedetection.io) | 页面变化检测、视觉/文本监控 | 与文章 RSS 数据模型不同 | 独立补充监控服务 |
| [rssweball.top](https://rssweball.top/) | Feed43 式在线网页转换、模板与分享 | **本次未确认可合法复用的官方源代码和许可证** | 产品功能参考，不能假定开源 |
| [feed43.com](https://feed43.com/) | 经典 `{%}`/`{*}` DSL 体系 | 在线服务状态与源码复用许可均不满足依赖要求 | 复刻公开功能语义，不依赖其服务 |

### 选择原则

1. **默认自己的核心数据归自己管**：Feed ID、Recipe、抓取历史与订阅地址不得被外部平台锁住。
2. 优先使用标准 Feed URL 组合；遇到多语言项目（Ruby/Go/PHP）通过独立进程/服务适配，不在主程序内部复制代码。
3. OpenPicker 负责从实际网页取得 CSS，**并不负责自动推断整个重复文章列表**；需要在主系统另建列表推断算法与人工校验。
4. html2rss 自动推断虽成熟，但与 Python 主程序存在跨语言管理成本；先通过外部工具基准验证其相对优势，再决定适配。
5. **禁止以“GitHub 可见”为依据认定能自由复制**。集成代码前需确认仓库许可证、第三方字体/图片资源版权与依赖许可。

### 计划中的技术 Benchmark

每个候选使用相同公开来源、相同网络和时间窗，记录：可提取条目数、标题链接准确率、日期准确率、首字节时间、提取 CPU/内存、JS 资源秒数、稳定 GUID、7 日运行成功率、部署依赖数量、引擎版本、许可证结论。若无法访问则写明“不可测”，不能以宣传描述代替测量。
