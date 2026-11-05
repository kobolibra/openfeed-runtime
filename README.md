# OpenFeed Studio · 网页转 RSS

把金融研究、新闻与招聘信息页转换成可供 RSS 阅读器订阅的信息流。支持 CSS/XPath、Feed43 子集、JSON API、PDF 链接、原生 RSS/Atom/JSON Feed、分页去重、规则历史、网页点选、OPML 与数据库备份。

## 本次实际交付（2026-10-22）

- 两份原始 ZIP 已逐字节核对，113 个文件完整，原包单独保留，未使用记忆重建。
- **6 个真实站点页面 → 111 条实际 RSS 项目**：Oaktree 36、BofA 24、Gold.org 20、KKR 4、Morgan Stanley 4、猎聘 23。
- 提供 6 份 XML、可导入规则、带文章历史的 SQLite 备份、原始页面 SHA-256 及核验记录。
- 每条链接来自真实页面正文卡片；复取去重、失败保留原 RSS、独立 RSS 解析均验证。Oaktree 有 36 个完整原始日期；其他条目原页只有月份、相对日期或无日期，未编造完整发布日期。
- **194 项 Python 回归、4 项 JS 弹窗测试、19 项真实本地 HTTP/UI/恢复检查**，范围分别见证据。MV3 安装冒烟通过，完整真实工具栏点选回传未完成。

### 核验范围

这 111 条来自本次真实公开网页快照，经过原工程提取器、SQLite 和真实 Uvicorn RSS 接口校验。它们证明页面内容能正确生成 RSS；不代表全站历史完整覆盖、持续自动更新或 Readwise 云订阅已经通过。

本机系统 DNS 为站点返回 198.18.* 保留地址，默认受保护抓取器正常拒绝连接。本次使用固定公开域名白名单的只读系统网络工具按 robots 抓取原文，再核验规则；没有放宽生产抓取器的 SSRF 校验。提供的 6 条规则保持暂停，部署真实抓取网络并复测后再开启更新。

Capital Group 有资格/条款门槛；CEPR 返回 403；Citi 的 robots 禁止该路径。本次均未绕过。猎聘通过系统只读请求得到公开职位列表，另一网页读取工具此前遇到验证码；不声称任何访问条件下一定可用。

## 启动

Python 3.12，单进程运行；完整步骤见 [部署指南](docs/DEPLOYMENT_20261022.zh-CN.md)。从本目录运行：

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-lock.txt
export OPENFEED_ADMIN_TOKEN="$(python -c 'import secrets;print(secrets.token_urlsafe(32))')"
export OPENFEED_DB="$PWD/local-openfeed.sqlite3"
export OPENFEED_PUBLIC_URL='http://localhost:8765'
python -m uvicorn openfeed.app:app --host 127.0.0.1 --port 8765 --workers 1
```

在 http://localhost:8765 打开管理界面，输入终端中的 `OPENFEED_ADMIN_TOKEN` 值。若希望直接查看本轮真实内容，将交付包 `feeds/captured-feeds-backup.sqlite3` 复制为 `local-openfeed.sqlite3` 后再启动；不要覆盖已有数据库。规则 JSON 导入只迁移规则，SQLite 备份同时包含文章历史。

本地 URL 不能供 Readwise 云访问；需要固定公开 HTTPS origin。Docker Compose 文件已提供，但本机没有可用 Docker Engine，镜像构建和真实隔离网络尚未验收。

## 验证

```sh
python -m playwright install chromium
export OPENFEED_DB="$PWD/test-import.sqlite3"
python -m pytest -q -ra
node --test tests/js/test_popup.cjs
PYTHONPATH=. python tools/verify_http_ui.py --output evidence/http-ui
PYTHONPATH=. python tools/verify_generated_rss.py --snapshot ../feeds/captured-feeds-backup.sqlite3 --output evidence/real-rss-http
```

本轮页面采集、明确规则和 RSS 再生成可分别使用 `tools/capture_public_sources.py`、`tools/build_captured_rss.py`。前者仅能请求固定白名单公开域，先检查 robots，不能接收任意用户 URL，也不替代应用受保护抓取器。当前输出见交付包 `evidence/public-captures/` 与 `feeds/`。

## 文档与源码

- [本次 RSS 结果与限制](docs/RSS_RESULTS_20261022.zh-CN.md)
- [验收矩阵及证据](docs/ACCEPTANCE_20261022.zh-CN.md)
- [启动、部署、备份恢复](docs/DEPLOYMENT_20261022.zh-CN.md)
- `openfeed/` 后端、提取器、SQLite、受保护 HTTP 与独立浏览器 IPC
- `static/` 管理 UI 与静态点选；`extension/` Chrome MV3 实时点选
- `tests/`、`tools/` 回归和复现工具；`requirements-*.lock` 本次锁定依赖

原始版本历史文档与旧 README 保留用于追溯，当前状态以本 README、本次验收和实际日志为准。当前仍是单管理员、单实例工程版本；自动抓取网络、Docker 运行隔离、完整 MV3 权限流程、Readwise 云订阅和长期在线运行均有明确未通过项，不能标记生产全部验收。
