# OpenFeed Studio — 2026-10-21 继续工程验收

## 本轮完成（已运行实际代码）

1. RSS 公开订阅地址现同时支持 `GET` 和 `HEAD`，保留标准 `ETag`、`Cache-Control`、无嗅探头；可识别多个 `If-None-Match`、弱验证值和 `*`，返回 `304`。HEAD 不返回正文，并提供原始 Feed 长度。`tests/test_rss_reader_http.py` 使用真实 FastAPI ASGI 路由与 SQLite 验证，不代表已被 Readwise 云端实测。
2. `tools/restore_backup.py` 提供离线 SQLite 灾难恢复：SQLite integrity_check、foreign_key_check、必需表校验、默认只检查不执行、覆盖需 `--replace --execute`、旧库另存 `.before-restore`、拒绝存在 WAL/SHM/journal 文件的目标、临时文件写入后原子替换。`tests/test_disaster_recovery_cli.py` 验证正向恢复及拒绝危险操作。
3. 实测 Chromium 尝试导航 localhost 返回 `net::ERR_BLOCKED_BY_ADMINISTRATOR`；使用 Xvfb 启动扩展 Service Worker 仍超时。因此 MV3 真实安装及本机浏览器导航**不能视为通过**，且这不是前端 DOM 单元测试能替代的。

## 使用数据库恢复脚本

先停止运行的 API / Worker，确认数据库不再被使用，将数据库备份复制到目标服务器的私有目录：

```bash
python tools/restore_backup.py backup.sqlite3 /path/to/new-openfeed.sqlite3
# 仅显示备份内源和文章数量，不做任何更改
python tools/restore_backup.py backup.sqlite3 /path/to/new-openfeed.sqlite3 --execute
# 如果已有数据库，先停服、做独立备份、检查 WAL，然后使用
python tools/restore_backup.py backup.sqlite3 /path/to/openfeed.sqlite3 --replace --execute
```

覆盖操作会保留原目标为 `.before-restore`，如果同名恢复副本已存在则拒绝继续。不能在 API 活跃时调用，且无法自动检查所有外部进程已关闭，请管理员自行确认停机。

## 未完成的发布门槛

- 完整真实 Chrome/Edge MV3 安装、弹窗、页面选择到 Studio 回传的人工/自动端到端验收。
- Docker 构建、容器内 Chromium 实际启动、公共出口代理的网络隔离与恶意网页网络测试、跨容器 IPC。只有测试用例和配置并不等于已证明生产隔离。
- 在可联网的执行环境多次实际抓取 Oaktree / BofA / KKR 等目标站点，并分别确认版权、访问和日期问题。
- 一个稳定公网 HTTPS 地址上的 Reader 云端订阅及跨周期 GUID 验收。
- 连续运行与灾备演练；当前新增恢复脚本是功能验证，不是完整停机/重启验收。

以上在缺少相应运行环境或授权前保持 NO-GO，不得声称正式产品发布成功。
