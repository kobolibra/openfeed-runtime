# 当前 Mac 运行位置（迁移时必须更新）

工作区：`/Users/time/Documents/Codex/2026-10-22/referenced-chatgpt-conversation-this-is-an-3`
源码：工作区下 `work/local-trial/source`。
Python：工作区下 `work/venv312/bin/python`。测试cwd为源码根目录，使用绝对Python路径，避免反复cwd错误。
API：`http://127.0.0.1:8765`，用户入口 `http://localhost:8765/`。
管理令牌：源码 `.openfeed-local/admin-token.txt`，只内部读取，不展示或写进维护记录。
权威SQLite：Docker卷 `openfeed-live_openfeed-data`，容器路径 `/data/openfeed.sqlite3`。源码旁的sqlite不是权威运行库。

Compose：工作区 `work/stage3/compose.live.yaml`；从工作区执行 `work/venv312/bin/python work/stage3/live_stack.py ps`。
Docker socket：`unix:///Users/time/Documents/Codex/.openfeed-colima/openfeed/docker.sock`。
Colima home：`/Users/time/Documents/Codex/.openfeed-colima`，profile `openfeed`。
服务：openfeed、browser-worker、egress-proxy。browser-worker init=true，私有网络+专用代理，不放宽sandbox或TLS。
宿主出口：127.0.0.1:8900，绑定en0，OPENFEED_PHYSICAL_DNS=encrypted；详见源码 NETWORK.zh-CN.md。

用户LaunchAgents：`/Users/time/Library/LaunchAgents/com.time.openfeed.{egress,health,publish}.plist`。
包装程序：工作区 `work/stage6/run_auto_publish.py`。端口健康探测不能证明目标站可达。
状态/发布日志：`work/stage6/publisher-state`。公共发布checkout：`work/stage6/publish-repo`。
公共仓库：https://github.com/kobolibra/openfeed-feeds
Pages：https://kobolibra.github.io/openfeed-feeds ，RSS `/rss/<id>.xml`，OPML `/subscriptions.opml`。

旧证据：work/stage13（RSS全量、备份、失败复验）、work/stage14（446项测试和历史统计）。
调研：outputs/OpenFeed-稳健性调研-20261103/调研与改进.md；PageSift固定版本调研在outputs/OpenFeed-PageSift-Research-20261026。
备份：work/stage13/before-deploy.sqlite3、after-deploy.sqlite3（私密，禁止公开）。不要拿历史备份直接覆盖运行库。

当前Mac空间有限，不安装大型VM或重复下载浏览器。仅因连接失败不应重建全部栈。曾有自动权限审核超时，可按工具提示处理，不能将其当作代码故障。

## 2026-11-05当前检查点

实际API镜像d5ab37b52896、出口406db2946f21、浏览器5a23457c6d86（完整ID在私密包runtime/image-identities.json）。最新单次导出在work/handoff-20261105/openfeed-online.sqlite3；该文件是交接备份，不是新的生产数据库。
最新关键测试work/stage19/tests-final.log（466通过）。真实源与证据对应见RESOURCE_INDEX，迁移计划CLOUD_HANDOFF。
本轮私密包生成脚本work/handoff-20261105/build_bundle.py可在授权环境重新打包；包含私密DB/配方，禁止上传公共仓库；不含管理员令牌/GitHub凭据。
