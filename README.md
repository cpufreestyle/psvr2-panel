# PS VR2 PC 控制面板 v4.1.0

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
- ✅ 可滚动画布（界面内容再多不被裁剪）

## 安装

```bash
git clone https://gitee.com/cpufreestyle/psvr2-panel.git
cd psvr2-panel
python main.py
```

或直接运行 `launch.bat`，或下载 `dist/PSVR2-Panel-v4.1.0.exe` 双击运行。

## 系统要求

- Windows 10/11 64位
- Python 3.6+（exe 版本无需 Python）
- tkinter（Python 内置）

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

https://github.com/PSVR2Toolkit

PSVR2Toolkit 是开源项目，免费使用，由 `tinybnuuy` 等开发者历时 5 个月破解。

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