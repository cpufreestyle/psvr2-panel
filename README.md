# PS VR2 PC 控制面板 v3.2

PlayStation VR2 PC 管理工具，一键解锁 PS VR2 在 PC 上的隐藏功能。

## 功能

- ✅ 检测 PS VR2 连接状态
- ✅ 驱动一键切换 (官方 ↔ PSVR2Toolkit)
- ✅ 显示功能解锁状态（眼动追踪、头显震动、HDR等）
- ✅ 一键启动 SteamVR / VRCFaceTracking
- ✅ VRCFaceTracking Steam 安装入口（推荐）
- ✅ SteamVR / VRCFT 进程监控
- ✅ GitHub 驱动更新检查
- ✅ PlayStation 蓝色主题界面

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
- PS VR2 头显 + 官方 PC 适配器（可选）

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