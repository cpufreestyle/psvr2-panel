# PS VR2 PC 控制面板 v4.6.0

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/Python-3.6+-green.svg)](https://www.python.org/downloads/)

PlayStation VR2 PC 管理工具，一键解锁 PS VR2 在 PC 上的隐藏功能。

## 功能

- ✅ 检测 PS VR2 连接状态（USB PnP 设备识别）
- ✅ 驱动一键切换（官方 ↔ PSVR2Toolkit）
- ✅ 驱动备份/恢复（时间戳快照管理）
- ✅ SteamVR 快速设置（渲染缩放/超采样/运动平滑）
- ✅ SteamVR / VRCFaceTracking 进程监控
- ✅ 一键启动 SteamVR + VRCFaceTracking
- ✅ VRCFaceTracking Steam 安装入口
- ✅ GitHub 驱动更新检查
- ✅ 设备信息面板（USB 连接详情）
- ✅ PlayStation 风格深色主题 UI
- ✅ **系统托盘**（最小化到托盘，后台运行，右键菜单）
- ✅ **开机启动**（Windows 注册表 Run 项）
- ✅ **一键安装 PSVR2Toolkit**（自动从 GitHub 下载）
- ✅ **一键关闭 SteamVR**（配合驱动切换工作流）
- ✅ **驱动操作容错**（SteamVR 运行中文件占用时友好提示）
- ✅ **备份自动清理**（自动保留最近 5 份）
- ✅ **一键健康检查**（驱动/连接/运行时/备份/自启状态诊断报告，自动复制）
- ✅ **VRCFT 升级管理**（版本检查 / 一键下载安装包）
- ✅ **VRCFT 眼动模块一键部署**（PSVR2Toolkit.VRCFT，用于 VRChat 眼动追踪）
- ✅ **Steam 路径自动检测**（注册表 + 多库扫描，告别硬编码盘符）
- ✅ 可滚动画布（界面内容再多不被裁剪）

## 安装

### 🎯 推荐：直接下载 exe（无需 Python）

前往 [GitHub Releases](https://github.com/cpufreestyle/psvr2-panel/releases) 下载最新版本的 `PSVR2-Panel-v4.6.0.exe`，双击即可运行。

### 💻 从源码运行

```bash
git clone https://github.com/cpufreestyle/psvr2-panel.git
cd psvr2-panel
pip install -r requirements.txt
python main.py
```

或直接运行 `launch.bat`。

## 📸 截图

> 截图待添加（请在 [Issues](https://github.com/cpufreestyle/psvr2-panel/issues) 中提交截图）

## 系统要求

- Windows 10/11 64位
- Python 3.6+（exe 版本无需 Python）
- tkinter（Python 内置）

## v4.6.0 更新

| 类别 | 更新内容 |
|------|---------|
| 🐛 Bug | 修复 PSVR2Toolkit API 地址失效（仓库已迁移至 BnuuySolutions/PSVR2Toolkit），版本检查与一键安装恢复可用 |
| 🧩 模块 | 新增 VRCFT 眼动模块一键下载部署（BnuuySolutions/PSVR2Toolkit.VRCFT），模块安装状态实时显示 |
| 📂 检测 | Steam 路径注册表自动检测（HKLM InstallPath + libraryfolders.vdf 多库扫描，保留硬编码回退） |
| 🍱 托盘 | 托盘菜单新增切换驱动 / 关闭 SteamVR / 健康检查快捷项 |
| 🩺 诊断 | 健康检查新增 VRCFT 眼动模块状态与 Toolkit 最新版本信息 |

## v4.5.0 更新

| 类别 | 更新内容 |
|------|---------|
| ⏹ 启动 | 新增一键关闭 SteamVR；驱动切换前自动检测 SteamVR 运行状态并提示 |
| 🛡 稳定性 | 驱动切换/备份/恢复支持文件占用容错（SteamVR 运行中给出友好提示，不再崩溃） |
| 🧹 备份 | 驱动备份自动清理，保留最近 5 份 |
| ⚡ 性能 | 监控降载：连接检测降至约 20 秒一次（原 3 秒），进程检测保持 3 秒 |

## v4.4.0 更新

| 类别 | 更新内容 |
|------|---------|
| 🩺 诊断 | 一键健康检查：驱动/连接/运行时/VRCFT/备份/自启/设置文件状态汇总，报告自动复制到剪贴板 |
| ⬆️ VRCFT | VRCFT 在线升级管理：本地版本读取、GitHub 最新版检查、安装包下载并启动 |

## v4.3.0 更新

| 类别 | 更新内容 |
|------|---------|
| 🐛 Bug | 修复 `PROFILE_DIR` 未定义的致命 Bug |
| 📦 规范 | 新增 `.gitignore` 完善 / `requirements.txt` 整理 |
| 📝 文档 | README 添加 Badges、exe 下载链接、截图占位 |

## v4.2.0 更新

| 类别 | 更新内容 |
|------|---------|
| 🎨 UI | PlayStation 风格深色主题 UI / 分 Tab 布局 |
| 🔧 驱动 | PSVR2Toolkit 驱动一键切换 |
| 💾 备份 | 驱动备份/恢复（时间戳快照） |
| ⚙️ SteamVR | 渲染缩放/超采样/运动平滑快速设置 |
| 🚀 启动 | SteamVR / VRCFaceTracking 一键启动 |
| 🔍 更新 | GitHub 版本检查 |

## v4.1.0 更新

| 类别 | 更新内容 |
|------|---------|
| 🐛 Bug | `toolable_active` 拼写修正 / 时间戳健壮解析 / 清理未用导入 |
| 🪶 托盘 | 关闭按钮最小化到系统托盘，后台运行，右键菜单（显示/刷新/退出） |
| ⚡ 启动 | Windows 开机自动启动开关（注册表 Run 项） |
| 📜 界面 | 可滚动画布，内容再多也不被裁剪 |
| ⬇️ 安装 | 一键从 GitHub 下载安装 PSVR2Toolkit，无需手动操作 |

## v4.0.0 更新

| 类别 | 更新内容 |
|------|---------|
| 🎨 UI | 现代化深色主题 / 分 Tab 布局 / 卡片式设计 |
| 💾 驱动管理 | 备份/恢复时间戳快照，历史版本可回滚 |
| ⚙️ SteamVR | 渲染缩放/超采样/运动平滑快速设置面板 |
| ⚡ 性能 | tasklist 替代 PowerShell，单线程监控 |
| 🔧 代码 | 日志系统、类型提示、无重复导入 |
| 📊 设备 | USB 连接详情（设备名称/状态/ID） |

## PSVR2Toolkit

要解锁眼动追踪、头显震动、HDR 等功能，需要安装 PSVR2Toolkit：

https://github.com/BnuuySolutions/PSVR2Toolkit

PSVR2Toolkit 是开源项目（Bnuuy Solutions），免费使用，由 `meowybnuuy` 等开发者破解。

## 功能对照表

| 功能 | 官方适配器 | PSVR2Toolkit |
|------|-----------|--------------|
| 4K 画面 | ✅ | ✅ |
| 110° 视野 | ✅ | ✅ |
| 透视视图 | ✅ | ✅ |
| 3D 音效 | ✅ | ✅ |
| HDR | ❌ | ✅ 已解锁 10-bit |
| 眼动追踪 | ❌ | ✅ |
| 头显震动 | ❌ | ✅ |
| 自适应扳机 | ❌ | ✅ |
| 触觉反馈 | ❌ 部分 | ✅ |

## 作者

Michael Qiu (cpufreestyle)

## 许可证

MIT License