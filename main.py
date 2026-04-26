#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PS VR2 PC 控制面板 — PSVR2 Panel v2.0
一键管理 PS VR2 在 PC 上的解锁功能
集成 PSVR2Toolkit 工具链
作者: Michael Qiu (cpufreestyle)
"""

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import json
import os
import sys
import threading
import time
from pathlib import Path

# ============================================================
# 常量配置
# ============================================================
APP_NAME = "PSVR2 Panel"
APP_VERSION = "2.0.0"
APP_AUTHOR = "Michael Qiu"

# 颜色主题（索尼 PlayStation 风格）
COLORS = {
    "bg_dark": "#003087",
    "bg_light": "#0050C8",
    "accent": "#0070D1",
    "text_white": "#FFFFFF",
    "text_light": "#B0C4DE",
    "green": "#00C853",
    "red": "#FF1744",
    "yellow": "#FFD600",
    "gray": "#424242",
    "card_bg": "#1A237E",
    "card_border": "#283593",
    "success": "#00E676",
}

# PSVR2Toolkit 相关路径
PSVR2_DRIVER_PATHS = [
    r"D:\Program Files (x86)\Steam\steamapps\common\PlayStation VR2 App\SteamVR_Plug-In\bin\win64",
    r"C:\Program Files (x86)\Steam\steamapps\common\PlayStation VR2 App\SteamVR_Plug-In\bin\win64",
]

STEAMVR_PATHS = [
    r"D:\Program Files (x86)\Steam\steamapps\common\SteamVR\bin\win64\vrstartup.exe",
    r"C:\Program Files (x86)\Steam\steamapps\common\SteamVR\bin\win64\vrstartup.exe",
]

VRCFT_PATHS = [
    Path.home() / "AppData" / "Local" / "VRCFaceTracking" / "VRCFaceTracking.exe",
    Path("C:/Program Files/VRCFaceTracking/VRCFaceTracking.exe"),
]

# GitHub 链接
PSVR2TOOLKIT_URL = "https://github.com/BnuuySolutions/PSVR2Toolkit"
VRCFT_MODULE_URL = "https://github.com/BnuuySolutions/PSVR2Toolkit.VRCFT"
VRCFT_DOWNLOAD_URL = "https://github.com/benaclejames/VRCFaceTracking/releases"


# ============================================================
# PS VR2 检测与工具集成
# ============================================================
class PSVR2Toolkit:
    """PSVR2Toolkit 工具集成"""

    def __init__(self):
        self.driver_path = None
        self.driver_installed = False
        self.driver_version = "未知"
        self.steam_path = None

    def find_installation(self):
        """查找 PSVR2Toolkit 驱动安装位置"""
        for path in PSVR2_DRIVER_PATHS:
            driver_dll = os.path.join(path, "driver_playstation_vr2.dll")
            orig_dll = os.path.join(path, "driver_playstation_vr2_orig.dll")

            if os.path.exists(driver_dll):
                self.driver_path = path
                self.driver_installed = True

                # 检查是否有备份文件（表示已安装 toolkit）
                if os.path.exists(orig_dll):
                    # 比较文件大小判断是否是 toolkit 版本
                    driver_size = os.path.getsize(driver_dll)
                    orig_size = os.path.getsize(orig_dll)

                    # Toolkit 版本约 410KB，原版约 3.5MB
                    if driver_size < 500000 and orig_size > 3000000:
                        self.driver_version = "PSVR2Toolkit v0.2.1"
                        return True

                self.driver_version = "官方驱动"
                return True

        return False

    def get_feature_status(self):
        """获取各功能的解锁状态"""
        if not self.driver_installed:
            return {
                "eye_tracking": "需要安装",
                "head_vibration": "需要安装",
                "adaptive_trigger": "需要安装",
                "hdr": "需要安装",
                "haptic_feedback": "需要安装",
                "passthrough": "官方支持",
            }

        if "PSVR2Toolkit" in self.driver_version:
            return {
                "eye_tracking": "已解锁 ✅",
                "head_vibration": "已解锁 ✅",
                "adaptive_trigger": "已解锁 ✅",
                "hdr": "已解锁 ✅",
                "haptic_feedback": "部分可用",
                "passthrough": "官方支持",
            }

        return {
            "eye_tracking": "未解锁",
            "head_vibration": "未解锁",
            "adaptive_trigger": "未解锁",
            "hdr": "未解锁",
            "haptic_feedback": "未解锁",
            "passthrough": "官方支持",
        }

    def find_steam_path(self):
        """查找 Steam 安装路径"""
        steam_paths = [
            r"D:\Program Files (x86)\Steam",
            r"C:\Program Files (x86)\Steam",
            r"D:\Steam",
            r"C:\Steam",
        ]
        for path in steam_paths:
            if os.path.exists(path):
                self.steam_path = path
                return path
        return None


class VRCFaceTrackingIntegration:
    """VRCFaceTracking 集成"""

    def __init__(self):
        self.installed = False
        self.path = None
        self.psvr2_module_installed = False

    def find_installation(self):
        """查找 VRCFaceTracking 安装"""
        for path in VRCFT_PATHS:
            if path.exists():
                self.installed = True
                self.path = str(path)
                return True

        # 尝试在常见位置查找
        appdata_local = Path.home() / "AppData" / "Local"
        for folder in appdata_local.iterdir():
            if "vrcfacetracking" in folder.name.lower():
                exe = folder / "VRCFaceTracking.exe"
                if exe.exists():
                    self.installed = True
                    self.path = str(exe)
                    return True

        return False

    def check_psvr2_module(self):
        """检查 PSVR2 VRCFT 模块是否已安装"""
        if not self.installed:
            return False

        # VRCFT 模块路径
        module_paths = [
            Path.home() / "AppData" / "Roaming" / "VRCFaceTracking" / "Modules",
            Path.home() / "AppData" / "Local" / "VRCFaceTracking" / "Modules",
        ]

        for modules_dir in module_paths:
            if modules_dir.exists():
                for item in modules_dir.iterdir():
                    if "psvr2" in item.name.lower():
                        self.psvr2_module_installed = True
                        return True

        return False

    def launch(self):
        """启动 VRCFaceTracking"""
        if self.path and os.path.exists(self.path):
            subprocess.Popen([self.path])
            return True
        return False


class PSVR2Detector:
    """PS VR2 设备检测"""

    def __init__(self):
        self.connected = False
        self.toolkit = PSVR2Toolkit()
        self.vrcft = VRCFaceTrackingIntegration()
        self.features = {
            "eye_tracking": {"name": "👁️ 眼动追踪", "status": "检测中...", "desc": "VRChat 眼动追踪支持"},
            "head_vibration": {"name": "📳 头显震动", "status": "检测中...", "desc": "头显震动反馈"},
            "adaptive_trigger": {"name": "🎮 自适应扳机", "status": "检测中...", "desc": "Sense 控制器扳机阻力"},
            "hdr": {"name": "🌈 HDR / 10-bit", "status": "检测中...", "desc": "HDR 高动态范围色彩"},
            "haptic_feedback": {"name": "✋ 触觉反馈", "status": "检测中...", "desc": "控制器触觉反馈"},
            "passthrough": {"name": "📷 透视视图", "status": "检测中...", "desc": "摄像头透视模式"},
        }

    def detect_all(self):
        """全面检测"""
        # 检测 PS VR2 连接
        self._detect_connection()

        # 检测 PSVR2Toolkit
        self.toolkit.find_installation()

        # 检测 VRCFaceTracking
        self.vrcft.find_installation()
        self.vrcft.check_psvr2_module()

        # 更新功能状态
        self._update_feature_status()

        return self.connected

    def _detect_connection(self):
        """检测 PS VR2 是否连接"""
        try:
            # 方法1: PowerShell 检查 PnP 设备
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-PnpDevice | Where-Object { $_.FriendlyName -match 'PlayStation|PSVR|VR2' } | "
                 "Select-Object FriendlyName, Status | ConvertTo-Json -Compress"],
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10
            )

            if result.returncode == 0 and result.stdout.strip():
                try:
                    devices = json.loads(result.stdout)
                    if isinstance(devices, dict):
                        devices = [devices]
                    for dev in devices:
                        if dev.get("Status") == "OK":
                            self.connected = True
                            return
                except json.JSONDecodeError:
                    pass

            # 方法2: 检查 SteamVR 是否识别 PS VR2
            if self.toolkit.driver_installed:
                # 如果驱动已安装，假设可能已连接
                self.connected = True

        except (subprocess.TimeoutExpired, Exception):
            pass

    def _update_feature_status(self):
        """更新功能状态"""
        status = self.toolkit.get_feature_status()

        for key, feat in self.features.items():
            if key in status:
                feat["status"] = status[key]


# ============================================================
# GUI 主界面
# ============================================================
class PSVR2Panel:
    """PS VR2 控制面板主界面"""

    def __init__(self):
        self.detector = PSVR2Detector()
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("560x780")
        self.root.resizable(False, False)
        self.root.configure(bg=COLORS["bg_dark"])

        # 状态变量
        self.status_var = tk.StringVar(value="正在检测...")
        self.toolkit_status_var = tk.StringVar(value="检测中...")

        self._build_ui()
        self._run_detection()

    def _build_ui(self):
        """构建界面"""
        # ---- 顶部标题 ----
        header = tk.Frame(self.root, bg=COLORS["bg_dark"])
        header.pack(fill=tk.X, padx=20, pady=(15, 5))

        tk.Label(
            header, text="🎮 PS VR2 Panel",
            font=("Microsoft YaHei", 22, "bold"),
            fg=COLORS["text_white"], bg=COLORS["bg_dark"]
        ).pack(anchor="w")

        tk.Label(
            header, text="PlayStation VR2 PC 控制面板",
            font=("Microsoft YaHei", 10),
            fg=COLORS["text_light"], bg=COLORS["bg_dark"]
        ).pack(anchor="w")

        # ---- 连接状态 ----
        conn_frame = tk.Frame(
            self.root, bg=COLORS["card_bg"],
            highlightbackground=COLORS["card_border"], highlightthickness=1
        )
        conn_frame.pack(fill=tk.X, padx=20, pady=8)

        self.conn_indicator = tk.Label(
            conn_frame, text="●", font=("Arial", 16),
            fg=COLORS["yellow"], bg=COLORS["card_bg"]
        )
        self.conn_indicator.pack(side=tk.LEFT, padx=(12, 5), pady=10)

        tk.Label(
            conn_frame, textvariable=self.status_var,
            font=("Microsoft YaHei", 11),
            fg=COLORS["text_white"], bg=COLORS["card_bg"]
        ).pack(side=tk.LEFT, pady=10)

        tk.Button(
            conn_frame, text="🔄 刷新",
            font=("Microsoft YaHei", 9),
            bg=COLORS["accent"], fg=COLORS["text_white"],
            relief=tk.FLAT, cursor="hand2",
            command=self._run_detection
        ).pack(side=tk.RIGHT, padx=12, pady=10)

        # ---- PSVR2Toolkit 状态 ----
        toolkit_frame = tk.Frame(
            self.root, bg=COLORS["card_bg"],
            highlightbackground=COLORS["card_border"], highlightthickness=1
        )
        toolkit_frame.pack(fill=tk.X, padx=20, pady=4)

        tk.Label(
            toolkit_frame, text="🔧 PSVR2Toolkit:",
            font=("Microsoft YaHei", 10),
            fg=COLORS["text_light"], bg=COLORS["card_bg"]
        ).pack(side=tk.LEFT, padx=(12, 5), pady=8)

        self.toolkit_status_label = tk.Label(
            toolkit_frame, textvariable=self.toolkit_status_var,
            font=("Microsoft YaHei", 10, "bold"),
            fg=COLORS["text_white"], bg=COLORS["card_bg"]
        )
        self.toolkit_status_label.pack(side=tk.LEFT, pady=8)

        tk.Button(
            toolkit_frame, text="📁 打开目录",
            font=("Microsoft YaHei", 8),
            bg=COLORS["accent"], fg=COLORS["text_white"],
            relief=tk.FLAT, cursor="hand2",
            command=self._open_driver_folder
        ).pack(side=tk.RIGHT, padx=12, pady=8)

        # ---- VRCFaceTracking 状态 ----
        vrcft_frame = tk.Frame(
            self.root, bg=COLORS["card_bg"],
            highlightbackground=COLORS["card_border"], highlightthickness=1
        )
        vrcft_frame.pack(fill=tk.X, padx=20, pady=4)

        tk.Label(
            vrcft_frame, text="👀 VRCFaceTracking:",
            font=("Microsoft YaHei", 10),
            fg=COLORS["text_light"], bg=COLORS["card_bg"]
        ).pack(side=tk.LEFT, padx=(12, 5), pady=8)

        self.vrcft_status_label = tk.Label(
            vrcft_frame, text="检测中...",
            font=("Microsoft YaHei", 10, "bold"),
            fg=COLORS["text_white"], bg=COLORS["card_bg"]
        )
        self.vrcft_status_label.pack(side=tk.LEFT, pady=8)

        tk.Button(
            vrcft_frame, text="🚀 启动",
            font=("Microsoft YaHei", 8),
            bg=COLORS["success"], fg=COLORS["text_white"],
            relief=tk.FLAT, cursor="hand2",
            command=self._launch_vrcft
        ).pack(side=tk.RIGHT, padx=(5, 12), pady=8)

        tk.Button(
            vrcft_frame, text="📥 下载",
            font=("Microsoft YaHei", 8),
            bg=COLORS["accent"], fg=COLORS["text_white"],
            relief=tk.FLAT, cursor="hand2",
            command=self._download_vrcft
        ).pack(side=tk.RIGHT, padx=5, pady=8)

        # ---- 功能状态卡片 ----
        tk.Label(
            self.root, text="📊 功能状态",
            font=("Microsoft YaHei", 12, "bold"),
            fg=COLORS["text_white"], bg=COLORS["bg_dark"]
        ).pack(anchor="w", padx=25, pady=(15, 5))

        self.feature_frames = {}
        for key, feat in self.detector.features.items():
            frame = self._create_feature_card(key, feat)
            self.feature_frames[key] = frame

        # ---- 底部操作区 ----
        bottom = tk.Frame(self.root, bg=COLORS["bg_dark"])
        bottom.pack(fill=tk.X, padx=20, pady=(15, 20), side=tk.BOTTOM)

        # SteamVR 按钮
        tk.Button(
            bottom, text="🥽 启动 SteamVR",
            font=("Microsoft YaHei", 13, "bold"),
            bg=COLORS["accent"], fg=COLORS["text_white"],
            relief=tk.FLAT, cursor="hand2", height=2,
            command=self._launch_steamvr
        ).pack(fill=tk.X, pady=(0, 8))

        # 工具链按钮
        tools_frame = tk.Frame(bottom, bg=COLORS["bg_dark"])
        tools_frame.pack(fill=tk.X)

        tk.Button(
            tools_frame, text="📦 PSVR2Toolkit",
            font=("Microsoft YaHei", 9),
            bg=COLORS["card_bg"], fg=COLORS["text_white"],
            relief=tk.FLAT, cursor="hand2",
            command=self._open_toolkit_github
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))

        tk.Button(
            tools_frame, text="🔌 VRCFT 模块",
            font=("Microsoft YaHei", 9),
            bg=COLORS["card_bg"], fg=COLORS["text_white"],
            relief=tk.FLAT, cursor="hand2",
            command=self._open_vrcft_module
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)

        tk.Button(
            tools_frame, text="ℹ️ 关于",
            font=("Microsoft YaHei", 9),
            bg=COLORS["card_bg"], fg=COLORS["text_white"],
            relief=tk.FLAT, cursor="hand2",
            command=self._show_about
        ).pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(4, 0))

    def _create_feature_card(self, key, feat):
        """创建功能卡片"""
        frame = tk.Frame(
            self.root, bg=COLORS["card_bg"],
            highlightbackground=COLORS["card_border"], highlightthickness=1
        )
        frame.pack(fill=tk.X, padx=20, pady=2)

        # 左侧：图标+名称
        left = tk.Frame(frame, bg=COLORS["card_bg"])
        left.pack(side=tk.LEFT, padx=(12, 5), pady=6)

        tk.Label(
            left, text=feat["name"],
            font=("Microsoft YaHei", 10),
            fg=COLORS["text_white"], bg=COLORS["card_bg"]
        ).pack(anchor="w")

        tk.Label(
            left, text=feat["desc"],
            font=("Microsoft YaHei", 8),
            fg=COLORS["text_light"], bg=COLORS["card_bg"]
        ).pack(anchor="w")

        # 右侧：状态
        status_label = tk.Label(
            frame, text=feat["status"],
            font=("Microsoft YaHei", 9, "bold"),
            fg=COLORS["text_white"], bg=COLORS["card_bg"]
        )
        status_label.pack(side=tk.RIGHT, padx=12, pady=6)

        return {"frame": frame, "status_label": status_label}

    def _status_color(self, status):
        """状态颜色"""
        if "已解锁" in status or "官方支持" in status:
            return COLORS["green"]
        elif "未解锁" in status or "需要安装" in status:
            return COLORS["red"]
        elif "部分" in status:
            return COLORS["yellow"]
        return COLORS["gray"]

    def _run_detection(self):
        """后台检测"""
        self.status_var.set("正在检测...")
        self.conn_indicator.config(fg=COLORS["yellow"])

        def detect():
            connected = self.detector.detect_all()
            self.root.after(0, self._update_ui, connected)

        threading.Thread(target=detect, daemon=True).start()

    def _update_ui(self, connected):
        """更新 UI"""
        # 连接状态
        if connected:
            self.status_var.set("✅ PS VR2 已连接")
            self.conn_indicator.config(fg=COLORS["green"])
        else:
            self.status_var.set("❌ PS VR2 未检测到")
            self.conn_indicator.config(fg=COLORS["red"])

        # PSVR2Toolkit 状态
        toolkit = self.detector.toolkit
        if toolkit.driver_installed:
            self.toolkit_status_var.set(f"✅ {toolkit.driver_version}")
            self.toolkit_status_label.config(fg=COLORS["green"])
        else:
            self.toolkit_status_var.set("❌ 未安装")
            self.toolkit_status_label.config(fg=COLORS["red"])

        # VRCFaceTracking 状态
        vrcft = self.detector.vrcft
        if vrcft.installed:
            if vrcft.psvr2_module_installed:
                self.vrcft_status_label.config(text="✅ 已安装模块", fg=COLORS["green"])
            else:
                self.vrcft_status_label.config(text="⚠️ 缺少 PSVR2 模块", fg=COLORS["yellow"])
        else:
            self.vrcft_status_label.config(text="❌ 未安装", fg=COLORS["red"])

        # 功能状态
        for key, frame in self.feature_frames.items():
            feat = self.detector.features[key]
            frame["status_label"].config(
                text=feat["status"],
                fg=self._status_color(feat["status"])
            )

    def _launch_steamvr(self):
        """启动 SteamVR"""
        for path in STEAMVR_PATHS:
            if os.path.exists(path):
                subprocess.Popen([path])
                messagebox.showinfo("SteamVR", "SteamVR 已启动！")
                return

        # 通过 Steam 协议启动
        try:
            os.startfile("steam://rungameid/250820")
            messagebox.showinfo("SteamVR", "正在通过 Steam 启动...")
        except Exception:
            messagebox.showwarning("未找到", "未检测到 SteamVR 安装")

    def _launch_vrcft(self):
        """启动 VRCFaceTracking"""
        if self.detector.vrcft.launch():
            messagebox.showinfo("VRCFaceTracking", "VRCFaceTracking 已启动！")
        else:
            messagebox.showwarning("未安装", "VRCFaceTracking 未安装\n\n请点击「下载」按钮获取")

    def _download_vrcft(self):
        """打开 VRCFaceTracking 下载页"""
        os.startfile(VRCFT_DOWNLOAD_URL)

    def _open_driver_folder(self):
        """打开驱动目录"""
        path = self.detector.toolkit.driver_path
        if path and os.path.exists(path):
            os.startfile(path)
        else:
            messagebox.showinfo("提示", "未找到 PSVR2 驱动目录")

    def _open_toolkit_github(self):
        """打开 PSVR2Toolkit GitHub"""
        os.startfile(PSVR2TOOLKIT_URL)

    def _open_vrcft_module(self):
        """打开 VRCFT 模块页面"""
        os.startfile(VRCFT_MODULE_URL)

    def _show_about(self):
        """关于"""
        messagebox.showinfo(
            f"关于 {APP_NAME}",
            f"{APP_NAME} v{APP_VERSION}\n\n"
            f"PS VR2 PC 控制面板\n"
            f"集成 PSVR2Toolkit 工具链\n\n"
            f"功能：\n"
            f"• 检测 PS VR2 连接状态\n"
            f"• 管理 PSVR2Toolkit 功能\n"
            f"• 集成 VRCFaceTracking 眼动追踪\n"
            f"• 一键启动 SteamVR\n\n"
            f"作者: {APP_AUTHOR}\n"
            f"https://gitee.com/cpufreestyle/psvr2-panel"
        )

    def run(self):
        """启动"""
        self.root.mainloop()


if __name__ == "__main__":
    app = PSVR2Panel()
    app.run()
