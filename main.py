#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PS VR2 PC 控制面板 — PSVR2 Panel v4.0.0
一键管理 PS VR2 在 PC 上的解锁功能，深度集成 PSVR2Toolkit 工具链

v4.0.0 更新：
  🎨 UI 全面升级：现代化深色主题、分 Tab 布局、卡片式设计
  📊 设备信息面板：USB 连接详情
  💾 驱动备份/恢复：时间戳快照管理
  ⚙️ SteamVR 快速设置：分辨率/超采样/运动平滑
  ⚡ 性能优化：tasklist 替代 PowerShell，单线程监控
  🔧 代码重构：日志系统、类型提示、无重复导入、版本统一

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
import logging
import logging.handlers
import urllib.request
import urllib.error
import zipfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple

# ============================================================
# 常量 & 主题
# ============================================================
APP_NAME = "PSVR2 Panel"
APP_VERSION = "4.0.0"
APP_AUTHOR = "Michael Qiu"
GITEE_URL = "https://gitee.com/cpufreestyle/psvr2-panel"

# 颜色主题（索尼 PlayStation 风格）
C = {
    "bg": "#0a0e27",
    "card": "#151a3a",
    "card_hi": "#1e2a5a",
    "accent": "#0070d1",
    "accent_hi": "#1a82ef",
    "text": "#ffffff",
    "text_sub": "#8fa4c4",
    "green": "#00c853",
    "red": "#ff1744",
    "yellow": "#ffd600",
    "orange": "#ff9100",
    "teal": "#00bcd4",
}

# PSVR2Toolkit 路径
DRIVER_DIRS = [
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
VRCFT_DEPLOY = Path.home() / "AppData" / "Local" / "PSVR2Panel" / "VRCFaceTracking"
BACKUP_DIR = Path.home() / "AppData" / "Local" / "PSVR2Panel" / "backups"
LOG_DIR = Path.home() / "AppData" / "Local" / "PSVR2Panel" / "logs"

DRIVER_DLL = "driver_playstation_vr2.dll"
DRIVER_ORIG = "driver_playstation_vr2_orig.dll"
DRIVER_TOOLKIT = "driver_playstation_vr2_toolkit.dll"

PSVR2TOOLKIT_API = "https://api.github.com/repos/BnuuySolutions/PSVR2Toolkit/releases/latest"
VRCFT_STEAM_URL = "steam://store/658580"


# ============================================================
# 日志系统
# ============================================================
def _setup_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "psvr2_panel.log"
    logger = logging.getLogger("PSVR2Panel")
    logger.setLevel(logging.DEBUG)
    if logger.handlers:
        return logger
    fh = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=524288, backupCount=3, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
    fh.setFormatter(fmt)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


log = _setup_logging()


# ============================================================
# 工具函数
# ============================================================
def _run(cmd, **kw) -> subprocess.CompletedProcess:
    kw.setdefault("capture_output", True)
    kw.setdefault("timeout", 10)
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE
    kw["startupinfo"] = si
    if "encoding" not in kw:
        kw["encoding"] = "utf-8"
        kw["errors"] = "replace"
    return subprocess.run(cmd, **kw)


def _popen(cmd, **kw) -> subprocess.Popen:
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE
    kw["startupinfo"] = si
    return subprocess.Popen(cmd, **kw)


def _process_running(name: str) -> bool:
    """用 tasklist 快速检测进程是否运行（比 PowerShell 快很多）"""
    r = _run(["tasklist", "/FI", f"IMAGENAME eq {name}", "/FO", "CSV", "/NH"])
    return name.lower() in r.stdout.lower()


def _open_in_explorer(path: str):
    if os.path.exists(path):
        os.startfile(path)
    else:
        messagebox.showwarning("提示", f"路径不存在：\n{path}")


def _open_url(url: str):
    os.startfile(url)


def _steamvr_settings_path() -> Optional[Path]:
    p = Path(os.environ.get("LOCALAPPDATA", "")) / "openvr" / "openvrsettings.vrsettings"
    if p.exists():
        return p
    return None


# ============================================================
# PSVR2Toolkit 驱动管理
# ============================================================
class PSVR2Toolkit:
    """PSVR2Toolkit 驱动管理器（增强版：备份/恢复）"""

    def __init__(self):
        self.driver_dir: Optional[str] = None
        self.driver_installed: bool = False
        self.toolkit_active: bool = False
        self.driver_version: str = "未知"
        self.latest_version: Optional[str] = None
        self.latest_url: Optional[str] = None

    def find_installation(self) -> bool:
        for path in DRIVER_DIRS:
            driver_path = os.path.join(path, DRIVER_DLL)
            orig_path = os.path.join(path, DRIVER_ORIG)
            if os.path.exists(driver_path):
                self.driver_dir = path
                self.driver_installed = True
                if os.path.exists(orig_path):
                    ds = os.path.getsize(driver_path)
                    os2 = os.path.getsize(orig_path)
                    if ds < 500000 and os2 > 3000000:
                        self.toolkit_active = True
                        self.driver_version = "PSVR2Toolkit (激活)"
                    elif ds > 3000000 and os2 < 500000:
                        self.toolable_active = False
                        self.driver_version = "官方驱动"
                    else:
                        self.driver_version = "官方驱动"
                else:
                    self.driver_version = "官方驱动"
                log.info(f"驱动检测: {self.driver_dir} | {self.driver_version}")
                return True
        return False

    def get_feature_status(self) -> Dict[str, Tuple[str, str]]:
        if not self.driver_installed:
            return {k: ("需要安装", "red") for k in
                    ["eye_tracking", "head_vibration", "adaptive_trigger", "hdr",
                     "haptic_feedback", "passthrough"]}
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

    def switch(self, to_toolkit: bool) -> Tuple[bool, str]:
        if not self.driver_dir:
            return False, "未找到驱动目录"
        dp = os.path.join(self.driver_dir, DRIVER_DLL)
        op = os.path.join(self.driver_dir, DRIVER_ORIG)
        tp = os.path.join(self.driver_dir, DRIVER_TOOLKIT)

        if to_toolkit:
            if self.toolkit_active:
                return True, "Toolkit 驱动已是当前状态"
            if os.path.exists(tp):
                os.rename(dp, op)
                os.rename(tp, dp)
                self.toolkit_active = True
                self.driver_version = "PSVR2Toolkit (激活)"
                log.info("已切换到 PSVR2Toolkit 驱动")
                return True, "已切换到 PSVR2Toolkit 驱动"
            if os.path.exists(op):
                os2 = os.path.getsize(op)
                if os2 < 500000:
                    os.rename(dp, tp)
                    os.rename(op, dp)
                    self.toolkit_active = True
                    self.driver_version = "PSVR2Toolkit (激活)"
                    log.info("已切换到 PSVR2Toolkit 驱动")
                    return True, "已切换到 PSVR2Toolkit 驱动"
            return False, "未找到 PSVR2Toolkit 驱动文件"
        else:
            if not self.toolkit_active:
                return True, "官方驱动已是当前状态"
            if os.path.exists(op):
                os2 = os.path.getsize(op)
                if os2 > 3000000:
                    os.rename(dp, tp)
                    os.rename(op, dp)
                    self.toolkit_active = False
                    self.driver_version = "官方驱动"
                    log.info("已切换回官方驱动")
                    return True, "已切换回官方驱动"
                os.rename(op, dp)
                self.toolkit_active = False
                self.driver_version = "官方驱动"
                return True, "已切换回官方驱动"
            if os.path.exists(tp):
                os.rename(dp, DRIVER_DLL + ".bak")
                os.rename(tp, dp)
                self.toolkit_active = False
                self.driver_version = "官方驱动"
                return True, "已切换回官方驱动"
            return False, "未找到官方驱动备份"

    def backup(self) -> Tuple[bool, str]:
        """创建带时间戳的驱动备份"""
        if not self.driver_dir:
            return False, "未找到驱动目录"
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = BACKUP_DIR / ts
        dst.mkdir(parents=True, exist_ok=True)
        copied = []
        for fname in [DRIVER_DLL, DRIVER_ORIG, DRIVER_TOOLKIT]:
            src = os.path.join(self.driver_dir, fname)
            if os.path.exists(src):
                shutil.copy2(src, dst / fname)
                copied.append(fname)
        info = {
            "timestamp": ts,
            "active": "toolkit" if self.toolkit_active else "official",
            "version": self.driver_version,
            "driver_dir": self.driver_dir,
            "files": copied,
        }
        with open(dst / "backup_info.json", "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
        log.info(f"驱动备份已创建: {ts} ({len(copied)} 个文件)")
        return True, f"备份已创建：{ts} ({len(copied)} 个文件)"

    def list_backups(self) -> List[Dict]:
        backups = []
        if not BACKUP_DIR.exists():
            return backups
        for d in sorted(BACKUP_DIR.iterdir(), reverse=True):
            info_file = d / "backup_info.json"
            if info_file.exists():
                try:
                    with open(info_file, "r", encoding="utf-8") as f:
                        backups.append(json.load(f))
                except Exception:
                    backups.append({"timestamp": d.name, "active": "未知", "files": []})
        return backups

    def restore(self, ts: str) -> Tuple[bool, str]:
        if not self.driver_dir:
            return False, "未找到驱动目录"
        src = BACKUP_DIR / ts
        if not src.exists():
            return False, f"备份不存在：{ts}"
        dp = os.path.join(self.driver_dir, DRIVER_DLL)
        if os.path.exists(dp):
            os.rename(dp, os.path.join(self.driver_dir, DRIVER_DLL + ".pre_restore"))
        for fname in [DRIVER_DLL, DRIVER_ORIG, DRIVER_TOOLKIT]:
            s = src / fname
            if s.exists():
                shutil.copy2(s, os.path.join(self.driver_dir, fname))
        # 更新状态
        info_file = src / "backup_info.json"
        if info_file.exists():
            with open(info_file, "r", encoding="utf-8") as f:
                info = json.load(f)
            self.toolkit_active = info.get("active") == "toolkit"
        self.driver_version = "PSVR2Toolkit (激活)" if self.toolkit_active else "官方驱动"
        log.info(f"驱动已从备份恢复: {ts}")
        return True, f"已从备份恢复：{ts}"

    def delete_backup(self, ts: str) -> Tuple[bool, str]:
        p = BACKUP_DIR / ts
        if p.exists():
            shutil.rmtree(p)
            log.info(f"备份已删除: {ts}")
            return True, f"备份已删除：{ts}"
        return False, "备份不存在"

    def check_update(self) -> Tuple[bool, str]:
        try:
            req = urllib.request.Request(PSVR2TOOLKIT_API)
            req.add_header("User-Agent", "PSVR2Panel/4.0")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self.latest_version = data.get("tag_name", "unknown")
                for asset in data.get("assets", []):
                    if asset["name"].endswith(".dll"):
                        self.latest_url = asset["browser_download_url"]
                        break
                log.info(f"版本检查完成: {self.latest_version}")
                return True, self.latest_version
        except Exception as e:
            log.warning(f"版本检查失败: {e}")
            return False, str(e)


# ============================================================
# VRCFaceTracking 集成
# ============================================================
class VRCFaceTracking:
    def __init__(self):
        self.installed: bool = False
        self.path: Optional[str] = None
        self.is_running: bool = False
        self.bundled: bool = False

    def find_installation(self) -> bool:
        for p in VRCFT_PATHS:
            if p.exists():
                self.installed = True
                self.path = str(p)
                self.bundled = False
                return True
        appdata = Path.home() / "AppData" / "Local"
        if appdata.exists():
            for folder in appdata.iterdir():
                if "vrcfacetracking" in folder.name.lower():
                    exe = folder / "VRCFaceTracking.exe"
                    if exe.exists():
                        self.installed = True
                        self.path = str(exe)
                        self.bundled = False
                        return True
        if VRCFT_DEPLOY.exists():
            exe = VRCFT_DEPLOY / "VRCFaceTracking.exe"
            if exe.exists():
                self.installed = True
                self.path = str(exe)
                self.bundled = True
                return True
        return False

    def check_running(self) -> bool:
        self.is_running = _process_running("VRCFaceTracking.exe")
        return self.is_running

    def launch(self) -> bool:
        if self.path and os.path.exists(self.path):
            _popen([self.path])
            log.info("VRCFaceTracking 已启动")
            return True
        return False


# ============================================================
# SteamVR 监控
# ============================================================
class SteamVRMonitor:
    def __init__(self):
        self.is_running: bool = False
        self.psvr2_detected: bool = False

    def check_running(self) -> bool:
        self.is_running = _process_running("vrserver.exe")
        return self.is_running


# ============================================================
# PS VR2 设备检测
# ============================================================
class PSVR2Detector:
    def __init__(self):
        self.connected: bool = False
        self.toolkit = PSVR2Toolkit()
        self.vrcft = VRCFaceTracking()
        self.steamvr = SteamVRMonitor()
        self.device_info: Dict[str, str] = {}
        self.features: Dict[str, Dict] = {
            "eye_tracking":        {"name": "👁 眼动追踪",      "desc": "VRChat 眼动追踪支持"},
            "head_vibration":      {"name": "📳 头显震动",      "desc": "头显震动反馈"},
            "adaptive_trigger":    {"name": "🎮 自适应扳机",    "desc": "Sense 控制器扳机阻力"},
            "hdr":                {"name": "🌈 HDR / 10-bit",  "desc": "HDR 高动态范围色彩"},
            "haptic_feedback":    {"name": "✋ 触觉反馈",      "desc": "控制器触觉反馈"},
            "passthrough":        {"name": "📷 透视视图",      "desc": "摄像头透视模式"},
        }

    def detect_all(self) -> bool:
        self._detect_connection()
        self.toolkit.find_installation()
        self.vrcft.find_installation()
        self.vrcft.check_running()
        self.steamvr.check_running()
        self._update_features()
        return self.connected

    def _detect_connection(self):
        r = _run([
            "powershell", "-Command",
            "Get-PnpDevice | Where-Object {$_.FriendlyName -match 'PlayStation|PSVR|VR2'} | "
            "Select-Object FriendlyName, Status, DeviceID | ConvertTo-Json -Compress"
        ])
        if r.returncode == 0 and r.stdout.strip():
            try:
                devs = json.loads(r.stdout)
                if isinstance(devs, dict):
                    devs = [devs]
                for d in devs:
                    if d.get("Status") == "OK":
                        self.connected = True
                        self.device_info = {
                            "name": d.get("FriendlyName", "PS VR2"),
                            "status": d.get("Status", "OK"),
                            "device_id": d.get("DeviceID", "—"),
                        }
                        return
            except json.JSONDecodeError:
                pass
        if self.toolkit.driver_installed:
            self.connected = True
            self.device_info = {"name": "PS VR2", "status": "已安装驱动", "device_id": "—"}
        else:
            self.connected = False
            self.device_info = {}

    def _update_features(self):
        sm = self.toolkit.get_feature_status()
        for k, v in self.features.items():
            v["status"], v["color"] = sm.get(k, ("未知", "gray"))

    def refresh_runtime(self):
        self.vrcft.check_running()
        self.steamvr.check_running()


# ============================================================
# SteamVR 设置管理
# ============================================================
class SteamVRSettings:
    def __init__(self):
        self.path = _steamvr_settings_path()
        self.data: Dict = {}
        self.original: str = ""

    def load(self) -> bool:
        if not self.path:
            return False
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self.original = f.read()
            self.data = json.loads(self.original)
            return True
        except Exception as e:
            log.warning(f"SteamVR 设置读取失败: {e}")
            return False

    def save(self) -> Tuple[bool, str]:
        if not self.path:
            return False, "SteamVR 设置文件未找到"
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            return True, "设置已保存（重启 SteamVR 生效）"
        except Exception as e:
            return False, f"保存失败: {e}"

    def get(self, key: str, default=None):
        return self.data.get("steamvr", {}).get(key, default)

    def set(self, key: str, value):
        if "steamvr" not in self.data:
            self.data["steamvr"] = {}
        self.data["steamvr"][key] = value


# ============================================================
# 卡片组件
# ============================================================
def card(parent, title: str = "", pad: int = 12) -> Tuple[tk.Frame, tk.Frame]:
    """创建卡片 Frame，返回 (frame, content)"""
    f = tk.Frame(parent, bg=C["card"],
                 highlightbackground=C["card_hi"], highlightthickness=1)
    f.pack(fill="x", padx=12, pady=4)
    if title:
        tk.Label(f, text=title, font=("Microsoft YaHei", 10, "bold"),
                 fg=C["text_sub"], bg=C["card"]).pack(anchor="w", padx=pad, pady=(pad, 0))
    content = tk.Frame(f, bg=C["card"])
    content.pack(fill="x", padx=pad, pady=(4 if title else pad, pad))
    return f, content


def btn(parent, text: str, cmd, color: str = "accent", width: int = 0) -> tk.Button:
    colors = {
        "accent": (C["accent"], C["accent_hi"]),
        "green": (C["green"], "#00e676"),
        "red": (C["red"], "#ff5252"),
        "orange": (C["orange"], "#ffab40"),
        "gray": (C["card_hi"], "#2a3a6a"),
        "teal": (C["teal"], "#26c6da"),
    }
    bg, ah = colors.get(color, colors["accent"])
    b = tk.Button(parent, text=text, font=("Microsoft YaHei", 9),
                  bg=bg, activebackground=ah, fg=C["text"],
                  relief=tk.FLAT, cursor="hand2", command=cmd)
    if width:
        b.config(width=width)
    return b


# ============================================================
# 主面板
# ============================================================
class PSVR2Panel:
    def __init__(self):
        self.detector = PSVR2Detector()
        self.sv_settings = SteamVRSettings()
        self._stop_monitor = threading.Event()
        self._monitor_lock = threading.Lock()

        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("580x720")
        self.root.minsize(420, 560)
        self.root.configure(bg=C["bg"])

        self._build_ui()
        self._run_detection()
        self._start_monitor()

        log.info(f"{APP_NAME} v{APP_VERSION} 已启动")

    # ── 界面构建 ──────────────────────────────────────────
    def _build_ui(self):
        # 顶部标题栏
        header = tk.Frame(self.root, bg=C["bg"])
        header.pack(fill="x", padx=16, pady=(10, 0))
        tk.Label(header, text=f"🎮 {APP_NAME}",
                 font=("Microsoft YaHei", 18, "bold"),
                 fg=C["text"], bg=C["bg"]).pack(side="left")
        tk.Label(header, text=f"v{APP_VERSION}",
                 font=("Microsoft YaHei", 10),
                 fg=C["text_sub"], bg=C["bg"]).pack(side="left", padx=(8, 0))

        # 刷新按钮
        btn(header, "🔄", self._run_detection, "gray").pack(side="right")

        # 标签页
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=12, pady=(8, 0))

        self.tab_dash = tk.Frame(self.nb, bg=C["bg"])
        self.tab_driver = tk.Frame(self.nb, bg=C["bg"])
        self.tab_settings = tk.Frame(self.nb, bg=C["bg"])

        self.nb.add(self.tab_dash, text="📊 仪表盘")
        self.nb.add(self.tab_driver, text="🔧 驱动")
        self.nb.add(self.tab_settings, text="⚙️ 设置")

        self._build_dashboard()
        self._build_driver_tab()
        self._build_settings_tab()
        self._build_bottom_bar()

    def _build_dashboard(self):
        p = self.tab_dash

        # ── 连接状态卡片 ──
        _, c = card(p, "")
        conn = tk.Frame(c, bg=C["card"])
        conn.pack(fill="x")
        self.conn_dot = tk.Label(conn, text="●", font=("Arial", 18),
                                  fg=C["yellow"], bg=C["card"])
        self.conn_dot.pack(side="left", padx=(0, 8), pady=8)
        self.conn_lbl = tk.Label(conn, text="正在检测...",
                                  font=("Microsoft YaHei", 11, "bold"),
                                  fg=C["text"], bg=C["card"], anchor="w")
        self.conn_lbl.pack(side="left", fill="x", expand=True)

        # ── 设备信息 + 运行状态（两列）──
        row = tk.Frame(p, bg=C["bg"])
        row.pack(fill="x", padx=12, pady=0)

        # 设备信息
        _, dev_c = card(row, "📋 设备信息")
        self.dev_name_lbl = tk.Label(dev_c, text="—",
                                      font=("Microsoft YaHei", 9, "bold"),
                                      fg=C["text"], bg=C["card"], anchor="w")
        self.dev_name_lbl.pack(fill="x")
        self.dev_status_lbl = tk.Label(dev_c, text="状态: —",
                                       font=("Microsoft YaHei", 9),
                                       fg=C["text_sub"], bg=C["card"], anchor="w")
        self.dev_status_lbl.pack(fill="x")

        # 运行状态
        _, run_c = card(row, "🥽 运行状态")
        steamvr_frame = tk.Frame(run_c, bg=C["card"])
        steamvr_frame.pack(fill="x")
        tk.Label(steamvr_frame, text="SteamVR:", font=("Microsoft YaHei", 9),
                 fg=C["text_sub"], bg=C["card"]).pack(side="left")
        self.steamvr_lbl = tk.Label(steamvr_frame, text="—",
                                     font=("Microsoft YaHei", 9, "bold"),
                                     fg=C["text"], bg=C["card"])
        self.steamvr_lbl.pack(side="right")
        vrcft_frame = tk.Frame(run_c, bg=C["card"])
        vrcft_frame.pack(fill="x", pady=(4, 0))
        tk.Label(vrcft_frame, text="VRCFT:", font=("Microsoft YaHei", 9),
                 fg=C["text_sub"], bg=C["card"]).pack(side="left")
        self.vrcft_lbl = tk.Label(vrcft_frame, text="—",
                                   font=("Microsoft YaHei", 9, "bold"),
                                   fg=C["text"], bg=C["card"])
        self.vrcft_lbl.pack(side="right")

        # ── 功能状态 ──
        _, feat_c = card(p, "📊 功能解锁状态")
        feat_grid = tk.Frame(feat_c, bg=C["card"])
        feat_grid.pack(fill="x")
        self.feat_labels: Dict[str, tk.Label] = {}
        items = list(self.detector.features.items())
        for i, (k, v) in enumerate(items):
            col = i % 2
            row_f = i // 2
            cell = tk.Frame(feat_grid, bg=C["card"])
            cell.grid(row=row_f, column=col, sticky="w", padx=4, pady=2)
            tk.Label(cell, text=v["name"], font=("Microsoft YaHei", 9),
                     fg=C["text"], bg=C["card"]).pack(anchor="w")
            lbl = tk.Label(cell, text="检测中...",
                           font=("Microsoft YaHei", 8),
                           fg=C["text_sub"], bg=C["card"])
            lbl.pack(anchor="w")
            self.feat_labels[k] = lbl

    def _build_driver_tab(self):
        p = self.tab_driver

        # 当前驱动状态
        _, c = card(p, "")
        drv = tk.Frame(c, bg=C["card"])
        drv.pack(fill="x")
        tk.Label(drv, text="当前驱动:", font=("Microsoft YaHei", 10),
                 fg=C["text_sub"], bg=C["card"]).pack(side="left")
        self.drv_version_lbl = tk.Label(drv, text="检测中...",
                                         font=("Microsoft YaHei", 10, "bold"),
                                         fg=C["text"], bg=C["card"])
        self.drv_version_lbl.pack(side="left", padx=(6, 0))
        self.drv_switch_btn = btn(drv, "切换驱动", self._switch_driver, "orange")
        self.drv_switch_btn.pack(side="right")

        _, c = card(p, "📂 驱动目录")
        drv_dir_frame = tk.Frame(c, bg=C["card"])
        drv_dir_frame.pack(fill="x")
        self.drv_dir_lbl = tk.Label(drv_dir_frame, text="未找到",
                                     font=("Microsoft YaHei", 9),
                                     fg=C["text_sub"], bg=C["card"], anchor="w")
        self.drv_dir_lbl.pack(side="left", fill="x", expand=True)
        btn(drv_dir_frame, "📁", self._open_driver_dir, "gray", 4).pack(side="right")

        # 版本检查
        _, c = card(p, "🔄 版本检查")
        ver_frame = tk.Frame(c, bg=C["card"])
        ver_frame.pack(fill="x")
        tk.Label(ver_frame, text="最新版本:", font=("Microsoft YaHei", 9),
                 fg=C["text_sub"], bg=C["card"]).pack(side="left")
        self.update_lbl = tk.Label(ver_frame, text="未检查",
                                    font=("Microsoft YaHei", 9, "bold"),
                                    fg=C["text"], bg=C["card"])
        self.update_lbl.pack(side="left", padx=(6, 0))
        self.update_btn = btn(ver_frame, "🔍 检查", self._check_update, "accent", 8)
        self.update_btn.pack(side="right")

        # 备份管理
        _, c = card(p, "💾 驱动备份")
        self.backup_listbox = tk.Listbox(c, font=("Microsoft YaHei", 9),
                                          bg=C["card_hi"], fg=C["text"],
                                          selectbackground=C["accent"],
                                          selectforeground=C["text"],
                                          highlightthickness=0, bd=0,
                                          height=5)
        self.backup_listbox.pack(fill="x", pady=(0, 6))
        backup_btn_frame = tk.Frame(c, bg=C["card"])
        backup_btn_frame.pack(fill="x")
        btn(backup_btn_frame, "💾 创建备份", self._do_backup, "teal", 10).pack(side="left", padx=(0, 4))
        self.restore_btn = btn(backup_btn_frame, "♻ 恢复", self._do_restore, "accent", 8)
        self.restore_btn.pack(side="left", padx=(0, 4))
        btn(backup_btn_frame, "🗑 删除", self._delete_backup, "red", 8).pack(side="right")
        self._refresh_backup_list()

    def _build_settings_tab(self):
        p = self.tab_settings
        self.sv_settings.load()

        _, c = card(p, "🎯 SteamVR 渲染设置")
        info_lbl = tk.Label(c,
                             text="调整 SteamVR 渲染参数，重启 SteamVR 后生效",
                             font=("Microsoft YaHei", 8),
                             fg=C["text_sub"], bg=C["card"])
        info_lbl.pack(anchor="w", pady=(0, 8))

        # 超采样
        tk.Label(c, text="渲染缩放 (超采样)",
                 font=("Microsoft YaHei", 9), fg=C["text"], bg=C["card"]).pack(anchor="w")
        sample_frame = tk.Frame(c, bg=C["card"])
        sample_frame.pack(fill="x", pady=(2, 0))
        self.sample_scale = tk.DoubleVar(
            value=float(self.sv_settings.get("renderTargetMultiplier", 1.0)))
        scale_slider = ttk.Scale(sample_frame, from_=0.5, to_=2.0,
                                  variable=self.sample_scale, orient="horizontal",
                                  command=lambda _: self._update_scale_lbl())
        scale_slider.pack(side="left", fill="x", expand=True)
        self.scale_lbl = tk.Label(sample_frame, text="100%",
                                   font=("Microsoft YaHei", 9, "bold"),
                                   fg=C["accent"], bg=C["card"], width=6)
        self.scale_lbl.pack(side="right")
        self._update_scale_lbl()

        # 复选框
        cb_frame = tk.Frame(c, bg=C["card"])
        cb_frame.pack(fill="x", pady=(10, 0))
        self.cb_filter = tk.BooleanVar(
            value=bool(self.sv_settings.get("allowSupersampleFiltering", True)))
        ttk.Checkbutton(cb_frame, text="超采样过滤 (更平滑)",
                        variable=self.cb_filter,
                        style="TCheckbutton").pack(anchor="w")
        self.cb_smooth = tk.BooleanVar(
            value=bool(self.sv_settings.get("motionSmoothing", True)))
        ttk.Checkbutton(cb_frame, text="运动平滑",
                        variable=self.cb_smooth,
                        style="TCheckbutton").pack(anchor="w", pady=(4, 0))

        # 操作按钮
        btn_frame = tk.Frame(c, bg=C["card"])
        btn_frame.pack(fill="x", pady=(12, 0))
        btn(btn_frame, "💾 应用设置", self._apply_sv_settings, "green", 11).pack(side="left", padx=(0, 6))
        btn(btn_frame, "↩ 恢复默认", self._reset_sv_settings, "gray", 10).pack(side="left")

        if not self.sv_settings.path:
            tk.Label(c, text="⚠ SteamVR 设置文件未找到",
                     font=("Microsoft YaHei", 8), fg=C["yellow"],
                     bg=C["card"], anchor="w").pack(pady=(8, 0))

        # ── 一键启动 ──
        _, c2 = card(p, "🚀 快速启动")
        btn(c2, "🚀 启动 SteamVR + VRCFT", self._launch_all, "green").pack(fill="x", pady=2)
        startup_frame = tk.Frame(c2, bg=C["card"])
        startup_frame.pack(fill="x", pady=(4, 0))
        btn(startup_frame, "SteamVR", self._launch_steamvr, "accent", 9).pack(side="left", padx=(0, 4))
        btn(startup_frame, "VRCFT", self._launch_vrcft, "accent", 9).pack(side="left")
        btn(startup_frame, "VRCFT (Steam)", self._open_vrcft_steam, "gray", 12).pack(side="right")

    def _build_bottom_bar(self):
        bar = tk.Frame(self.root, bg=C["bg"])
        bar.pack(fill="x", padx=12, pady=(6, 8))
        btn(bar, "🚀 一键启动全部", self._launch_all, "green").pack(side="left", fill="x", expand=True, padx=(0, 4))
        btn(bar, "ℹ 关于", self._show_about, "gray", 8).pack(side="right")

    # ── 检测与监控 ──────────────────────────────────────
    def _run_detection(self):
        def detect():
            self.detector.detect_all()
            self.root.after(0, self._update_ui)

        threading.Thread(target=detect, daemon=True).start()

    def _update_ui(self):
        d = self.detector

        # 连接状态
        if d.connected:
            self.conn_dot.config(fg=C["green"])
            self.conn_lbl.config(text="✅ PS VR2 已连接")
            dev = d.device_info
            self.dev_name_lbl.config(text=dev.get("name", "PS VR2"))
            self.dev_status_lbl.config(text=f"状态: {dev.get('status', 'OK')}")
        else:
            self.conn_dot.config(fg=C["red"])
            self.conn_lbl.config(text="❌ PS VR2 未检测到")
            self.dev_name_lbl.config(text="—")
            self.dev_status_lbl.config(text="状态: 未连接")

        # 运行状态
        sv = d.steamvr
        self.steamvr_lbl.config(
            text="▶ 运行中" if sv.is_running else "⏹ 未运行",
            fg=C["green"] if sv.is_running else C["text_sub"])

        vrcft = d.vrcft
        if vrcft.is_running:
            tag = "内置" if vrcft.bundled else ""
            self.vrcft_lbl.config(text=f"▶ 运行中{tag}", fg=C["green"])
        elif vrcft.installed:
            tag = "内置" if vrcft.bundled else ""
            self.vrcft_lbl.config(text=f"已安装{tag}", fg=C["text"])
        else:
            self.vrcft_lbl.config(text="❌ 未安装", fg=C["red"])

        # 功能状态
        color_map = {"green": C["green"], "red": C["red"],
                     "yellow": C["yellow"], "gray": C["text_sub"]}
        for k, lbl in self.feat_labels.items():
            v = d.features.get(k, {})
            lbl.config(text=v.get("status", "—"),
                       fg=color_map.get(v.get("color", "gray"), C["text_sub"]))

        # 驱动
        tk_info = d.toolkit
        if tk_info.driver_installed:
            self.drv_version_lbl.config(text=tk_info.driver_version,
                                         fg=C["green"] if tk_info.toolkit_active else C["yellow"])
            self.drv_switch_btn.config(
                text="⏪ 恢复官方" if tk_info.toolkit_active else "🔄 切换Toolkit",
                bg=C["accent"] if tk_info.toolkit_active else C["orange"],
                activebackground=C["accent_hi"])
            self.drv_dir_lbl.config(text=tk_info.driver_dir or "—")
        else:
            self.drv_version_lbl.config(text="❌ 未安装驱动", fg=C["red"])
            self.drv_switch_btn.config(text="切换驱动", state="disabled")
            self.drv_dir_lbl.config(text="未找到驱动目录")

    def _start_monitor(self):
        def loop():
            while not self._stop_monitor.wait(3):
                self.detector.refresh_runtime()
                self.root.after(0, self._update_runtime_ui)

        t = threading.Thread(target=loop, daemon=True)
        t.start()

    def _update_runtime_ui(self):
        sv = self.detector.steamvr
        self.steamvr_lbl.config(
            text="▶ 运行中" if sv.is_running else "⏹ 未运行",
            fg=C["green"] if sv.is_running else C["text_sub"])
        vrcft = self.detector.vrcft
        if vrcft.is_running:
            tag = "内置" if vrcft.bundled else ""
            self.vrcft_lbl.config(text=f"▶ 运行中{tag}", fg=C["green"])
        elif vrcft.installed:
            tag = "内置" if vrcft.bundled else ""
            self.vrcft_lbl.config(text=f"已安装{tag}", fg=C["text"])
        else:
            self.vrcft_lbl.config(text="❌ 未安装", fg=C["red"])

    # ── 驱动操作 ────────────────────────────────────────
    def _switch_driver(self):
        tk_info = self.detector.toolkit
        to_toolkit = not tk_info.toolkit_active
        action = "切换到 PSVR2Toolkit" if to_toolkit else "切换回官方驱动"
        confirm = messagebox.askyesno("确认", f"{action}？\n\n需要重启 SteamVR 生效")
        if not confirm:
            return

        success, msg = tk_info.switch(to_toolkit)
        if success:
            messagebox.showinfo("成功", msg)
            self._run_detection()
        else:
            messagebox.showerror("失败", msg)

    def _open_driver_dir(self):
        d = self.detector.toolkit.driver_dir
        if d:
            _open_in_explorer(d)
        else:
            messagebox.showwarning("提示", "未找到驱动目录")

    def _check_update(self):
        self.update_lbl.config(text="检查中...", fg=C["text_sub"])
        self.update_btn.config(state="disabled")

        def check():
            ok, ver = self.detector.toolkit.check_update()
            self.root.after(0, self._on_update_checked, ok, ver)

        threading.Thread(target=check, daemon=True).start()

    def _on_update_checked(self, ok, ver):
        self.update_btn.config(state="normal")
        if ok:
            self.update_lbl.config(text=ver, fg=C["green"])
            messagebox.showinfo("版本检查", f"最新版本: {ver}")
        else:
            self.update_lbl.config(text="检查失败", fg=C["red"])

    # ── 备份操作 ────────────────────────────────────────
    def _refresh_backup_list(self):
        self.backup_listbox.delete(0, "end")
        for b in self.detector.toolkit.list_backups():
            ts = b.get("timestamp", "?")
            active = b.get("active", "?")
            files = len(b.get("files", []))
            label = f"📦 {ts}  [{active}]  {files}个文件"
            self.backup_listbox.insert("end", label)

    def _do_backup(self):
        success, msg = self.detector.toolkit.backup()
        if success:
            messagebox.showinfo("备份", msg)
            self._refresh_backup_list()
        else:
            messagebox.showerror("备份失败", msg)

    def _do_restore(self):
        sel = self.backup_listbox.curselection()
        if not sel:
            messagebox.showwarning("提示", "请先选择要恢复的备份")
            return
        label = self.backup_listbox.get(sel[0])
        ts = label.split()[1]
        confirm = messagebox.askyesno("确认", f"从备份 [{ts}] 恢复？\n需要重启 SteamVR 生效")
        if not confirm:
            return
        success, msg = self.detector.toolkit.restore(ts)
        if success:
            messagebox.showinfo("恢复", msg)
            self._run_detection()
        else:
            messagebox.showerror("恢复失败", msg)

    def _delete_backup(self):
        sel = self.backup_listbox.curselection()
        if not sel:
            messagebox.showwarning("提示", "请先选择要删除的备份")
            return
        label = self.backup_listbox.get(sel[0])
        ts = label.split()[1]
        confirm = messagebox.askyesno("确认", f"删除备份 [{ts}]？")
        if not confirm:
            return
        success, msg = self.detector.toolkit.delete_backup(ts)
        if success:
            messagebox.showinfo("删除", msg)
            self._refresh_backup_list()
        else:
            messagebox.showerror("删除失败", msg)

    # ── SteamVR 设置 ────────────────────────────────────
    def _update_scale_lbl(self):
        val = self.sample_scale.get()
        self.scale_lbl.config(text=f"{int(val * 100)}%")

    def _apply_sv_settings(self):
        self.sv_settings.load()
        self.sv_settings.set("renderTargetMultiplier", self.sample_scale.get())
        self.sv_settings.set("allowSupersampleFiltering", self.cb_filter.get())
        self.sv_settings.set("motionSmoothing", self.cb_smooth.get())
        success, msg = self.sv_settings.save()
        if success:
            messagebox.showinfo("设置", msg)
        else:
            messagebox.showerror("设置失败", msg)

    def _reset_sv_settings(self):
        self.sample_scale.set(1.0)
        self.cb_filter.set(True)
        self.cb_smooth.set(True)
        self._update_scale_lbl()
        messagebox.showinfo("重置", "已恢复默认值，请点击「应用设置」保存")

    # ── 启动操作 ────────────────────────────────────────
    def _launch_steamvr(self):
        for p in STEAMVR_PATHS:
            if os.path.exists(p):
                _popen([p])
                log.info("SteamVR 已启动")
                time.sleep(1)
                self._run_detection()
                return
        try:
            os.startfile("steam://rungameid/250820")
            time.sleep(1)
            self._run_detection()
        except Exception:
            messagebox.showwarning("未找到", "SteamVR 未安装")

    def _launch_vrcft(self):
        if self.detector.vrcft.launch():
            time.sleep(1)
            self._run_detection()
        else:
            messagebox.showwarning("未安装", "VRCFaceTracking 未安装\n可点击「VRCFT (Steam)」安装")

    def _launch_all(self):
        self._launch_steamvr()
        time.sleep(2)
        self._launch_vrcft()

    def _open_vrcft_steam(self):
        try:
            os.startfile(VRCFT_STEAM_URL)
        except Exception:
            os.startfile("https://store.steampowered.com/app/658580/VRCFaceTracking/")

    # ── 关于 ────────────────────────────────────────────
    def _show_about(self):
        messagebox.showinfo(
            f"关于 {APP_NAME}",
            f"{APP_NAME} v{APP_VERSION}\n\n"
            f"PlayStation VR2 PC 控制面板\n"
            f"深度集成 PSVR2Toolkit 工具链\n\n"
            f"v4.0.0 更新：\n"
            f"  🎨 全新 UI / 分 Tab 布局\n"
            f"  💾 驱动备份/恢复\n"
            f"  ⚙️ SteamVR 快速设置\n"
            f"  ⚡ tasklist 替代 PowerShell\n"
            f"  📊 设备信息面板\n\n"
            f"作者: {APP_AUTHOR}\n"
            f"{GITEE_URL}"
        )

    def run(self):
        self.root.mainloop()
        self._stop_monitor.set()

    def destroy(self):
        self._stop_monitor.set()
        self.root.destroy()


# ============================================================
# 入口
# ============================================================
if __name__ == "__main__":
    try:
        app = PSVR2Panel()
        app.run()
    except Exception as e:
        log.exception("Fatal error")
        messagebox.showerror("错误", f"程序异常退出:\n{e}")
