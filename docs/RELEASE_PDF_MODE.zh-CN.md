# OpenFeed Studio — PDF 研究报告订阅集成

## 本轮完成

- 新增 `pdf` Recipe 模式：支持从 HTML 列表中的 PDF 链接生成独立 RSS item。用户可输入 CSS 容器规则（例如 `article.report`），也可直接选中 `a[href]`。
- 只纳入 URL 路径以 `.pdf` 结尾的 HTTP(S) 链接；保留查询参数，过滤非 PDF 页面与重复 URL。**不下载或重新发布 PDF 正文。**
- 文章标题来源于链接文本、title 属性，最终回退至文件名；从同一报告卡片的 `<time datetime>` 读取日期；不伪造缺失的发布日期。
- 将 PDF 识别接入现有 `Recipe`、前端模式切换、`/api/inspect`、`/api/feeds`、调度、存储、去重及 RSS 输出；不是独立脚本。
- 自动化测试覆盖 CSS 范围、重复、日期、非法选择器，以及从 HTTP API 创建源、重复抓取、网络失败保留历史 RSS 的闭环。

## 当前验证

本地离线样本 + 真实 FastAPI/SQLite 代码，`78 passed`。尚未在真实金融机构网站连续抓取；未对 RSS `enclosure` 输出做兼容承诺（目前输出 PDF 的标准 `<link>`），因为没有可靠的文件大小/媒体类型验证。

## 仍未完成的上线门禁

1. Chrome/Edge 扩展完整安装与 UI 实测。
2. 真实金融网站连续抓取、公共 HTTPS RSS 与 Readwise Reader 云端订阅。
3. Playwright 独立网络隔离 Worker 和容器真实构建验收。
4. 更多分页/筛选和身份认证网站的适配、资源基准和备份恢复演练。

## 使用方式

在新建 Feed 中选择 **PDF publications**，输入公开研究栏目地址，并根据需要把 item selector 设为 `article.report`、`.document-card` 或 `main a[href]`。点击预览确认标题、PDF 链接及日期后保存 Feed。
