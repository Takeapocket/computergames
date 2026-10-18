# PySide6 比赛流程迁移与便携 EXE 0.2 验证

日期：2026-10-18。范围：在已交付的 0.1 单盘样机上迁移自定义开局、七盘制、完整计时及自动保存恢复。旧 Tk 界面、现有规则、P14 默认配置和旧棋谱读写继续保留。

## 交付

- 版本：`0.2.0-preview`。
- EXE：`E:\computergame\dist\desktop-0.2.0-20261018-portable\EinsteinChess-preview\EinsteinChess.exe`。
- ZIP：同一输出目录下 `EinsteinChess-preview-windows-x64.zip`，37,493,469 字节，约 35.8 MiB。
- ZIP SHA-256：`d48faa16b3a40e02bf653494adddbe5ea3345ab9e651ff3a31e7a979b73cdc98`。
- 操作说明：[DESKTOP_PREVIEW.md](../docs/DESKTOP_PREVIEW.md)；实际 EXE 截图：[desktop-match-prototype.png](../docs/ui/desktop-match-prototype.png)。
- 机器可读证据：[desktop_match_20261018_selftest.json](desktop_match_20261018_selftest.json)。旧 0.1 包与报告保留。

解压整个 ZIP 后双击 EXE；`_internal` 是随包运行依赖，不能单独拿走 EXE。运行无需另装 Python。用户数据在 EXE 同级 `user-data`；源码启动入口为 `scripts/run_desktop.py`，使用独立 `.venv-desktop`。

## 实现与行为

`MatchSession` 统一协调现有 core、GameRecord、MatchRecord、自动保存和计时。`gui/timing.py` 从旧 Tk 计时面板提取原计时模型，旧导入路径继续重导出，避免新 UI 引入 Tk 或另写时间规则。

- 开局：编辑双方六枚棋子的起始布局，验证编号与区域，支持原有预设和布局 JSON。七盘制默认沿用我方获胜时的实际布局；对手每盘重新录入，确认前仍须核对实际摆法。界面允许人工调整，不代替现场裁判核验。
- 七盘制：设置我方颜色和甲乙角色，复用原有先手映射、计分和四胜终止逻辑。每盘结束保存成功后才能继续；导出整轮包含已完成各盘。
- 计时：总用时可配置，默认每方 240 秒，显示剩余时间及当前步用时；悔棋不返还已用时间。暂停只停止计时，沿用旧 UI 允许合法补录的语义。默认超时提示及裁判确认，自动判负需显式开启；迟到判罚可指定已超时方，双方均超时需选定判负方。
- 恢复：关键操作落盘，计时中约每 2 秒保存；启动提示及手动入口支持恢复。恢复保留已保存的剩余时间、暂停状态与比分，不扣离线时间。实际盘和整轮不匹配、旧残留不能对应当前盘时明确拒绝，保留原文件和当前会话。
- 故障：原子替换遇 Windows 错误 5/32/33 最多尝试三次，等待合计 70ms；其他错误立即报告。持续失败需手动重试；终局保存未完成不能进入下一盘，重试不再计分。退出时不能把单盘另存成功误当成整轮恢复已保存。

当前单盘与整轮恢复分别使用 `recovery/auto_save.json` 和 `recovery/auto_save_match.json`。不删除损坏或不匹配文件。旧单盘棋谱继续由原 GameRecord 读取；无计时字段时无法重建历史用时。无规则版本标记沿用现有兼容策略；显式不匹配版本只读。

## 验证结果

| 验证 | 实际结果 |
|---|---|
| 原 `.venv` 完整 pytest | **1472 passed, 2 skipped，89.50 秒**；两个 Qt 测试模块因原环境没有 PySide6 而跳过 |
| `.venv-desktop` 桌面专项 | **99 passed，5.02 秒**；包含 session、match session、Qt 控件、app、路径及独立流程验收 |
| 源码 Qt 自检 | P14 合法推荐、单步执行、原 GameRecord 读写、悔棋及完整流程通过 |
| 实际 ZIP 解压验证 | 中文含空格目录、不同 cwd、仅系统 PATH，移除 PYTHONHOME/PYTHONPATH；165 个文件与包内 manifest 哈希一致 |
| 实际 EXE 100% 缩放 | 冻结运行通过；P14 签名与默认参数一致，推荐源为 rollout，内部 fallback 为 false；未加载 Tk |
| 实际 EXE 150% / 200% 缩放 | 完整自检通过；窗口使用滚动区域容纳较小逻辑屏幕，截图已检查 |
| 无效数据目录 | 实际 EXE 退出码 1，报告 `data_directory` 错误，没有卡在模态对话框 |
| 规则与参数保护 | 与本轮 P14 基线 manifest 比对，core/ai/record/release 共 35 个记录文件哈希全部一致；旧 Tk 主窗口哈希不变 |

三个缩放级别均运行了 13 项完整流程检查：自定义开局、暂停继续和悔棋计时、单盘恢复、原棋谱读取、四组角色颜色映射、4:0 和 4:3 赛程、整轮恢复不重计分、损坏文件保留、保存失败后重试、未提交超时及自然终局恢复、旧棋谱兼容。每次涵盖 28 次先手映射、11 盘完成与 11 次会话重建；自然终局场景通过 17 步真实合法走法到达终点。

最终交付包在三个缩放级别的推荐源均为 rollout，P14 内部 fallback 均为 false。此前并发回归时有内部截止时间 fallback 的记录留在临时验收目录；最终 JSON 对应上述最终 ZIP，UI 自检不作为棋力或性能结论。

新增恢复边界回归证明：整轮已进入下一盘却只有上一盘残留，以及残留并非最后已结算盘，都在安装状态前拒绝；失败不改会话状态或两份恢复文件。旧规则记录的读取和暂停只读行为有对应覆盖。

主要复现命令：

```powershell
& ".venv/Scripts/python.exe" -m pytest -q --basetemp .pytest-tmp/desktop-phase2-final-v2
& ".venv-desktop/Scripts/python.exe" -m pytest tests/test_desktop_session.py tests/test_desktop_match_session.py tests/test_desktop_flow_acceptance.py tests/test_desktop_qt.py tests/test_desktop_app.py tests/test_desktop_paths.py -q --basetemp .pytest-tmp/desktop-phase2-qt-final
& ".venv-desktop/Scripts/python.exe" scripts/build_desktop.py --output-dir "dist/新的输出目录"
```

实际 EXE 支持 `--self-test "新报告.json" --screenshot "截图.png"`。报告路径必须不存在；自检数据放在独立子目录，不覆盖操作者的恢复文件。构建保持独立子进程 PATH，防止收集其他工具的同名 ICU DLL。

## 验证边界与下一步

当前证据来自开发电脑上的真实 Windows EXE。流程恢复通过写入磁盘后重建会话验证，未模拟断电或在写入中强杀进程；不承诺恢复尚未成功落盘的最后操作。独立无开发环境的 Windows 机器、不同显卡/DPI 及整轮人工演练仍待验收，不能用本轮测试数替代这些检查或赛事方认证。

下一 UI 阶段先完成目标机器演练，重点是实际开局录入、暂停、退出重启、恢复、超时判罚和整轮导出。研究方向仍按 PROJECT_PHASES.md 的同时间上限对照与单因素消融推进；本轮没有新增棋力实验或调整 P14。
