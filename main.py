#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PS VR2 PC 控制面板 — PSVR2 Panel v3.1
一键管理 PS VR2 在 PC 上的解锁功能
深度集成 PSVR2Toolkit 工具链
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
import urllib.request
import urllib.error
import zipfile
import shutil
from pathlib import Path
import subprocess
import sys

# ---- 隐藏子进程控制台窗口 (Windows) ----
if sys.platform == "win32":
    _si = subprocess.STARTUPINFO()
    _si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    _si.wShowWindow = subprocess.SW_HIDE
else:
    _si = None

def _run_hidden(cmd, **kwargs):
    """执行 subprocess.run，自动隐藏控制台窗口"""
    kw = dict(capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
    if sys.platform == "win32":
        kw["startupinfo"] = _si
    kw.update(kwargs)
    return subprocess.run(cmd, **kw)

def _popen_hidden(cmd, **kwargs):
    """执行 subprocess.Popen，自动隐藏控制台窗口"""
    kw = {}
    if sys.platform == "win32":
        kw["startupinfo"] = _si
    kw.update(kwargs)
    return subprocess.Popen(cmd, **kw)

# ============================================================
# 常量配置
# ============================================================
APP_NAME = "PSVR2 Panel"
APP_VERSION = "3.2.0"
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
    "orange": "#FF9100",
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
VRCFT_DEPLOY_DIR = Path.home() / "AppData" / "Local" / "PSVR2Panel" / "VRCFaceTracking"

# GitHub 链接
PSVR2TOOLKIT_URL = "https://github.com/BnuuySolutions/PSVR2Toolkit"
PSVR2TOOLKIT_API = "https://api.github.com/repos/BnuuySolutions/PSVR2Toolkit/releases/latest"
VRCFT_DOWNLOAD_URL = "https://github.com/benaclejames/VRCFaceTracking/releases"
VRCFT_STEAM_URL = "steam://store/658580"  # VRCFaceTracking Steam 页面

# 驱动文件名
DRIVER_DLL = "driver_playstation_vr2.dll"
DRIVER_ORIG_DLL = "driver_playstation_vr2_orig.dll"


# ============================================================
# PSVR2Toolkit 深度集成
# ============================================================
class PSVR2Toolkit:
    """PSVR2Toolkit 工具链深度集成"""

    def __init__(self):
        self.driver_dir = None
        self.driver_installed = False
        self.toolkit_active = False
        self.driver_version = "未知"
        self.steam_path = None
        self.latest_version = None
        self.latest_download_url = None

    def find_installation(self):
        """查找 PSVR2Toolkit 驱动安装位置"""
        for path in PSVR2_DRIVER_PATHS:
            driver_dll = os.path.join(path, DRIVER_DLL)
            orig_dll = os.path.join(path, DRIVER_ORIG_DLL)

            if os.path.exists(driver_dll):
                self.driver_dir = path
                self.driver_installed = True

                if os.path.exists(orig_dll):
                    driver_size = os.path.getsize(driver_dll)
                    orig_size = os.path.getsize(orig_dll)
                    if driver_size < 500000 and orig_size > 3000000:
                        self.toolkit_active = True
                        self.driver_version = "PSVR2Toolkit"
                        return True
                    elif driver_size > 3000000 and orig_size < 500000:
                        # 反向情况：原始驱动在使用，toolkit备份
                        self.toolkit_active = False
                        self.driver_version = "官方驱动 (Toolkit已备份)"
                        return True

                self.driver_version = "官方驱动"
                return True

        return False

    def get_feature_status(self):
        """获取各功能的解锁状态"""
        if not self.driver_installed:
            return {
                "eye_tracking": ("需要安装", "red"),
                "head_vibration": ("需要安装", "red"),
                "adaptive_trigger": ("需要安装", "red"),
                "hdr": ("需要安装", "red"),
                "haptic_feedback": ("需要安装", "red"),
                "passthrough": ("官方支持", "green"),
            }

        if self.toolkit_active:
            return {
                "eye_tracking": ("已解锁 ✅", "green"),
                "head_vibration": ("已解锁 ✅", "green"),
                "adaptive_trigger": ("已解锁 ✅", "green"),
                "hdr": ("已解锁 ✅", "green"),
                "haptic_feedback": ("部分可用", "yellow"),
                "passthrough": ("官方支持", "green"),
            }

        return {
            "eye_tracking": ("未解锁", "red"),
            "head_vibration": ("未解锁", "red"),
            "adaptive_trigger": ("未解锁", "red"),
            "hdr": ("未解锁", "red"),
            "haptic_feedback": ("未解锁", "red"),
            "passthrough": ("官方支持", "green"),
        }

    def switch_to_toolkit(self):
        """切换到 PSVR2Toolkit 驱动"""
        if not self.driver_dir:
            return False, "未找到驱动目录"

        driver_path = os.path.join(self.driver_dir, DRIVER_DLL)
        orig_path = os.path.join(self.driver_dir, DRIVER_ORIG_DLL)
        toolkit_path = os.path.join(self.driver_dir, "driver_playstation_vr2_toolkit.dll")

        if self.toolkit_active:
            return True, "Toolkit 驱动已是当前激活状态"

        # 查找 toolkit 驱动
        # 策略1: 检查是否有 _toolkit.dll 备份
        if os.path.exists(toolkit_path):
            # 备份当前官方驱动
            if os.path.exists(driver_path):
                os.rename(driver_path, orig_path)
            # 激活 toolkit
            os.rename(toolkit_path, driver_path)
            self.toolkit_active = True
            self.driver_version = "PSVR2Toolkit"
            return True, "已切换到 PSVR2Toolkit 驱动"

        # 策略2: 如果有 orig 备份且 orig 是大文件，当前就是官方驱动
        if os.path.exists(orig_path):
            orig_size = os.path.getsize(orig_path)
            if orig_size < 500000:
                # orig 是 toolkit 备份，当前是官方驱动 → 互换
                os.rename(driver_path, toolkit_path)  # 备份官方
                os.rename(orig_path, driver_path)      # 恢复 toolkit
                self.toolkit_active = True
                self.driver_version = "PSVR2Toolkit"
                return True, "已切换到 PSVR2Toolkit 驱动"

        return False, "未找到 PSVR2Toolkit 驱动文件，请先下载安装"

    def switch_to_official(self):
        """切换回官方驱动"""
        if not self.driver_dir:
            return False, "未找到驱动目录"

        driver_path = os.path.join(self.driver_dir, DRIVER_DLL)
        orig_path = os.path.join(self.driver_dir, DRIVER_ORIG_DLL)
        toolkit_path = os.path.join(self.driver_dir, "driver_playstation_vr2_toolkit.dll")

        if not self.toolkit_active:
            return True, "官方驱动已是当前激活状态"

        # 备份 toolkit 驱动
        if os.path.exists(driver_path):
            os.rename(driver_path, toolkit_path)

        # 恢复官方驱动
        if os.path.exists(orig_path):
            orig_size = os.path.getsize(orig_path)
            if orig_size > 3000000:
                os.rename(orig_path, driver_path)
                self.toolkit_active = False
                self.driver_version = "官方驱动"
                return True, "已切换回官方驱动"
            else:
                # orig 不是官方驱动，恢复回去
                if os.path.exists(toolkit_path):
                    os.rename(toolkit_path, driver_path)
                return False, "未找到官方驱动备份文件"

        return False, "未找到官方驱动备份文件"

    def check_update(self):
        """检查 GitHub 上的最新版本"""
        try:
            req = urllib.request.Request(PSVR2TOOLKIT_API)
            req.add_header("User-Agent", "PSVR2Panel/3.1")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self.latest_version = data.get("tag_name", "unknown")
                assets = data.get("assets", [])
                for asset in assets:
                    if asset["name"].endswith(".dll"):
                        self.latest_download_url = asset["browser_download_url"]
                        break
                return True, self.latest_version
        except Exception as e:
            return False, str(e)

    def download_update(self, progress_callback=None):
        """下载最新驱动"""
        if not self.latest_download_url:
            return False, "无下载链接"

        try:
            save_path = os.path.join(self.driver_dir, "driver_playstation_vr2_new.dll")
            urllib.request.urlretrieve(
                self.latest_download_url, save_path,
                reporthook=progress_callback
            )
            return True, save_path
        except Exception as e:
            return False, str(e)

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


# ============================================================
# VRCFaceTracking 深度集成
# ============================================================
class VRCFaceTrackingIntegration:
    """VRCFaceTracking 深度集成（内置部署）"""

    BUNDLED_ZIP = "vrcft.zip"

    def __init__(self):
        self.installed = False
        self.path = None
        self.is_running = False
        self.bundled = False

    @staticmethod
    def _get_bundled_zip_path():
        """获取内置 vrcft.zip 的路径（兼容 PyInstaller 和开发模式）"""
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
        else:
            base = Path(__file__).parent
        return Path(base) / VRCFaceTrackingIntegration.BUNDLED_ZIP

    def deploy_bundled(self):
        """从内置 vrcft.zip 解压部署到 AppData，返回是否成功"""
        zip_path = self._get_bundled_zip_path()
        if not zip_path.exists():
            return False
        try:
            dest = VRCFT_DEPLOY_DIR
            exe = dest / "VRCFaceTracking.exe"
            if exe.exists():
                # 已部署过，直接用
                return True
            dest.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(str(zip_path), 'r') as zf:
                zf.extractall(str(dest))
            return exe.exists()
        except Exception:
            return False

    def find_installation(self):
        """查找 VRCFaceTracking 安装（标准路径 > 内置部署）"""
        # 1. 检查标准安装路径
        for path in VRCFT_PATHS:
            if path.exists():
                self.installed = True
                self.path = str(path)
                self.bundled = False
                return True

        # 2. AppData 广泛搜索
        appdata_local = Path.home() / "AppData" / "Local"
        if appdata_local.exists():
            for folder in appdata_local.iterdir():
                if "vrcfacetracking" in folder.name.lower():
                    exe = folder / "VRCFaceTracking.exe"
                    if exe.exists():
                        self.installed = True
                        self.path = str(exe)
                        self.bundled = False
                        return True

        # 3. 从内置 zip 部署
        if self.deploy_bundled():
            exe = VRCFT_DEPLOY_DIR / "VRCFaceTracking.exe"
            if exe.exists():
                self.installed = True
                self.path = str(exe)
                self.bundled = True
                return True

        return False

    def check_running(self):
        """检查 VRCFaceTracking 是否正在运行"""
        try:
            result = _run_hidden(
                ["powershell", "-Command",
                 "Get-Process VRCFaceTracking -ErrorAction SilentlyContinue | "
                 "Select-Object Id, ProcessName | ConvertTo-Json -Compress"]
            )
            if result.returncode == 0 and result.stdout.strip():
                self.is_running = True
                return True
        except Exception:
            pass
        self.is_running = False
        return False

    def launch(self):
        """启动 VRCFaceTracking"""
        if self.path and os.path.exists(self.path):
            _popen_hidden([self.path])
            return True
        return False


# ============================================================
# SteamVR 进程监控
# ============================================================
class SteamVRMonitor:
    """SteamVR 进程监控"""

    def __init__(self):
        self.is_running = False
        self.psvr2_detected = False

    def check_running(self):
        """检查 SteamVR 是否运行"""
        try:
            result = _run_hidden(
                ["powershell", "-Command",
                 "Get-Process vrserver -ErrorAction SilentlyContinue | "
                 "Select-Object Id | ConvertTo-Json -Compress"]
            )
            self.is_running = result.returncode == 0 and result.stdout.strip() != ""
        except Exception:
            self.is_running = False
        return self.is_running

    def check_psvr2_in_steamvr(self):
        """检查 SteamVR 是否识别 PSVR2"""
        try:
            result = _run_hidden(
                ["powershell", "-Command",
                 "Get-Content \"$env:LOCALAPPDATA\\openvr\\openvrpaths.vrpath\" "
                 "-ErrorAction SilentlyContinue"]
            )
            if result.returncode == 0 and "playstation" in result.stdout.lower():
                self.psvr2_detected = True
                return True
        except Exception:
            pass
        self.psvr2_detected = False
        return False


# ============================================================
# PS VR2 设备检测
# ============================================================
class PSVR2Detector:
    """PS VR2 综合检测器"""

    def __init__(self):
        self.connected = False
        self.toolkit = PSVR2Toolkit()
        self.vrcft = VRCFaceTrackingIntegration()
        self.steamvr = SteamVRMonitor()
        self.features = {
            "eye_tracking": {"name": "👁️ 眼动追踪", "status": "检测中...", "color": "gray", "desc": "VRChat 眼动追踪支持"},
            "head_vibration": {"name": "📳 头显震动", "status": "检测中...", "color": "gray", "desc": "头显震动反馈"},
            "adaptive_trigger": {"name": "🎮 自适应扳机", "status": "检测中...", "color": "gray", "desc": "Sense 控制器扳机阻力"},
            "hdr": {"name": "🌈 HDR / 10-bit", "status": "检测中...", "color": "gray", "desc": "HDR 高动态范围色彩"},
            "haptic_feedback": {"name": "✋ 触觉反馈", "status": "检测中...", "color": "gray", "desc": "控制器触觉反馈"},
            "passthrough": {"name": "📷 透视视图", "status": "检测中...", "color": "gray", "desc": "摄像头透视模式"},
        }

    def detect_all(self):
        """全面检测"""
        self._detect_connection()
        self.toolkit.find_installation()
        self.vrcft.find_installation()
        self.vrcft.check_running()
        self.steamvr.check_running()
        self.steamvr.check_psvr2_in_steamvr()
        self._update_feature_status()
        return self.connected

    def _detect_connection(self):
        """检测 PS VR2 是否连接"""
        try:
            result = _run_hidden(
                ["powershell", "-Command",
                 "Get-PnpDevice | Where-Object { $_.FriendlyName -match 'PlayStation|PSVR|VR2' } | "
                 "Select-Object FriendlyName, Status | ConvertTo-Json -Compress"]
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
            if self.toolkit.driver_installed:
                self.connected = True
        except (subprocess.TimeoutExpired, Exception):
            pass

    def _update_feature_status(self):
        """更新功能状态"""
        status_map = self.toolkit.get_feature_status()
        for key, (status, color) in status_map.items():
            if key in self.features:
                self.features[key]["status"] = status
                self.features[key]["color"] = color


# ============================================================
# GUI 主界面 v3.1
# ============================================================
class PSVR2Panel:
    """PS VR2 控制面板 v3.2 — 深度集成 PSVR2Toolkit"""

    def __init__(self):
        self.detector = PSVR2Detector()
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("620x820")
        self.root.minsize(380, 560)   # 可缩小到 380x560
        self.root.maxsize(1200, 1400)
        self.root.configure(bg=COLORS["bg_dark"])

        # ---- 内容容器（可随窗口拉伸） ----
        self.content = tk.Frame(self.root, bg=COLORS["bg_dark"])
        self.content.pack(fill=tk.BOTH, expand=True)

        # 状态变量
        self.status_var = tk.StringVar(value="正在检测...")
        self.toolkit_status_var = tk.StringVar(value="检测中...")
        self.vrcft_status_var = tk.StringVar(value="检测中...")
        self.steamvr_status_var = tk.StringVar(value="检测中...")

        self._build_ui()
        self._run_detection()
        self._start_monitor()

    def _build_ui(self):
        """构建界面（带滚动支持）"""
        # Canvas + Scrollbar，让窗口可调整大小 + 可滚动
        self.canvas = tk.Canvas(
            self.content, bg=COLORS["bg_dark"],
            highlightthickness=0, bd=0
        )
        self.scrollbar = tk.Scrollbar(
            self.content, orient=tk.VERTICAL,
            command=self.canvas.yview, bg=COLORS["bg_dark"]
        )
        self.scrollable = tk.Frame(self.canvas, bg=COLORS["bg_dark"])

        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scroll_id = self.canvas.create_window(
            (0, 0), window=self.scrollable, anchor="nw"
        )

        def on_configure(e):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.scrollable.bind("<Configure>", on_configure)

        def on_canvas_resize(e):
            # 窗口缩小时自动显示滚动条
            pass
        self.canvas.bind("<Configure>", on_canvas_resize)

        # 鼠标滚轮支持
        def on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.canvas.bind_all("<MouseWheel>", on_mousewheel)

        # ---- 顶部标题 ----
        header = tk.Frame(self.scrollable, bg=COLORS["bg_dark"])
        header.pack(fill=tk.X, padx=20, pady=(12, 3))

        tk.Label(
            header, text="🎮 PS VR2 Panel",
            font=("Microsoft YaHei", 22, "bold"),
            fg=COLORS["text_white"], bg=COLORS["bg_dark"]
        ).pack(anchor="w")

        version_label = tk.Label(
            header, text=f"v{APP_VERSION} · PlayStation VR2 PC 控制面板",
            font=("Microsoft YaHei", 9),
            fg=COLORS["text_light"], bg=COLORS["bg_dark"]
        )
        version_label.pack(anchor="w")

        # ---- 连接状态 ----
        conn_frame = tk.Frame(
            self.scrollable, bg=COLORS["card_bg"],
            highlightbackground=COLORS["card_border"], highlightthickness=1
        )
        conn_frame.pack(fill=tk.X, padx=20, pady=6)

        self.conn_indicator = tk.Label(
            conn_frame, text="●", font=("Arial", 16),
            fg=COLORS["yellow"], bg=COLORS["card_bg"]
        )
        self.conn_indicator.pack(side=tk.LEFT, padx=(12, 5), pady=8)

        tk.Label(
            conn_frame, textvariable=self.status_var,
            font=("Microsoft YaHei", 11),
            fg=COLORS["text_white"], bg=COLORS["card_bg"]
        ).pack(side=tk.LEFT, pady=8)

        tk.Button(
            conn_frame, text="🔄 刷新",
            font=("Microsoft YaHei", 9),
            bg=COLORS["accent"], fg=COLORS["text_white"],
            relief=tk.FLAT, cursor="hand2",
            command=self._run_detection
        ).pack(side=tk.RIGHT, padx=12, pady=8)

        # ============ 驱动管理区 ============
        tk.Label(
            self.scrollable, text="🔧 驱动管理",
            font=("Microsoft YaHei", 12, "bold"),
            fg=COLORS["text_white"], bg=COLORS["bg_dark"]
        ).pack(anchor="w", padx=25, pady=(10, 3))

        # PSVR2Toolkit 状态
        toolkit_frame = tk.Frame(
            self.scrollable, bg=COLORS["card_bg"],
            highlightbackground=COLORS["card_border"], highlightthickness=1
        )
        toolkit_frame.pack(fill=tk.X, padx=20, pady=2)

        tk.Label(
            toolkit_frame, text="PSVR2Toolkit:",
            font=("Microsoft YaHei", 10),
            fg=COLORS["text_light"], bg=COLORS["card_bg"]
        ).pack(side=tk.LEFT, padx=(12, 5), pady=8)

        self.toolkit_status_label = tk.Label(
            toolkit_frame, textvariable=self.toolkit_status_var,
            font=("Microsoft YaHei", 10, "bold"),
            fg=COLORS["text_white"], bg=COLORS["card_bg"]
        )
        self.toolkit_status_label.pack(side=tk.LEFT, pady=8)

        # 驱动切换按钮
        btn_frame = tk.Frame(toolkit_frame, bg=COLORS["card_bg"])
        btn_frame.pack(side=tk.RIGHT, padx=12, pady=8)

        self.switch_btn = tk.Button(
            btn_frame, text="🔄 切换驱动",
            font=("Microsoft YaHei", 8),
            bg=COLORS["orange"], fg=COLORS["text_white"],
            relief=tk.FLAT, cursor="hand2",
            command=self._switch_driver
        )
        self.switch_btn.pack(side=tk.RIGHT, padx=(4, 0))

        tk.Button(
            btn_frame, text="📁",
            font=("Arial", 9),
            bg=COLORS["accent"], fg=COLORS["text_white"],
            relief=tk.FLAT, cursor="hand2", width=3,
            command=self._open_driver_folder
        ).pack(side=tk.RIGHT, padx=4)

        # 更新检查
        update_frame = tk.Frame(
            self.scrollable, bg=COLORS["card_bg"],
            highlightbackground=COLORS["card_border"], highlightthickness=1
        )
        update_frame.pack(fill=tk.X, padx=20, pady=2)

        tk.Label(
            update_frame, text="🔄 驱动更新:",
            font=("Microsoft YaHei", 10),
            fg=COLORS["text_light"], bg=COLORS["card_bg"]
        ).pack(side=tk.LEFT, padx=(12, 5), pady=8)

        self.update_status_label = tk.Label(
            update_frame, text="未检查",
            font=("Microsoft YaHei", 10),
            fg=COLORS["text_light"], bg=COLORS["card_bg"]
        )
        self.update_status_label.pack(side=tk.LEFT, pady=8)

        self.update_btn = tk.Button(
            update_frame, text="🔍 检查更新",
            font=("Microsoft YaHei", 8),
            bg=COLORS["accent"], fg=COLORS["text_white"],
            relief=tk.FLAT, cursor="hand2",
            command=self._check_update
        )
        self.update_btn.pack(side=tk.RIGHT, padx=12, pady=8)

        # ============ SteamVR & VRCFT 状态 ============
        tk.Label(
            self.scrollable, text="🥽 运行状态",
            font=("Microsoft YaHei", 12, "bold"),
            fg=COLORS["text_white"], bg=COLORS["bg_dark"]
        ).pack(anchor="w", padx=25, pady=(10, 3))

        # SteamVR 状态
        steamvr_frame = tk.Frame(
            self.scrollable, bg=COLORS["card_bg"],
            highlightbackground=COLORS["card_border"], highlightthickness=1
        )
        steamvr_frame.pack(fill=tk.X, padx=20, pady=2)

        tk.Label(
            steamvr_frame, text="SteamVR:",
            font=("Microsoft YaHei", 10),
            fg=COLORS["text_light"], bg=COLORS["card_bg"]
        ).pack(side=tk.LEFT, padx=(12, 5), pady=8)

        self.steamvr_status_label = tk.Label(
            steamvr_frame, textvariable=self.steamvr_status_var,
            font=("Microsoft YaHei", 10, "bold"),
            fg=COLORS["text_white"], bg=COLORS["card_bg"]
        )
        self.steamvr_status_label.pack(side=tk.LEFT, pady=8)

        tk.Button(
            steamvr_frame, text="🚀 启动",
            font=("Microsoft YaHei", 8),
            bg=COLORS["success"], fg=COLORS["text_white"],
            relief=tk.FLAT, cursor="hand2",
            command=self._launch_steamvr
        ).pack(side=tk.RIGHT, padx=12, pady=8)

        # VRCFaceTracking 状态
        vrcft_frame = tk.Frame(
            self.scrollable, bg=COLORS["card_bg"],
            highlightbackground=COLORS["card_border"], highlightthickness=1
        )
        vrcft_frame.pack(fill=tk.X, padx=20, pady=2)

        tk.Label(
            vrcft_frame, text="VRCFaceTracking:",
            font=("Microsoft YaHei", 10),
            fg=COLORS["text_light"], bg=COLORS["card_bg"]
        ).pack(side=tk.LEFT, padx=(12, 5), pady=8)

        self.vrcft_status_label = tk.Label(
            vrcft_frame, textvariable=self.vrcft_status_var,
            font=("Microsoft YaHei", 10, "bold"),
            fg=COLORS["text_white"], bg=COLORS["card_bg"]
        )
        self.vrcft_status_label.pack(side=tk.LEFT, pady=8)

        vrcft_btn_frame = tk.Frame(vrcft_frame, bg=COLORS["card_bg"])
        vrcft_btn_frame.pack(side=tk.RIGHT, padx=12, pady=8)

        self.vrcft_launch_btn = tk.Button(
            vrcft_btn_frame, text="🚀 启动",
            font=("Microsoft YaHei", 8),
            bg=COLORS["success"], fg=COLORS["text_white"],
            relief=tk.FLAT, cursor="hand2",
            command=self._launch_vrcft
        )
        self.vrcft_launch_btn.pack(side=tk.RIGHT, padx=(4, 0))

        tk.Button(
            vrcft_btn_frame, text="🎮 Steam安装",
            font=("Microsoft YaHei", 8),
            bg=COLORS["accent"], fg=COLORS["text_white"],
            relief=tk.FLAT, cursor="hand2",
            command=self._install_vrcft_steam
        ).pack(side=tk.RIGHT, padx=4)

        # ============ 功能解锁状态 ============
        tk.Label(
            self.scrollable, text="📊 功能状态",
            font=("Microsoft YaHei", 12, "bold"),
            fg=COLORS["text_white"], bg=COLORS["bg_dark"]
        ).pack(anchor="w", padx=25, pady=(10, 3))

        self.feature_labels = {}
        for key, feat in self.detector.features.items():
            frame = tk.Frame(
                self.scrollable, bg=COLORS["card_bg"],
                highlightbackground=COLORS["card_border"], highlightthickness=1
            )
            frame.pack(fill=tk.X, padx=20, pady=2)

            left = tk.Frame(frame, bg=COLORS["card_bg"])
            left.pack(side=tk.LEFT, padx=(12, 5), pady=5)

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

            status_label = tk.Label(
                frame, text=feat["status"],
                font=("Microsoft YaHei", 9, "bold"),
                fg=COLORS["gray"], bg=COLORS["card_bg"]
            )
            status_label.pack(side=tk.RIGHT, padx=12, pady=5)
            self.feature_labels[key] = status_label

        # ============ 底部操作区 ============
        bottom = tk.Frame(self.scrollable, bg=COLORS["bg_dark"])
        bottom.pack(fill=tk.X, padx=20, pady=(12, 15))

        # 一键启动全部
        tk.Button(
            bottom, text="🚀 一键启动全部 (SteamVR + VRCFT)",
            font=("Microsoft YaHei", 13, "bold"),
            bg=COLORS["success"], fg=COLORS["text_white"],
            relief=tk.FLAT, cursor="hand2", height=2,
            command=self._launch_all
        ).pack(fill=tk.X, pady=(0, 6))

        # 工具链按钮
        tools_frame = tk.Frame(bottom, bg=COLORS["bg_dark"])
        tools_frame.pack(fill=tk.X)

        tk.Button(
            tools_frame, text="📦 PSVR2Toolkit",
            font=("Microsoft YaHei", 9),
            bg=COLORS["card_bg"], fg=COLORS["text_white"],
            relief=tk.FLAT, cursor="hand2",
            command=self._open_toolkit_github
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 3))



        tk.Button(
            tools_frame, text="ℹ️ 关于",
            font=("Microsoft YaHei", 9),
            bg=COLORS["card_bg"], fg=COLORS["text_white"],
            relief=tk.FLAT, cursor="hand2",
            command=self._show_about
        ).pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(3, 0))

    # ---- 后台检测 ----
    def _run_detection(self):
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

        # PSVR2Toolkit
        toolkit = self.detector.toolkit
        if toolkit.driver_installed:
            if toolkit.toolkit_active:
                self.toolkit_status_var.set(f"✅ {toolkit.driver_version} (激活)")
                self.toolkit_status_label.config(fg=COLORS["green"])
                self.switch_btn.config(text="⏪ 恢复官方", bg=COLORS["accent"])
            else:
                self.toolkit_status_var.set(f"⚠️ {toolkit.driver_version}")
                self.toolkit_status_label.config(fg=COLORS["yellow"])
                self.switch_btn.config(text="🔄 切换Toolkit", bg=COLORS["orange"])
        else:
            self.toolkit_status_var.set("❌ 未安装")
            self.toolkit_status_label.config(fg=COLORS["red"])

        # SteamVR
        if self.detector.steamvr.is_running:
            self.steamvr_status_var.set("▶ 运行中")
            self.steamvr_status_label.config(fg=COLORS["green"])
        else:
            self.steamvr_status_var.set("⏹ 未运行")
            self.steamvr_status_label.config(fg=COLORS["text_light"])

        # VRCFaceTracking
        vrcft = self.detector.vrcft
        if vrcft.is_running:
            tag = "内置" if vrcft.bundled else "本地"
            self.vrcft_status_var.set(f"▶ 运行中 ({tag})")
            self.vrcft_status_label.config(fg=COLORS["green"])
        elif vrcft.installed:
            tag = "内置" if vrcft.bundled else "已安装"
            self.vrcft_status_var.set(tag)
            self.vrcft_status_label.config(fg=COLORS["text_white"])
        else:
            self.vrcft_status_var.set("❌ 未部署")
            self.vrcft_status_label.config(fg=COLORS["red"])

        # 功能状态
        for key, label in self.feature_labels.items():
            feat = self.detector.features[key]
            label.config(text=feat["status"], fg=COLORS.get(feat["color"], COLORS["gray"]))

    # ---- 进程监控 ----
    def _start_monitor(self):
        """启动定期进程监控"""
        self._monitor_loop()

    def _monitor_loop(self):
        """监控循环（每5秒）"""
        def check():
            steamvr_running = self.detector.steamvr.check_running()
            vrcft_running = self.detector.vrcft.check_running()
            self.root.after(0, self._update_process_status, steamvr_running, vrcft_running)

        threading.Thread(target=check, daemon=True).start()
        self.root.after(5000, self._monitor_loop)

    def _update_process_status(self, steamvr_running, vrcft_running):
        """更新进程状态"""
        if steamvr_running:
            self.steamvr_status_var.set("▶ 运行中")
            self.steamvr_status_label.config(fg=COLORS["green"])
        else:
            self.steamvr_status_var.set("⏹ 未运行")
            self.steamvr_status_label.config(fg=COLORS["text_light"])

        vrcft = self.detector.vrcft
        if vrcft_running:
            tag = "内置" if vrcft.bundled else "本地"
            self.vrcft_status_var.set(f"▶ 运行中 ({tag})")
            self.vrcft_status_label.config(fg=COLORS["green"])
        elif vrcft.installed:
            tag = "内置" if vrcft.bundled else "已安装"
            self.vrcft_status_var.set(tag)
            self.vrcft_status_label.config(fg=COLORS["text_white"])

    # ---- 驱动管理 ----
    def _switch_driver(self):
        """切换驱动"""
        toolkit = self.detector.toolkit
        if toolkit.toolkit_active:
            result = messagebox.askyesno(
                "切换驱动",
                "确定要切换回官方驱动吗？\n\n"
                "⚠️ 切换后将失去眼动追踪等功能\n"
                "需要重启 SteamVR 生效"
            )
            if result:
                success, msg = toolkit.switch_to_official()
                if success:
                    messagebox.showinfo("成功", f"{msg}\n\n请重启 SteamVR 使更改生效")
                else:
                    messagebox.showerror("失败", msg)
                self._run_detection()
        else:
            result = messagebox.askyesno(
                "切换驱动",
                "确定要切换到 PSVR2Toolkit 驱动吗？\n\n"
                "✅ 将解锁眼动追踪、头显震动等功能\n"
                "需要重启 SteamVR 生效"
            )
            if result:
                success, msg = toolkit.switch_to_toolkit()
                if success:
                    messagebox.showinfo("成功", f"{msg}\n\n请重启 SteamVR 使更改生效")
                else:
                    messagebox.showerror("失败", msg)
                self._run_detection()

    def _check_update(self):
        """检查驱动更新"""
        self.update_status_label.config(text="检查中...", fg=COLORS["yellow"])
        self.update_btn.config(state=tk.DISABLED)

        def check():
            ok, ver = self.detector.toolkit.check_update()
            self.root.after(0, self._on_update_checked, ok, ver)

        threading.Thread(target=check, daemon=True).start()

    def _on_update_checked(self, ok, ver):
        self.update_btn.config(state=tk.NORMAL)
        if ok:
            self.update_status_label.config(
                text=f"最新: {ver}",
                fg=COLORS["green"]
            )
            result = messagebox.askyesno(
                "更新可用",
                f"PSVR2Toolkit 最新版本: {ver}\n\n是否打开下载页面？"
            )
            if result:
                os.startfile(PSVR2TOOLKIT_URL + "/releases/latest")
        else:
            self.update_status_label.config(text="检查失败", fg=COLORS["red"])

    # ---- 启动功能 ----
    def _launch_steamvr(self):
        for path in STEAMVR_PATHS:
            if os.path.exists(path):
                _popen_hidden([path])
                return
        try:
            os.startfile("steam://rungameid/250820")
        except Exception:
            messagebox.showwarning("未找到", "未检测到 SteamVR 安装")

    def _launch_vrcft(self):
        if self.detector.vrcft.launch():
            pass
        else:
            messagebox.showwarning("未安装", "VRCFaceTracking 未安装\n\n请点击「下载」按钮获取")

    def _launch_all(self):
        """一键启动全部"""
        self._launch_steamvr()
        if self.detector.vrcft.installed:
            time.sleep(2)
            self._launch_vrcft()
        else:
            messagebox.showwarning("提示", "VRCFaceTracking 未安装，仅启动 SteamVR")

    def _download_vrcft(self):
        os.startfile(VRCFT_DOWNLOAD_URL)

    def _install_vrcft_steam(self):
        """打开 VRCFaceTracking Steam 页面"""
        try:
            os.startfile(VRCFT_STEAM_URL)
        except Exception:
            # 如果 steam:// 协议失败，打开网页版
            os.startfile("https://store.steampowered.com/app/658580/VRCFaceTracking/")

    def _open_driver_folder(self):
        path = self.detector.toolkit.driver_dir
        if path and os.path.exists(path):
            os.startfile(path)
        else:
            messagebox.showinfo("提示", "未找到 PSVR2 驱动目录")

    def _open_toolkit_github(self):
        os.startfile(PSVR2TOOLKIT_URL)

    def _show_about(self):
        messagebox.showinfo(
            f"关于 {APP_NAME}",
            f"{APP_NAME} v{APP_VERSION}\n\n"
            f"PS VR2 PC 控制面板\n"
            f"深度集成 PSVR2Toolkit 工具链\n\n"
            f"v3.2 更新：\n"
            f"• 移除 GitHub 下载按钮（项目已停止维护）\n"
            f"• 保留 Steam 安装渠道\n\n"
            f"v3.1 新功能：\n"
            f"• 驱动一键切换 (官方 ↔ Toolkit)\n"
            f"• 内置 VRCFaceTracking 自动部署\n"
            f"• SteamVR / VRCFT 进程监控\n"
            f"• GitHub 驱动更新检查\n"
            f"• 一键启动全部工具\n\n"
            f"作者: {APP_AUTHOR}\n"
            f"https://gitee.com/cpufreestyle/psvr2-panel"
        )

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = PSVR2Panel()
    app.run()
