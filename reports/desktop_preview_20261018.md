# PySide6 UI 效果稿与便携 EXE 样机

日期：2026-10-18。范围：用户确认的新版界面效果稿和最小可运行 EXE，旧 Tk 界面保留。

## 交付

- [交互效果稿](../docs/ui/desktop-preview.html)：离线、自包含 HTML，标明示例状态，不伪装真实 AI 输出。
- [实际 EXE 截图](../docs/ui/desktop-prototype.png)：来自最终便携包，Windows Qt 平台插件，真实 P14 推荐。
- [使用说明](../docs/DESKTOP_PREVIEW.md)。
- EXE：`E:\computergame\dist\desktop-preview-0.1.0-20261018-portable\EinsteinChess-preview\EinsteinChess.exe`。
- ZIP：`E:\computergame\dist\desktop-preview-0.1.0-20261018-portable\EinsteinChess-preview-windows-x64.zip`。

ZIP 为 **37,436,223 bytes（约 35.7 MiB）**，解压程序目录 **96,518,837 bytes（约 92.0 MiB）**。必须保留 EXE 同级 `_internal`；发布包不包含用户棋谱或测试数据。

ZIP SHA-256：`EFA5F58629CC3D9C5D810C295C418C638CDE80B945F3D59C42B6249D69F408F9`。

## 实现范围

新增独立 `desktop_qt/`，提供可缩放自绘棋盘、骰子输入/随机掷骰、合法走法选择与执行、P14 后台推荐与应用、棋谱列表、单盘保存/读取、撤销和未保存提醒。小窗口通过滚动区域访问全部内容。

`GameSession` 复用 core 与 GameRecord；GUI 不复制规则。新窗口默认 P14 和回退 AI 均使用与旧窗口一致的 `seed=0`，P14 显式参数直接读取现有 release 默认值。推荐使用原有单工作器，保留 revision、generation、局面/骰子 key 校验；关闭不等待正在运行的搜索。

三个显示格式函数原样移入 `gui/formatting.py`，旧 `gui.app` 继续重导出；后台工作器仅改变 formatter 导入位置，从而不为新 EXE 引入 Tk。`core/`、`ai/`、`record/`、旧 `gui/main_window.py` 与 P14 release 配置没有因本轮改变。

便携数据默认在 EXE 同级 `user-data/records` 与 `user-data/logs`，不依赖当前工作目录。源码模式使用仓库 ignored 的 `user-data/desktop-preview`。无效或不可写数据目录明确失败；日志轮转；自检错误不弹隐藏模态框。

## 验证

| 检查 | 实际结果 |
|---|---|
| 原开发环境全量回归 | `1428 passed, 1 skipped in 90.59s`；Qt 模块在不含 Qt 的原 `.venv` 中跳过 |
| 最终桌面环境专项 | `37 passed in 3.44s`；包括 Qt 窗口、会话、路径和自检保存失败路径 |
| 效果稿视觉/交互 | 1200×850、390px 窄屏验证；25 格、12 子、骰子演示正确 |
| Qt 小屏 | 1020×700、800×500 的滚动可达性回归通过 |
| 真实 Windows 源码自检 | P14 主推荐、合法走子、原 GameRecord 读取、GUI 加载及撤销通过，退出码 0 |
| 最终 ZIP 解压自检 | 新中文含空格目录，切换到无关工作目录；PATH 仅含 System32，清除 PYTHONHOME/PYTHONPATH；实际 EXE 退出码 0 |
| 冻结验证 | `frozen=true`、推荐来源 `rollout`、实际 AI 签名匹配 P14、未导入 Tk、棋谱往返/撤销通过 |
| 实际 EXE 缩放 | Windows 平台插件，100%、150%、200% 的自检通过并检查截图；高缩放时用滚动区域访问完整内容 |
| 无效数据目录 | 实际 EXE 返回 1，并写入 `stage=data_directory` 的 failed 报告，原文件保留 |
| 数据位置 | 出现在解压 EXE 同级 user-data，无关工作目录没有 user-data |
| 差异检查 | `git diff --check` 通过 |

[冻结 EXE 自检记录](desktop_preview_20261018_selftest.json) 保存完整签名和检查结果。测试只在本机 Windows 执行；清除环境变量不等于一台从未安装 Python 的干净系统，独立机器/虚拟机验收仍待后续完成。

打包初测实际发现启动前 `QtCore` DLL 加载失败。诊断构建确认 PyInstaller 从调用环境 PATH 中误收了其他工具的 `icuuc.dll`（Poppler ICU 78），与 Windows Qt 所需接口不符。构建脚本现仅为构建子进程设置受控 PATH，排除无关工具；最终包不再包含该外来 ICU，真实解压运行通过。没有修改系统 PATH、安装系统运行库或降低校验条件。

## 构建与环境

独立 `.venv-desktop`：Python 3.11.9、PySide6-Essentials/shiboken6 6.12.0、PyInstaller 6.22.3、hooks 2026.8。原 `.venv` 与研究依赖不变。构建依赖固定在 `requirements-desktop-build-lock.txt`，缓存使用 `E:\pip-cache`。

```powershell
& ".venv-desktop/Scripts/python.exe" "scripts/run_desktop.py"
& ".venv-desktop/Scripts/python.exe" "scripts/build_desktop.py"
```

构建脚本使用新目录，生成 EXE、依赖、说明、许可文本、文件哈希清单和 ZIP。只用于诊断时可设置进程环境变量 `CG_DESKTOP_CONSOLE=1`；正式包不显示控制台。最终交付只使用上述 `portable` 目录，其他构建保留为调试产物。

默认参数文件哈希仍为 `B83EB34EBFCF5C753FB6B16C99E8812CE8714D7C15979BD34B6ED31392508916`；core 规则文件哈希 `97FB2CBC4D58173C2D483D85CEA90D680F9B674D55A760B1F77B1A855149C135`；GameRecord 文件哈希 `734DFA15708176FE0433A158BB11B37EF02ECAC3BF51048A603F5EB190C5F4E3`，均与本轮开始时一致。

## 尚未迁移

本版是单盘样机，未实现自定义开局编辑、七盘制、完整比赛计时与崩溃自动恢复；这些继续使用旧 Tk 界面。没有发布网站、自动更新、签名安装器、训练或棋力晋升。用户确认界面方向后，下一阶段迁移这些完整流程，再做独立干净 Windows 验收。

本轮没有提交、推送或创建分支；此前未提交的审查和评测改动保留。
