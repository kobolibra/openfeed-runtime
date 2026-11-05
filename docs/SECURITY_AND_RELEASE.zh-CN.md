# 威胁模型、运行安全与上线门禁

**安全等级：个人单管理员、自建、默认只监听 127.0.0.1。** 管理 API 不支持公开匿名创建网页抓取任务。RSS 输出路径为公开端点，须确认每条源内容适合公开分发。

## 威胁模型与现状

| 威胁 | v0.2 已有保护 | 上线前补充 |
|---|---|---|
| SSRF（127.0.0.1、内网/云元数据、DNS rebinding、重定向） | scheme/端口/IP 检查、仅公网目标；aiohttp 自定义 Resolver 将经验证 IP 直接返回给 connector；跳转逐次校验 | 独立 egress 防火墙和网络策略，容器网络渗透测试 |
| 超大响应 / 卡死 | 限定响应类型、2.5 MB 页面、超时、最多 3 次跳转、Feed43 regex 超时 | 资源与日志总量限额、站点访问预算 |
| 站点脚本执行 / XSS | 脚本、iframe、表单、远程资产从网页快照移除；受限 srcdoc CSP；前端文本 HTML 转义 | 使用浏览器真实 DOM 后另做沙箱安全评估与 CSP 审查 |
| Token 泄露 | 仅管理员 Header，不放在 RSS URL；`.env` 排除版本库 | 公网反向代理身份鉴权、TLS、Token 轮换、访问日志脱敏 |
| 源网站过载 | 按域名 60s 默认间隔、4 抓取并发、指数退避 | robots/站点条款审查、域名定额、429 Retry-After |
| 无授权爬取 | 不绕过 CAPTCHA/付费墙；不接入未经授权的 Cookie | 访问权限记录、非公开内容默认不发布 |
| 持久化损坏 | SQLite WAL、事务写入、抓取失败不删旧条目 | 自动在线一致性备份、定期恢复演练与磁盘报警 |
| 多节点重复抓取 | 明确仅支持**单进程**调度 | PostgreSQL 持久租约/任务队列后才开启多副本 |
| 供应链漏洞 | Docker 非 root、只读根、禁用 Linux capabilities、依赖范围限制 | 锁定依赖版本/镜像 digest、SCA、SBOM、镜像扫描 |

**设计警示：** 针对公共 URL 的 DNS 过滤不能代替操作系统网络策略。即使连接目标经过解析器检查，未来引入 Playwright 时，浏览器的子资源和 WebSocket 请求仍要独立拦截内网目的地；不能把主进程的防护当成浏览器沙箱防护。

## 运维与可观测性（未来目标）

- 每源：成功率、连续失败数、零条目次数、文章数变化、P95 耗时、429/403、上次成功/调度时间。
- 全局：活动任务数、域名限流等待数、数据库大小、RSS ETag 命中率、队列到期延迟、磁盘余量。
- 告警门槛建议：连续失败 >=3；最后成功时间 > max(3×计划间隔, 24h)；抓取项数较 7 天中位数骤降 >80%。**这些只是拟定指标，未在生产负载上调参。**
- 不把单个源无法访问误报成服务整体宕机；不在日志里保存 Cookie / Authorization / 管理令牌。

## 数据备份与恢复

**Recipe Bundle v2 不包含历史条目，不能代替完整 SQLite 备份。** 数据库正在运行时不能粗暴复制 `.sqlite3` 而忽略 WAL；使用 SQLite Backup API 或安全停止服务后备份。

```bash
# 在服务容器运行时进行 SQLite Backup API 快照：
docker compose exec -T openfeed python -c "import sqlite3; s=sqlite3.connect('/data/openfeed.sqlite3'); d=sqlite3.connect('/data/openfeed-backup.sqlite3'); s.backup(d); d.close(); s.close()"
# 把备份文件从容器里复制出来，存放到另一块磁盘：
CID=$(docker compose ps -q openfeed)
docker cp "$CID:/data/openfeed-backup.sqlite3" ./openfeed-backup.sqlite3
```

恢复时先停止服务，再替换数据库文件；验证权限、`PRAGMA integrity_check`、Feed ID 和历史项目数后再启动。公网域名必须保持不变，才能真正保留既有 Reader 订阅 URL。

## 正式发布阻断项（Release Blockers）

- [ ] 真正的外网 HTTPS、反向代理访问控制、网络层出站规则已经设置。
- [ ] 原生与普通网页真实样本通过；对 JS 站点标记未支持而非静默假成功。
- [ ] 抓取故障情况下现有 Feed 不被清空、不会返回非 XML 成功响应。
- [ ] 灾难恢复演练在独立实例上通过；条目数、Feed ID、可读性核对。
- [ ] 多域名压力测试与 48–72 小时连续运行验收。
- [ ] 依赖锁文件、许可清单、漏洞扫描和日志脱敏审查完成。
- [ ] Readwise Reader 从公网实际添加 RSS URL 并观察多次刷新。
- [ ] 浏览器 Worker 完成隔离安全评估后才能开启任意网页 JS 执行。
