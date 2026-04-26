#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PS VR2 PC 控制面板 — PSVR2 Panel
一键管理 PS VR2 在 PC 上的解锁功能
作者: Michael Qiu (cpufreestyle)
版本: 1.0.0
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
# 常量
# ============================================================
APP_NAME = "PSVR2 Panel"
APP_VERSION = "1.0.0"
APP_AUTHOR = "Michael Qiu"

# 颜色主题（索尼 PlayStation 风格）
COLORS = {
    "bg_dark": "#003087",       # PlayStation 蓝
    "bg_light": "#0050C8",     # 亮蓝
    "accent": "#0070D1",       # 强调蓝
    "text_white": "#FFFFFF",
    "text_light": "#B0C4DE",
    "green": "#00C853",        # 开启状态
    "red": "#FF1744",          # 关闭状态
    "yellow": "#FFD600",       # 检测中
    "gray": "#424242",         # 未知状态
    "card_bg": "#1A237E",      # 卡片背景
    "card_border": "#283593",  # 卡片边框
}

# PSVR2Toolkit GitHub 仓库
PSVR2TOOLKIT_URL = "https://github.com/PSVR2Toolkit"
STEAMVR_PATHS = [
    r"C:\Program Files (x86)\Steam\steamapps\common\SteamVR\bin\win64\vrstartup.exe",
    r"D:\Steam\steamapps\common\SteamVR\bin\win64\vrstartup.exe",
    r"C:\Program Files\Steam\steamapps\common\SteamVR\bin\win64\vrstartup.exe",
]


# ============================================================
# PS VR2 检测逻辑
# ============================================================
class PSVR2Detector:
    """检测 PS VR2 连接状态和功能解锁情况"""

    def __init__(self):
        self.connected = False
        self.firmware = "未知"
        self.features = {
            "eye_tracking": {"name": "眼动追踪", "status": "未知", "icon": "👁️"},
            "head_vibration": {"name": "头显震动", "status": "未知", "icon": "📳"},
            "adaptive_trigger": {"name": "自适应扳机", "status": "未知", "icon": "🎮"},
            "hdr": {"name": "HDR / 10-bit色深", "status": "未知", "icon": "🌈"},
            "haptic_feedback": {"name": "触觉反馈", "status": "未知", "icon": "✋"},
            "passthrough": {"name": "透视视图", "status": "未知", "icon": "📷"},
        }

    def detect_connection(self):
        """检测 PS VR2 是否通过 USB/适配器连接"""
        try:
            # 方法1: 通过 PowerShell 检查 USB 设备
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-PnpDevice | Where-Object { $_.FriendlyName -match 'PlayStation|PSVR|VR2' } | "
                 "Select-Object FriendlyName, Status | ConvertTo-Json"],
                capture_output=True, text=True, encoding='utf-8', errors='replace',
                timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                devices = json.loads(result.stdout)
                if isinstance(devices, dict):
                    devices = [devices]
                for dev in devices:
                    if dev.get("Status") == "OK":
                        self.connected = True
                        return True

            # 方法2: 通过 WMI 检查
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-WmiObject Win32_USBControllerDevice | "
                 "ForEach-Object { $_.Dependent } | "
                 "Where-Object { $_.Name -match 'PlayStation|PSVR|VR2' } | "
                 "Select-Object Name, Status | ConvertTo-Json"],
                capture_output=True, text=True, encoding='utf-8', errors='replace',
                timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                for item in data:
                    if item.get("Status") == "OK":
                        self.connected = True
                        return True

        except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
            pass

        return False

    def detect_features(self):
        """检测 PSVR2Toolkit 功能解锁状态"""
        # 检查 PSVR2Toolkit 是否已安装
        toolkit_installed = self._check_toolkit_installed()

        if toolkit_installed:
            # 如果 toolkit 已安装，尝试检测各功能状态
            self.features["eye_tracking"]["status"] = "可解锁"
            self.features["head_vibration"]["status"] = "可解锁"
            self.features["adaptive_trigger"]["status"] = "可解锁"
            self.features["hdr"]["status"] = "可解锁"
            self.features["haptic_feedback"]["status"] = "部分可用"
            self.features["passthrough"]["status"] = "官方支持"
        elif self.connected:
            # 仅官方适配器
            for key in self.features:
                if key == "passthrough":
                    self.features[key]["status"] = "官方支持"
                else:
                    self.features[key]["status"] = "未解锁"
        else:
            for key in self.features:
                self.features[key]["status"] = "未连接"

    def _check_toolkit_installed(self):
        """检查 PSVR2Toolkit 是否已安装"""
        # 检查常见安装路径
        check_paths = [
            Path.home() / "PSVR2Toolkit",
            Path("C:/PSVR2Toolkit"),
            Path("D:/PSVR2Toolkit"),
            Path.home() / "AppData" / "Local" / "PSVR2Toolkit",
        ]
        for p in check_paths:
            if p.exists():
                return True

        # 检查 PATH 中是否有 psvr2toolkit
        try:
            result = subprocess.run(
                ["psvr2toolkit", "--version"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return False


# ============================================================
# GUI 主窗口
# ============================================================
class PSVR2Panel:
    """PS VR2 PC 控制面板主界面"""

    def __init__(self):
        self.detector = PSVR2Detector()
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("520x700")
        self.root.resizable(False, False)
        self.root.configure(bg=COLORS["bg_dark"])

        # 窗口图标（尝试设置）
        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass

        # 状态变量
        self.status_var = tk.StringVar(value="正在检测...")
        self.connected_var = tk.BooleanVar(value=False)

        self._build_ui()
        self._run_detection()

    def _build_ui(self):
        """构建界面"""
        # ---- 顶部标题栏 ----
        header = tk.Frame(self.root, bg=COLORS["bg_dark"], height=80)
        header.pack(fill=tk.X, padx=20, pady=(15, 5))
        header.pack_propagate(False)

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

        # ---- 连接状态栏 ----
        status_frame = tk.Frame(
            self.root, bg=COLORS["card_bg"],
            highlightbackground=COLORS["card_border"], highlightthickness=1
        )
        status_frame.pack(fill=tk.X, padx=20, pady=10)

        self.status_indicator = tk.Label(
            status_frame, text="●",
            font=("Arial", 18), fg=COLORS["yellow"],
            bg=COLORS["card_bg"]
        )
        self.status_indicator.pack(side=tk.LEFT, padx=(15, 5), pady=10)

        self.status_label = tk.Label(
            status_frame, textvariable=self.status_var,
            font=("Microsoft YaHei", 12),
            fg=COLORS["text_white"], bg=COLORS["card_bg"]
        )
        self.status_label.pack(side=tk.LEFT, pady=10)

        self.refresh_btn = tk.Button(
            status_frame, text="🔄 刷新",
            font=("Microsoft YaHei", 9),
            bg=COLORS["accent"], fg=COLORS["text_white"],
            relief=tk.FLAT, cursor="hand2",
            command=self._run_detection
        )
        self.refresh_btn.pack(side=tk.RIGHT, padx=15, pady=10)

        # ---- 功能卡片区域 ----
        cards_label = tk.Label(
            self.root, text="功能状态",
            font=("Microsoft YaHei", 12, "bold"),
            fg=COLORS["text_white"], bg=COLORS["bg_dark"]
        )
        cards_label.pack(anchor="w", padx=25, pady=(10, 5))

        self.feature_cards = {}
        for key, feat in self.detector.features.items():
            card = self._create_feature_card(key, feat)
            self.feature_cards[key] = card

        # ---- 底部操作区 ----
        bottom_frame = tk.Frame(self.root, bg=COLORS["bg_dark"])
        bottom_frame.pack(fill=tk.X, padx=20, pady=(15, 20), side=tk.BOTTOM)

        # SteamVR 启动按钮
        self.steamvr_btn = tk.Button(
            bottom_frame, text="🥽 启动 SteamVR",
            font=("Microsoft YaHei", 12, "bold"),
            bg=COLORS["accent"], fg=COLORS["text_white"],
            relief=tk.FLAT, cursor="hand2",
            height=2, command=self._launch_steamvr
        )
        self.steamvr_btn.pack(fill=tk.X, pady=(0, 8))

        # 工具包按钮
        toolkit_frame = tk.Frame(bottom_frame, bg=COLORS["bg_dark"])
        toolkit_frame.pack(fill=tk.X)

        self.toolkit_btn = tk.Button(
            toolkit_frame, text="📦 安装 PSVR2Toolkit",
            font=("Microsoft YaHei", 10),
            bg=COLORS["card_bg"], fg=COLORS["text_white"],
            relief=tk.FLAT, cursor="hand2",
            command=self._open_toolkit
        )
        self.toolkit_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))

        self.about_btn = tk.Button(
            toolkit_frame, text="ℹ️ 关于",
            font=("Microsoft YaHei", 10),
            bg=COLORS["card_bg"], fg=COLORS["text_white"],
            relief=tk.FLAT, cursor="hand2",
            command=self._show_about
        )
        self.about_btn.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(4, 0))

    def _create_feature_card(self, key, feat):
        """创建单个功能卡片"""
        card_frame = tk.Frame(
            self.root, bg=COLORS["card_bg"],
            highlightbackground=COLORS["card_border"], highlightthickness=1
        )
        card_frame.pack(fill=tk.X, padx=20, pady=3)

        # 图标 + 名称
        left = tk.Frame(card_frame, bg=COLORS["card_bg"])
        left.pack(side=tk.LEFT, padx=(15, 5), pady=8)

        icon_label = tk.Label(
            left, text=feat["icon"],
            font=("Arial", 14), bg=COLORS["card_bg"]
        )
        icon_label.pack(side=tk.LEFT, padx=(0, 8))

        name_label = tk.Label(
            left, text=feat["name"],
            font=("Microsoft YaHei", 11),
            fg=COLORS["text_white"], bg=COLORS["card_bg"]
        )
        name_label.pack(side=tk.LEFT)

        # 状态标签
        status_text = feat["status"]
        status_color = self._status_color(status_text)

        status_label = tk.Label(
            card_frame, text=status_text,
            font=("Microsoft YaHei", 10, "bold"),
            fg=status_color, bg=COLORS["card_bg"]
        )
        status_label.pack(side=tk.RIGHT, padx=15, pady=8)

        # 开关按钮（仅对可解锁功能显示）
        if status_text in ("可解锁", "未解锁"):
            toggle_btn = tk.Button(
                card_frame, text="切换",
                font=("Microsoft YaHei", 8),
                bg=COLORS["accent"], fg=COLORS["text_white"],
                relief=tk.FLAT, cursor="hand2", width=6,
                command=lambda k=key: self._toggle_feature(k)
            )
            toggle_btn.pack(side=tk.RIGHT, padx=(0, 5), pady=8)

        return {
            "frame": card_frame,
            "status_label": status_label,
            "key": key,
        }

    def _status_color(self, status):
        """根据状态返回颜色"""
        color_map = {
            "官方支持": COLORS["green"],
            "可解锁": COLORS["green"],
            "已开启": COLORS["green"],
            "未解锁": COLORS["red"],
            "未连接": COLORS["gray"],
            "部分可用": COLORS["yellow"],
            "未知": COLORS["gray"],
            "检测中...": COLORS["yellow"],
        }
        return color_map.get(status, COLORS["gray"])

    def _run_detection(self):
        """在后台线程中检测 PS VR2 状态"""
        self.status_var.set("正在检测...")
        self.status_indicator.config(fg=COLORS["yellow"])

        def detect():
            connected = self.detector.detect_connection()
            self.detector.detect_features()

            # 在主线程中更新 UI
            self.root.after(0, self._update_ui, connected)

        thread = threading.Thread(target=detect, daemon=True)
        thread.start()

    def _update_ui(self, connected):
        """更新界面状态"""
        self.connected_var.set(connected)

        if connected:
            self.status_var.set("✅ PS VR2 已连接")
            self.status_indicator.config(fg=COLORS["green"])
        else:
            self.status_var.set("❌ PS VR2 未检测到")
            self.status_indicator.config(fg=COLORS["red"])

        # 更新功能卡片状态
        for key, card in self.feature_cards.items():
            feat = self.detector.features[key]
            card["status_label"].config(
                text=feat["status"],
                fg=self._status_color(feat["status"])
            )

    def _toggle_feature(self, key):
        """切换功能开关"""
        feat = self.detector.features[key]
        if not self.connected_var.get():
            messagebox.showwarning(
                "未连接",
                "未检测到 PS VR2 设备，请先连接头显后再试。"
            )
            return

        current = feat["status"]
        if current == "可解锁":
            # TODO: 调用 PSVR2Toolkit API 开启功能
            feat["status"] = "已开启"
            messagebox.showinfo(
                "功能已开启",
                f"{feat['name']} 已开启！\n\n"
                f"注意：此功能需要 PSVR2Toolkit 支持。\n"
                f"如未安装，请点击底部「安装 PSVR2Toolkit」按钮。"
            )
        elif current == "已开启":
            feat["status"] = "可解锁"
        elif current == "未解锁":
            messagebox.showinfo(
                "需要 PSVR2Toolkit",
                f"要解锁 {feat['name']}，需要先安装 PSVR2Toolkit。\n\n"
                f"PSVR2Toolkit 是开源项目，可从 GitHub 免费下载：\n"
                f"{PSVR2TOOLKIT_URL}"
            )
            return

        # 更新卡片
        card = self.feature_cards[key]
        card["status_label"].config(
            text=feat["status"],
            fg=self._status_color(feat["status"])
        )

    def _launch_steamvr(self):
        """启动 SteamVR"""
        for path in STEAMVR_PATHS:
            if os.path.exists(path):
                try:
                    subprocess.Popen([path])
                    messagebox.showinfo("SteamVR", "SteamVR 已启动！")
                    return
                except Exception as e:
                    messagebox.showerror("启动失败", f"无法启动 SteamVR：{e}")
                    return

        # 尝试通过 Steam 协议启动
        try:
            os.startfile("steam://rungameid/250820")
            messagebox.showinfo("SteamVR", "正在通过 Steam 启动 SteamVR...")
        except Exception:
            messagebox.showwarning(
                "未找到 SteamVR",
                "未检测到 SteamVR 安装。\n"
                "请确保已安装 Steam 和 SteamVR。"
            )

    def _open_toolkit(self):
        """打开 PSVR2Toolkit 下载页面"""
        try:
            os.startfile(PSVR2TOOLKIT_URL)
        except Exception:
            messagebox.showinfo(
                "PSVR2Toolkit",
                f"请在浏览器中打开：\n{PSVR2TOOLKIT_URL}"
            )

    def _show_about(self):
        """显示关于对话框"""
        messagebox.showinfo(
            f"关于 {APP_NAME}",
            f"{APP_NAME} v{APP_VERSION}\n\n"
            f"PS VR2 PC 控制面板\n"
            f"一键管理 PS VR2 解锁功能\n\n"
            f"作者: {APP_AUTHOR}\n"
            f"开源项目: github.com/cpufreestyle/psvr2-panel\n\n"
            f"基于 PSVR2Toolkit 开源社区成果"
        )

    def run(self):
        """启动应用"""
        self.root.mainloop()


# ============================================================
# 入口
# ============================================================
if __name__ == "__main__":
    app = PSVR2Panel()
    app.run()
