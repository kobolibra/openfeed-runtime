# JSON API 提取模式 — 本轮新增

对合法公开、无需绕过登录验证的 JSON API，使用现有 Web 管理页选择 `JSON API fields`，将 `Item selector` 填为 JSON 数组的点分隔路径（例如 `data.reports` 或 `groups.0.posts`），然后分别填写字段路径：title (`headline`)、link (`permalink`)、date (`published_at`)、summary (`excerpt`)。

字段路径只支持简单属性名、数字数组索引以及句点分隔；**不支持执行 JavaScript、任意 JSONPath 表达式或通配符**。路径相对于单条数组记录，缺失或非标量字段不会生成字符串。最大响应解析长度 2.5MB，列表最多 500 条，单次最多返回 100 条；与既有分页逻辑一样，若需要超过 100 条应单独设计更完整的数据接口分页适配。

提取项使用同一套 canonical URL、发布日期解析、质量闸门、持久化、去重和 RSS 2.0 发布流程。未实现 Bearer/OAuth 验证、JSON API Cursor 分页、速率限制头自动解析、权限站点访问。切勿把带 Token 的私有 API URL 录入普通 Recipe。现有网页模式、浏览器扩展代码与 Recipe 字段保持兼容。

## 验证

执行 `PYTHONPATH=. pytest -q tests/test_json_api_mode.py`；包括离线固定 JSON 响应下的 `/api/inspect → /api/feeds → /api/feeds/{id}/run → /rss/{id}.xml` 全链路回归，重复刷新插入数量归零。此测试不代表任何指定机构的线上 JSON API 已被发现或验证。
