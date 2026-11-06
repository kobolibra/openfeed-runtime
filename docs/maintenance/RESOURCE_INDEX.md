## 2026-11-06正式云端生产新增
本机适配器：ops/local_cloud_sync.py、ops/local_cloud_ui.py及tests/test_local_cloud_*.py。实际本机启动配置的无凭据快照在ops/mac_runtime/（不是云端runner入口，不自动执行；源码/令牌路径需按LOCAL_RUNTIME定位）。生产云代码仍固定e105；维护main新增本机代码不代表生产runner已换源码。最终切换证据见CURRENT所列production-cutover-20261106目录。

# 文件与证据索引

同机工作区根见LOCAL_RUNTIME；交接包路径单列，不要把两个根混用。

| 内容 | 同机路径 | 私密包内路径 |
|---|---|---|
| 唯一接手入口 | source/AGENTS.md（完整路径见LOCAL_RUNTIME） | START_HERE.md → source/AGENTS.md |
| 迁移阶段合同 | source/docs/maintenance/CLOUD_HANDOFF.md | 同source相对路径 |
| 原始来源/规则/历史/阶段状态 | 运行Docker卷；在线备份work/handoff-20261105 | private-state/openfeed-online.sqlite3 |
| 完整当前配方 | work/handoff-20261105/feeds-private.json | private-state/feeds-private.json |
| GUID/ID/phase/db校验基线 | work/handoff-20261105/state-baseline.json | private-state/state-baseline.json |
| 20源两地请求 | work/stage19/comparison-targets.json、comparison_probe.py | evidence/stage19/同文件 |
| 远端每源响应正文、curl指标 | work/stage19/remote-comparison/ | evidence/stage19/remote-comparison/（不带header/cookie） |
| 本地同请求响应正文、指标 | work/stage19/local-comparison/evidence/ | evidence/stage19/local-comparison/evidence/ |
| 内容验证与对照结果 | work/stage19/remote-validation.json、local-validation.json | evidence/stage19/同文件 |
| 无需重跑的内容校验脚本 | work/stage19/validate_comparison.py、validate_local.py | evidence/stage19/同文件；按包根适配路径 |
| Brookings本地与加密DNS诊断 | work/brookings-20261105 | evidence/brookings-20261105（仅选定JSON） |
| 两猎聘浏览器现场 | work/stage19/liepin-browser-probe.json、liepin_browser_probe*.py | evidence/stage19/同文件；detail脚本未执行 |
| Stage19最新466测试 | work/stage19/tests-final.log | evidence/stage19/tests-final.log |
| Stage17恢复/保全测试 | work/stage17/tests.log、deadline-tests.log、preservation.json | evidence/stage17/同文件 |
| 当前Mac运行模板 | work/stage3/compose.live.yaml、live_stack.py | runtime/stage3/同文件（含Mac绝对路径，不可原样用于runner） |
| Mac发布/健康包装 | work/stage6/run_auto_publish.py | runtime/stage6/run_auto_publish.py |
| Mac发布最近成功/失败 | work/stage6/publisher-state/last-{success,failure}.json | runtime/stage6/publisher-summary/（时间戳快照） |
| 当前宿主egress配置模板 | work/stage10/com.time.openfeed.egress.plist（可能旧）；实际~/Library/LaunchAgents | runtime/launchagents/实际plist副本；含本机路径，无token明文 |
| 同类项目研究与方案 | outputs相关调研目录 | research/按原目录名选取MD/manifest；不含重复工程ZIP |
| 可复核校验清单 | 本轮包生成器 | MANIFEST.json、verify_bundle.py |

GitHub远端证据原run：41965774214（Brookings），41966397327（20源）；URL均为https://github.com/kobolibra/openfeed-feeds/actions/runs/<id>。远端artifact仅3天，关键文件已在本地和私密包保留，不要为取证再发起诊断。

包不含：管理令牌、GitHub凭据/keychain、个人浏览器/登录会话、venv、Docker虚拟机和缓存镜像、全部历史交付ZIP。原因与重建办法见START_HERE；正常运行用锁定依赖重建，敏感授权在目标环境重新配置。未包含不等于这些资源已经迁移。

若同机文件已经被后续agent更新，先看维护流水与hash差异，不使用旧包覆盖新内容。错误计数持续变化，始终重新采样。

原用户粘贴的两版需求与两版源列表已实际找到并复制到私密包research/original-user-materials；历史188项矩阵在evidence/intake/historical-188-acceptance.json。用于核对171当前来源与合并/删除/未完成项，不作为当前通过证据，不复活已删除来源。

## 当前免费云运行证据
- 免费入口公库workflow `.github/workflows/runtime-cloud.yml`，commit3f71d14；私库source ref固定b9516dab，state branch shadow-state。
- 实际运行与job时间：本chat work/cloud-evidence/public-{runs,jobs-*}.json；单源和批次报告report-*.json；独立state-verification.json；171行cloud-validation-matrix.json。source/work/cloud-switch有检查点副本，时间以文件为准。
- 本chat outputs/OpenFeed-cloud/runtime-cloud-48h.yml为实际已通过Chrome提交并逐字复核的67行配置，不再是让用户手工提交的阻断文件。
- GitHub连接工具transport故障可用CUA原生Chrome网页操作；不要把旧CUA超时当永久不可用。首次Browser inventory无Chrome扩展surface，但getApp(com.google.Chrome)原生AX可用。只使用cua_repl UI API，不运行AppleScript绕过。
