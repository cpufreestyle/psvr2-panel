# PS VR2 PC 控制面板 v4.0.0

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

## 截图

![PSVR2 Panel](screenshot.png)

## 安装

```bash
# 克隆仓库
git clone https://gitee.com/cpufreestyle/psvr2-panel.git

# 进入目录
cd psvr2-panel

# 安装依赖
pip install -r requirements.txt

# 运行
python main.py
```

或直接运行 `launch.bat`

## 系统要求

- Windows 10/11 64位
- Python 3.6+
- tkinter（Python 内置）

## v4.0.0 更新

| 类别 | 更新内容 |
|------|---------|
| 🎨 UI | 现代化深色主题 / 分 Tab 布局 / 卡片式设计 |
| 💾 驱动管理 | 备份/恢复时间戳快照，历史版本可回滚 |
| ⚙️ SteamVR | 渲染缩放/超采样/运动平滑快速设置面板 |
| ⚡ 性能 | tasklist 替代 PowerShell，单线程监控 |
| 🔧 代码 | 日志系统、类型提示、无重复导入 |
| 📊 设备 | USB 连接详情（设备名称/状态/ID） |

## v3.x 更新

- **v3.2**: 移除 GitHub 下载按钮（项目已停止维护），保留 Steam 安装渠道
- **v3.1**: 驱动一键切换 / 内置 VRCFaceTracking 自动部署 / SteamVR 进程监控 / GitHub 驱动更新检查 / 一键启动全部工具

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
