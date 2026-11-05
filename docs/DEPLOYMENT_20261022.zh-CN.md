# 运行、部署与恢复指南

## 已验证的本地运行

验证环境：macOS ARM64、Python 3.12.14、Playwright 1.55.0、Chromium 140.0.7339.16、SQLite WAL。实际执行日志见交付 `evidence/`。所有命令从解压后的 `source/` 目录执行。

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-lock.txt
python -m playwright install chromium
python -m pip check
```

`requirements-lock.txt` 是本轮完整开发/验收环境。`requirements-runtime.lock` 只包含 API 依赖，`requirements-browser.lock` 包含 worker 依赖。版本被锁定，但 Linux 镜像尚未在本机构建，不能推断其已验收。

```sh
export OPENFEED_ADMIN_TOKEN="$(python -c 'import secrets;print(secrets.token_urlsafe(32))')"
export OPENFEED_DB="$PWD/local-openfeed.sqlite3"
export OPENFEED_PUBLIC_URL='http://localhost:8765'
export OPENFEED_ENABLE_SCHEDULER=1
python -m uvicorn openfeed.app:app --host 127.0.0.1 --port 8765 --workers 1
```

在自己的终端保管生成的 `OPENFEED_ADMIN_TOKEN`，登录页面输入该值。只有一个进程/worker；当前锁、域限速与调度器按单实例设计。`localhost` 地址供本地使用，Reader 云无法访问。本机假 IP DNS 会被正常拒绝，改用真实公网 DNS 的部署网络，不能放宽非公开地址保护。

## Docker 部署步骤（必须在有 Docker Engine 的机器执行验收）

复制 `.env.example` 为 `.env`，生成强随机 token 并替换占位符；配置正确持久化数据库和固定 URL。不要将 `.env` 放入公开仓库。

```sh
docker compose config -q
docker compose up --build -d
docker compose ps
docker compose logs --no-color --tail 200 openfeed
```

浏览器模式使用独立 overlay，API 不在自身进程启动 Chromium：

```sh
docker compose -f compose.yaml -f compose.browser.yaml config -q
docker compose -f compose.yaml -f compose.browser.yaml up --build -d
docker compose -f compose.yaml -f compose.browser.yaml ps
docker compose -f compose.yaml -f compose.browser.yaml logs --no-color --tail 200
```

必须实际证明：worker 只在 internal 网络；egress proxy 可连公网且拒绝私网/localhost/169.254.169.254/混合 DNS 记录；worker 不能直连公网、API、SQLite；代理/worker 端口没有对外发布；浏览器崩溃或服务重启后旧 RSS 保留；队列状态可诊断。离线 YAML 测试不能替代这些探测。本次没有执行镜像构建和运行探测。

发布 Reader 可用地址时，在单独管理的 HTTPS 入口前设置永久 origin；管理页面、数据库备份及 token 保持受控。当前 token header 只是单管理员访问控制，不是多租户身份系统。验证外部 Reader 实际 GET、响应状态、RSS 项目与客户端更新后再标记云订阅通过。

## Chrome MV3

加载 `extension/` 为解压后的开发扩展。打开目标公开网页，点击扩展图标，选择文章容器及标题、链接、日期，设置自己的 Studio origin，选择 Open in Studio，先测试提取再保存。浏览器登录态不会传给服务端。

安装冒烟测试：

```sh
PYTHONPATH=. python tools/verify_extension_install.py
```

完整真实扩展人工操作脚本（会开一个临时 Chromium 和本地 Studio，源页面是清楚标注的合成 fixture）：

```sh
PYTHONPATH=. python tools/verify_extension_live.py --output evidence/extension-live
```

脚本出现 READY 后，在其窗口中点击工具栏 OpenFeed 扩展、逐项点选容器/title/link/date，再 Open in Studio。脚本验证真实 runtime/storage/tabs.create 与实际 HTTP Studio 导入。240 秒未完成即失败。本轮只有安装冒烟通过，完整人工操作脚本未完成。不要把修改 manifest、额外授予 host 权限或 Chrome API 仿真当成原权限模型通过。

## 复测

```sh
export OPENFEED_DB="$PWD/test-import.sqlite3"
# 如需已安装的 Chromium，可明确指定 OPENFEED_CHROMIUM_PATH。
python -m pytest -q -ra --junitxml=evidence/tests.xml
node --test tests/js/test_popup.cjs
for file in static/*.js extension/*.js; do node --check "$file"; done
PYTHONPATH=. python tools/verify_http_ui.py --output evidence/http-ui
PYTHONPATH=. python tools/verify_live_sources.py --output evidence/live-sources
PYTHONPATH=. python tools/benchmark_local.py --feeds 150 --cycles 10
PYTHONPATH=. python tools/verify_durability.py --seconds 120 --output evidence/durability
```

`verify_http_ui.py` 使用真实 Uvicorn HTTP、Chromium、SQLite 和恢复重启；内容明确为合成存储数据，不能用于声称站点真实抓取成功。`verify_live_sources.py` 使用真实客户端，先检查 robots；遇到禁止/无法核对/验证码/资格限制会留下状态并停止。候选提取也不能自动升级为稳定 RSS 验收。

## 备份与恢复

在管理 UI 的 Import & export 中下载 Full database backup。Recipe/OPML 不含文章历史；数据库备份包含历史、规则版本与稳定 ID，还可能包含私有源元数据。

```sh
# 先停止 API/调度器。省略 --execute 时只验证备份。
PYTHONPATH=. python tools/restore_backup.py openfeed-backup.sqlite3 restored.sqlite3
PYTHONPATH=. python tools/restore_backup.py openfeed-backup.sqlite3 restored.sqlite3 --execute
```

若目标已存在，用明确的 `--replace` 并保留生成的 `.before-restore`；存在 WAL/SHM/journal 时工具拒绝覆盖。恢复后设置相同 `OPENFEED_PUBLIC_URL` 和数据库路径，再启动单 worker。核对数据库完整性、源数量、文章数量、原 RSS URL、GUID 和 Reader 结果。此次真实 HTTP 验证已证明合成数据库备份恢复重启后 RSS 字节一致。

## 持续观察

在真实网络上先运行少量源，确认文章范围、日期和分页，再扩大到 150+。监控 `/api/monitor`、连续失败、空提取、限速、队列积压、存储空间与备份恢复。招聘源默认保持 Partial/unknown；只有完整枚举和分页均被证明时才能开启 Complete listing。消失只是观察结果，不代表职位确认关闭。

本轮 150 源基准和 120 秒本地短时耐久测试不构成 7×24 在线运行证明。长期稳定性、动态浏览器负载以及站点规则漂移，需要在实际部署网络持续观察并保留日志。
