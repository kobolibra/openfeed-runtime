# OpenFeed Studio v0.9 — 端到端抓取发布链路测试

## 本轮真实交付

新增 `tests/test_picker_to_rss_full.py`，在系统 Chromium 中真实点击文章、标题、链接、日期，通过真实浏览器扩展选择器算法得到 CSS Recipe。经真实 FastAPI `/api/feeds` 和 `/api/feeds/{id}/run`、SQLite 持久化、`/rss/{id}.xml` 发布检查完整链路。还验证重复刷新不新增 GUID、上游抓取失败时保持已发布 RSS。HTTP 上游为固定 HTML 测试夹具，原因是避免把第三方网站的不稳定性混入本地回归；这不是对公网实时网站的证明。

## 验证范围

- Python pytest 全量回归通过；可视化真实浏览器点击和后端 RSS 发布在同一端到端测试中验证。
- JS 语法编译、Python 编译成功。
- 浏览器扩展 Manifest V3 实际安装与弹窗行为仍未完成独立验收。
- 真实银行/资管/猎聘站点连续在线采集、Readwise Reader 云端消费、容器网络隔离、Docker 构建及长时运行仍未通过发布验收。

## 下一次真实环境发布门禁

1. 使用 Chrome/Edge 用户配置目录安装 MV3 扩展，确认 `activeTab`、Service Worker 与规则回传端到端成功。
2. 安全部署 Playwright 独立 Worker；应用层 SSRF 检查不足以替代网络出口防火墙。
3. 将 Oaktree / BofA / WGC / KKR / Citi 逐站加入多周期联网验证并保存来源证据。
4. 在公共 HTTPS Feed 上验收 Reader 轮询、GUID 与日期更新，执行 Docker 重启/恢复演练。

禁止将离线夹具验收标记为目标站已验证，禁止将实验浏览器模式暴露给不可信公共用户。
