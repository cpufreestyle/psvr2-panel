#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PS VR2 PC 控制面板 — PSVR2 Panel v4.7.0
一键管理 PS VR2 在 PC 上的解锁功能，深度集成 PSVR2Toolkit 工具链

v4.7.0 更新：
  🎛 新增 Toolkit 调节面板：屏幕亮度滑条（steamvr.analogGain）+
     5 项 Toolkit 开关（playstation_vr2_ex 节，键名查证自官方源码）

作者: Michael Qiu (cpufreestyle)
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import subprocess
import json
import os
import re
import sys
import threading
import time
import logging
import logging.handlers
import urllib.request
import winreg
import shutil
import winsound
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from auto_updater import check_update_background

# ============================================================
# 常量 & 主题
# ============================================================
APP_NAME = "PSVR2 Panel"
APP_VERSION = "4.7.0"
APP_AUTHOR = "Michael Qiu"
GITEE_URL = "https://gitee.com/cpufreestyle/psvr2-panel"
GITHUB_URL = "https://github.com/cpufreestyle/psvr2-panel"

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
    "green_hi": "#00e676",
    "red": "#ff1744",
    "red_hi": "#ff5252",
    "yellow": "#ffd600",
    "orange": "#ff9100",
    "orange_hi": "#ffab40",
    "teal": "#00bcd4",
    "teal_hi": "#4dd0e1",
    "gray": "#5a5a6e",
    "gray_hi": "#7a7a8e",
}

# ============================================================
# Steam 路径检测（注册表 + libraryfolders.vdf，硬编码回退）
# ============================================================
def _steam_library_roots() -> List[str]:
    """收集所有 Steam 库根目录（游戏位于 <root>\\steamapps\\common\\）"""
    roots: List[str] = []
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\WOW6432Node\Valve\Steam", 0, winreg.KEY_READ
        )
        install_path, _ = winreg.QueryValueEx(key, "InstallPath")
        winreg.CloseKey(key)
        if install_path:
            roots.append(install_path)
            vdf = Path(install_path) / "steamapps" / "libraryfolders.vdf"
            if vdf.exists():
                try:
                    text = vdf.read_text(encoding="utf-8", errors="replace")
                    for m in re.findall(r'"path"\s+"([^"]+)"', text):
                        p = m.replace("\\\\", "\\")
                        if p and p not in roots:
                            roots.append(p)
                except OSError as e:
                    log.warning(f"解析 libraryfolders.vdf 失败: {e}")
    except OSError:
        pass
    # 硬编码回退（注册表不可用时）
    for fallback in (r"C:\Program Files (x86)\Steam", r"D:\Program Files (x86)\Steam"):
        if fallback not in roots:
            roots.append(fallback)
    return roots


def _build_steam_paths() -> Tuple[List[str], List[str]]:
    """生成驱动目录与 SteamVR 启动程序候选路径"""
    driver_dirs: List[str] = []
    steamvr_paths: List[str] = []
    for root in _steam_library_roots():
        root = root.rstrip("\\")
        drv = rf"{root}\steamapps\common\PlayStation VR2 App\SteamVR_Plug-In\bin\win64"
        svr = rf"{root}\steamapps\common\SteamVR\bin\win64\vrstartup.exe"
        if drv not in driver_dirs:
            driver_dirs.append(drv)
        if svr not in steamvr_paths:
            steamvr_paths.append(svr)
    return driver_dirs, steamvr_paths


DRIVER_DIRS, STEAMVR_PATHS = _build_steam_paths()
VRCFT_PATHS = [
    Path.home() / "AppData" / "Local" / "VRCFaceTracking" / "VRCFaceTracking.exe",
    Path("C:/Program Files/VRCFaceTracking/VRCFaceTracking.exe"),
]
VRCFT_DEPLOY = Path.home() / "AppData" / "Local" / "PSVR2Panel" / "VRCFaceTracking"
BACKUP_DIR = Path.home() / "AppData" / "Local" / "PSVR2Panel" / "backups"
BACKUP_KEEP = 5  # 驱动备份自动保留份数
LOG_DIR = Path.home() / "AppData" / "Local" / "PSVR2Panel" / "logs"
PROFILE_DIR = Path.home() / "AppData" / "Local" / "PSVR2Panel" / "profiles"

DRIVER_DLL = "driver_playstation_vr2.dll"
DRIVER_ORIG = "driver_playstation_vr2_orig.dll"
DRIVER_TOOLKIT = "driver_playstation_vr2_toolkit.dll"

PSVR2TOOLKIT_API = "https://api.github.com/repos/BnuuySolutions/PSVR2Toolkit/releases/latest"
VRCFT_MODULE_API = "https://api.github.com/repos/BnuuySolutions/PSVR2Toolkit.VRCFT/releases/latest"
VRCFT_API = "https://api.github.com/repos/benaclejames/VRCFaceTracking/releases/latest"
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


def _steamvr_settings_path() -> Optional[Path]:
    p = Path(os.environ.get("LOCALAPPDATA", "")) / "openvr" / "openvrsettings.vrsettings"
    if p.exists():
        return p
    return None


# ============================================================
# 开机启动管理
# ============================================================
def auto_start_enabled() -> bool:
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_READ
        )
        winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


def set_auto_start(enable: bool) -> bool:
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        if enable:
            exe_path = sys.executable
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{exe_path}"')
            log.info(f"开机启动已开启: {exe_path}")
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
                log.info("开机启动已关闭")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception as e:
        log.error(f"开机启动设置失败: {e}")
        return False


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
                    else:
                        self.toolkit_active = False
                        self.driver_version = "官方驱动"
                else:
                    self.toolkit_active = False
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
        try:
            return self._switch_impl(to_toolkit)
        except OSError as e:
            log.error(f"驱动切换失败: {e}")
            return False, "驱动文件被占用，请先关闭 SteamVR 后重试"

    def _switch_impl(self, to_toolkit: bool) -> Tuple[bool, str]:
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
                log.info("已切换回官方驱动")
                return True, "已切换回官方驱动"
            if os.path.exists(tp):
                os.rename(dp, os.path.join(self.driver_dir, DRIVER_DLL + ".bak"))
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
        try:
            for fname in [DRIVER_DLL, DRIVER_ORIG, DRIVER_TOOLKIT]:
                src = os.path.join(self.driver_dir, fname)
                if os.path.exists(src):
                    shutil.copy2(src, dst / fname)
                    copied.append(fname)
        except OSError as e:
            shutil.rmtree(dst, ignore_errors=True)
            log.error(f"备份失败: {e}")
            return False, "备份失败：驱动文件被占用，请先关闭 SteamVR"
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
        self.cleanup_backups()
        return True, f"备份已创建：{ts} ({len(copied)} 个文件)"

    def cleanup_backups(self, keep: int = BACKUP_KEEP) -> int:
        """保留最近 keep 份备份，删除更旧的，返回删除数量"""
        if not BACKUP_DIR.exists():
            return 0
        removed = 0
        dirs = sorted((d for d in BACKUP_DIR.iterdir() if d.is_dir()),
                      key=lambda p: p.name, reverse=True)
        for d in dirs[keep:]:
            try:
                shutil.rmtree(d)
                removed += 1
            except OSError as e:
                log.warning(f"清理备份失败: {d.name}: {e}")
        if removed:
            log.info(f"已自动清理 {removed} 份旧备份")
        return removed

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
        pre_restore = os.path.join(self.driver_dir, DRIVER_DLL + ".pre_restore")
        if os.path.exists(dp):
            os.rename(dp, pre_restore)
        try:
            for fname in [DRIVER_DLL, DRIVER_ORIG, DRIVER_TOOLKIT]:
                s = src / fname
                if s.exists():
                    shutil.copy2(s, os.path.join(self.driver_dir, fname))
        except OSError as e:
            if os.path.exists(pre_restore) and not os.path.exists(dp):
                os.rename(pre_restore, dp)
            log.error(f"恢复失败: {e}")
            return False, "恢复失败：驱动文件被占用，请先关闭 SteamVR"
        if os.path.exists(pre_restore):
            os.remove(pre_restore)
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

    def check_update(self) -> Tuple[bool, str, Optional[str]]:
        """返回 (成功, 版本, 下载链接)"""
        try:
            req = urllib.request.Request(PSVR2TOOLKIT_API)
            req.add_header("User-Agent", "PSVR2Panel/4.7")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self.latest_version = data.get("tag_name", "unknown")
                download_url = None
                for asset in data.get("assets", []):
                    name = asset.get("name", "").lower()
                    if name.endswith(".dll") or "playstation" in name:
                        download_url = asset.get("browser_download_url")
                        break
                log.info(f"版本检查完成: {self.latest_version}")
                return True, self.latest_version, download_url
        except Exception as e:
            log.warning(f"版本检查失败: {e}")
            return False, str(e), None

    def download_toolkit(self, url: str, progress_callback=None) -> Tuple[bool, str]:
        """下载 PSVR2Toolkit dll 文件到驱动目录"""
        if not self.driver_dir:
            return False, "未找到驱动目录"
        try:
            log.info(f"开始下载 PSVR2Toolkit: {url}")
            temp_dir = LOG_DIR / "downloads"
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_file = temp_dir / DRIVER_TOOLKIT

            req = urllib.request.Request(url)
            req.add_header("User-Agent", "PSVR2Panel/4.7")
            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 65536
                with open(temp_file, "wb") as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total:
                            progress_callback(downloaded, total)

            dest = os.path.join(self.driver_dir, DRIVER_TOOLKIT)
            shutil.move(str(temp_file), dest)
            log.info("PSVR2Toolkit 下载完成并已放置到驱动目录")
            return True, f"下载完成: {dest}"
        except Exception as e:
            log.error(f"下载失败: {e}")
            return False, f"下载失败: {e}"


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

    def get_local_version(self) -> Optional[str]:
        """读取 VRCFT exe 的文件版本号"""
        if not self.path:
            return None
        r = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                  f"(Get-Item -LiteralPath '{self.path}').VersionInfo.FileVersion"])
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
        return None

    def check_update(self) -> Tuple[bool, str, Optional[str]]:
        """检查 GitHub 最新 Release，返回 (成功, 版本, 安装包链接)"""
        try:
            req = urllib.request.Request(VRCFT_API)
            req.add_header("User-Agent", "PSVR2Panel/4.7")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            latest = data.get("tag_name", "unknown")
            url = None
            for asset in data.get("assets", []):
                if asset.get("name", "").lower().endswith(".exe"):
                    url = asset.get("browser_download_url")
                    break
            log.info(f"VRCFT 版本检查完成: {latest}")
            return True, latest, url
        except Exception as e:
            log.warning(f"VRCFT 版本检查失败: {e}")
            return False, str(e), None

    def download_installer(self, url: str, progress_callback=None) -> Tuple[bool, str]:
        """下载安装包，成功返回 (True, 本地文件路径)"""
        try:
            temp_dir = LOG_DIR / "downloads"
            temp_dir.mkdir(parents=True, exist_ok=True)
            name = url.split("/")[-1].split("?")[0] or "VRCFaceTracking_Setup.exe"
            temp_file = temp_dir / name
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "PSVR2Panel/4.7")
            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                with open(temp_file, "wb") as f:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total:
                            progress_callback(downloaded, total)
            log.info(f"VRCFT 安装包已下载: {temp_file}")
            return True, str(temp_file)
        except Exception as e:
            log.error(f"VRCFT 安装包下载失败: {e}")
            return False, f"下载失败: {e}"

    def get_modules_dir(self) -> Optional[Path]:
        """探测 VRCFT 模块目录（安装目录 Modules/ 优先，回退 AppData）"""
        candidates: List[Path] = []
        if self.path:
            install_dir = Path(self.path).parent
            candidates += [install_dir / "Modules", install_dir / "modules",
                           install_dir.parent / "Modules"]
        candidates.append(Path.home() / "AppData" / "Roaming" / "VRCFaceTracking" / "Modules")
        for c in candidates:
            if c.exists():
                return c
        return None

    def get_module_status(self) -> Optional[str]:
        """检查 PSVR2 眼动模块是否已安装，返回模块 dll 文件名或 None"""
        mdir = self.get_modules_dir()
        if not mdir:
            return None
        try:
            for f in mdir.glob("*.dll"):
                if "psvr2" in f.name.lower():
                    return f.name
        except OSError as e:
            log.warning(f"扫描 VRCFT 模块目录失败: {e}")
        return None

    def check_module_update(self) -> Tuple[bool, str, Optional[str]]:
        """检查 PSVR2 VRCFT 模块最新 Release，返回 (成功, 版本, dll 链接)"""
        try:
            req = urllib.request.Request(VRCFT_MODULE_API)
            req.add_header("User-Agent", "PSVR2Panel/4.7")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            latest = data.get("tag_name", "unknown")
            url = None
            for asset in data.get("assets", []):
                if asset.get("name", "").lower().endswith(".dll"):
                    url = asset.get("browser_download_url")
                    break
            log.info(f"VRCFT 模块版本检查完成: {latest}")
            return True, latest, url
        except Exception as e:
            log.warning(f"VRCFT 模块版本检查失败: {e}")
            return False, str(e), None

    def install_module(self, url: str, progress_callback=None) -> Tuple[bool, str]:
        """下载 PSVR2 眼动模块 dll 部署到 VRCFT 模块目录，返回 (成功, 消息)"""
        mdir = self.get_modules_dir()
        if not mdir:
            return False, "未找到 VRCFT 模块目录\n请先安装 VRCFaceTracking"
        try:
            temp_dir = LOG_DIR / "downloads"
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_file = temp_dir / "PSVR2Toolkit.VRCFT.dll"
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "PSVR2Panel/4.7")
            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                with open(temp_file, "wb") as f:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total:
                            progress_callback(downloaded, total)
            dest = mdir / "PSVR2Toolkit.VRCFT.dll"
            shutil.move(str(temp_file), dest)
            log.info(f"VRCFT 眼动模块已部署: {dest}")
            return True, f"模块已部署：{dest}"
        except OSError as e:
            log.error(f"VRCFT 模块部署失败: {e}")
            return False, f"部署失败: {e}"


# ============================================================
# SteamVR 监控
# ============================================================
class SteamVRMonitor:
    def __init__(self):
        self.is_running: bool = False

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
            "eye_tracking":      {"name": "👁 眼动追踪",    "desc": "VRChat 眼动追踪支持"},
            "head_vibration":    {"name": "📳 头显震动",    "desc": "头显震动反馈"},
            "adaptive_trigger":  {"name": "🎮 自适应扳机",  "desc": "Sense 控制器扳机阻力"},
            "hdr":               {"name": "🌈 HDR / 10-bit","desc": "HDR 高动态范围色彩"},
            "haptic_feedback":   {"name": "✋ 触觉反馈",    "desc": "控制器触觉反馈"},
            "passthrough":       {"name": "📷 透视视图",    "desc": "摄像头透视模式"},
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
            "powershell", "-NoProfile", "-NonInteractive", "-Command",
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

    def refresh_connection(self) -> bool:
        old = self.connected
        self._detect_connection()
        self._update_features()
        return old != self.connected


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

    def get_in_section(self, section: str, key: str, default=None):
        return self.data.get(section, {}).get(key, default)

    def set_in_section(self, section: str, key: str, value):
        if section not in self.data:
            self.data[section] = {}
        self.data[section][key] = value


    # ── 预设管理 ──
    def save_profile(self, name: str) -> Tuple[bool, str]:
        if not self.data:
            return False, "没有可保存的设置"
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        safe = "".join(c for c in name if c.isalnum() or c in "_ -").strip()
        if not safe:
            return False, "预设名称无效"
        p = PROFILE_DIR / f"{safe}.json"
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"name": safe, "created": datetime.now().isoformat(),
                       "settings": self.data.get("steamvr", {})}, f, ensure_ascii=False, indent=2)
        log.info(f"预设已保存: {safe}")
        return True, f"预设「{safe}」已保存"

    def load_profile(self, name: str) -> Tuple[bool, str]:
        safe = "".join(c for c in name if c.isalnum() or c in "_ -").strip()
        p = PROFILE_DIR / f"{safe}.json"
        if not p.exists():
            return False, f"预设「{safe}」不存在"
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.load()
        if "steamvr" not in self.data:
            self.data["steamvr"] = {}
        self.data["steamvr"].update(data.get("settings", {}))
        success, msg = self.save()
        if success:
            return True, f"预设「{safe}」已应用（重启 SteamVR 生效）"
        return False, msg

    def delete_profile(self, name: str) -> Tuple[bool, str]:
        safe = "".join(c for c in name if c.isalnum() or c in "_ -").strip()
        p = PROFILE_DIR / f"{safe}.json"
        if p.exists():
            p.unlink()
            log.info(f"预设已删除: {safe}")
            return True, f"预设「{safe}」已删除"
        return False, "预设不存在"

    def list_profiles(self) -> List[str]:
        if not PROFILE_DIR.exists():
            return []
        return sorted(p.stem for p in PROFILE_DIR.glob("*.json"))

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
        "green":  (C["green"],  C["green_hi"]),
        "red":    (C["red"],    C["red_hi"]),
        "orange": (C["orange"], C["orange_hi"]),
        "gray":   (C["gray"],   C["gray_hi"]),
        "teal":   (C["teal"],   C["teal_hi"]),
    }
    bg, ah = colors.get(color, colors["accent"])
    b = tk.Button(parent, text=text, font=("Microsoft YaHei", 9),
                  bg=bg, activebackground=ah, fg=C["text"],
                  relief=tk.FLAT, cursor="hand2", command=cmd, bd=0)
    if width:
        b.config(width=width)
    b.bind("<Enter>", lambda e, _b=b, _c=ah: _b.config(bg=_c))
    b.bind("<Leave>", lambda e, _b=b, _c=bg: _b.config(bg=_c))
    return b


# ============================================================
# 主面板
# ============================================================

def section(parent, text: str, color: str = None) -> tk.Frame:
    """彩色分区标题栏"""
    bg = color or C["accent"]
    f = tk.Frame(parent, bg=bg, height=28)
    f.pack(fill="x", padx=12, pady=(12, 0))
    f.pack_propagate(False)
    tk.Label(f, text=f"  {text}", font=("Microsoft YaHei", 10, "bold"),
             fg=C["text"], bg=bg).pack(side="left")
    return f

class PSVR2Panel:
    def __init__(self):
        self.detector = PSVR2Detector()
        self.sv_settings = SteamVRSettings()
        self._stop_monitor = threading.Event()

        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("580x750")
        self.root.minsize(420, 580)
        self.root.configure(bg=C["bg"])
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_request)

        self._setup_ttk_theme()
        self._build_ui()
        self._run_detection()
        self._start_monitor()

        log.info(f"{APP_NAME} v{APP_VERSION} 已启动")

    def _setup_ttk_theme(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TNotebook", background=C["bg"], borderwidth=0)
        s.configure("TNotebook.Tab", background=C["card"], foreground=C["text"],
                     padding=[14, 6], font=("Microsoft YaHei", 9))
        s.map("TNotebook.Tab",
               background=[("selected", C["accent"])],
               foreground=[("selected", C["text"])])
        s.configure("TCheckbutton", background=C["card"], foreground=C["text"],
                     font=("Microsoft YaHei", 9))
        s.map("TCheckbutton", background=[("active", C["card_hi"])])
        s.configure("TScale", background=C["card"], troughcolor=C["card_hi"])
        s.configure("Vertical.TScrollbar", background=C["card_hi"],
                     troughcolor=C["bg"], arrowcolor=C["text"], borderwidth=0)

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

        # 刷新 + 关于按钮
        btn(header, "🔄", self._run_detection, "gray").pack(side="right")
        btn(header, "ℹ️", self._show_about, "gray").pack(side="right", padx=(0, 4))

        # 可滚动画布
        canvas = tk.Canvas(self.root, bg=C["bg"],
                           highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical",
                                  command=canvas.yview)
        self.scroll_frame = tk.Frame(canvas, bg=C["bg"])

        self.scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        self._canvas = canvas
        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw", tags="scroll_win")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(fill="both", expand=True, padx=0, pady=(8, 0))
        scrollbar.pack(fill="y", side="right", pady=(8, 0))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig("scroll_win", width=e.width - 16))

        # 鼠标滚轮支持
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self._build_dashboard()
        self._build_driver_tab()
        self._build_settings_tab()
        self._build_log_section()

    def _build_dashboard(self):
        section(self.scroll_frame, "📊 仪表盘", C["accent"])
        p = self.scroll_frame

        # 连接状态卡片
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

        # 设备信息 + 运行状态
        row = tk.Frame(p, bg=C["bg"])
        row.pack(fill="x", padx=0, pady=0)

        _, dev_c = card(row, "📋 设备信息")
        self.dev_name_lbl = tk.Label(dev_c, text="—",
                                      font=("Microsoft YaHei", 9, "bold"),
                                      fg=C["text"], bg=C["card"], anchor="w")
        self.dev_name_lbl.pack(fill="x")
        self.dev_status_lbl = tk.Label(dev_c, text="状态: —",
                                       font=("Microsoft YaHei", 9),
                                       fg=C["text_sub"], bg=C["card"], anchor="w")
        self.dev_status_lbl.pack(fill="x")

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

        # 功能状态
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

        # 健康检查
        _, hc = card(p, "🩺 健康检查")
        tk.Label(hc, text="汇总驱动 / 连接 / 运行时 / 备份 / 自启状态，生成诊断报告",
                 font=("Microsoft YaHei", 8),
                 fg=C["text_sub"], bg=C["card"]).pack(anchor="w", pady=(0, 6))
        btn(hc, "🩺 运行诊断", self._run_health_check, "teal", 12).pack(anchor="w")

    def _build_driver_tab(self):
        section(self.scroll_frame, "🔧 驱动管理", C["teal"])
        p = self.scroll_frame

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

        # 一键安装 PSVR2Toolkit
        _, c = card(p, "⬇️ 一键安装 PSVR2Toolkit")
        install_info = tk.Label(c,
                                 text="从 GitHub 下载最新版 Toolkit DLL 并自动安装到驱动目录",
                                 font=("Microsoft YaHei", 8),
                                 fg=C["text_sub"], bg=C["card"])
        install_info.pack(anchor="w", pady=(0, 6))
        install_btn_frame = tk.Frame(c, bg=C["card"])
        install_btn_frame.pack(fill="x")
        self.install_btn = btn(install_btn_frame, "⬇️ 下载安装",
                               self._install_toolkit, "green", 12)
        self.install_btn.pack(side="left", padx=(0, 6))
        self.install_status_lbl = tk.Label(install_btn_frame, text="",
                                             font=("Microsoft YaHei", 8),
                                             fg=C["text_sub"], bg=C["card"])
        self.install_status_lbl.pack(side="left", fill="x", expand=True)

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
        self.update_btn = btn(ver_frame, "🔍 检查", self._check_toolkit_update, "accent", 8)
        self.update_btn.pack(side="right")

        # 备份管理
        _, c = card(p, "💾 驱动备份")
        tk.Label(c, text=f"自动保留最近 {BACKUP_KEEP} 份，超出自动清理",
                 font=("Microsoft YaHei", 8),
                 fg=C["text_sub"], bg=C["card"]).pack(anchor="w", pady=(0, 4))
        self.backup_listbox = tk.Listbox(c, font=("Microsoft YaHei", 9),
                                          bg=C["card_hi"], fg=C["text"],
                                          selectbackground=C["accent"],
                                          selectforeground=C["text"],
                                          highlightthickness=0, bd=0,
                                          height=5)
        self.backup_listbox.pack(fill="x", pady=(0, 6))
        backup_btn_frame = tk.Frame(c, bg=C["card"])
        backup_btn_frame.pack(fill="x")
        btn(backup_btn_frame, "💾 创建备份", self._do_backup, "teal", 10).pack(
            side="left", padx=(0, 4))
        self.restore_btn = btn(backup_btn_frame, "♻ 恢复", self._do_restore, "accent", 8)
        self.restore_btn.pack(side="left", padx=(0, 4))
        btn(backup_btn_frame, "🗑 删除", self._delete_backup, "red", 8).pack(side="right")
        self._refresh_backup_list()

    def _build_settings_tab(self):
        section(self.scroll_frame, "⚙️ SteamVR 设置", C["orange"])
        p = self.scroll_frame
        self.sv_settings.load()

        _, c = card(p, "🎯 SteamVR 渲染设置")
        tk.Label(c, text="调整 SteamVR 渲染参数，重启 SteamVR 后生效",
                 font=("Microsoft YaHei", 8),
                 fg=C["text_sub"], bg=C["card"]).pack(anchor="w", pady=(0, 8))

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

        btn_frame = tk.Frame(c, bg=C["card"])
        btn_frame.pack(fill="x", pady=(12, 0))
        btn(btn_frame, "💾 应用设置", self._apply_sv_settings, "green", 11).pack(
            side="left", padx=(0, 6))
        btn(btn_frame, "↩ 恢复默认", self._reset_sv_settings, "gray", 10).pack(side="left")

        # 配置预设
        _, pf = card(p, "💾 配置预设")
        pfc = tk.Frame(pf, bg=C["card"])
        pfc.pack(fill="x")
        self.profile_combo = ttk.Combobox(pfc, values=self.sv_settings.list_profiles(),
                                           state="readonly", width=16,
                                           font=("Microsoft YaHei", 9))
        self.profile_combo.pack(side="left", padx=(0, 6))
        btn(pfc, "💾 保存", self._save_profile, "teal", 6).pack(side="left", padx=(0, 4))
        btn(pfc, "♻ 加载", self._load_profile, "accent", 6).pack(side="left", padx=(0, 4))
        btn(pfc, "🗑 删除", self._delete_profile, "red", 6).pack(side="left")

        # Toolkit 调节（键名查证自 BnuuySolutions/PSVR2Toolkit 源码 vr_settings.h）
        _, ctk = card(p, "🎛 Toolkit 调节")
        tk.Label(ctk, text="PSVR2Toolkit 参数，写入 vrsettings，重启 SteamVR 生效；亮度经驱动桥接硬件",
                 font=("Microsoft YaHei", 8),
                 fg=C["text_sub"], bg=C["card"]).pack(anchor="w", pady=(0, 8))

        tk.Label(ctk, text="屏幕亮度 (analogGain)",
                 font=("Microsoft YaHei", 9), fg=C["text"], bg=C["card"]).pack(anchor="w")
        bri_frame = tk.Frame(ctk, bg=C["card"])
        bri_frame.pack(fill="x", pady=(2, 0))
        self.tk_brightness = tk.DoubleVar(
            value=float(self.sv_settings.get_in_section("steamvr", "analogGain", 1.0)))
        ttk.Scale(bri_frame, from_=0.0, to_=1.0,
                  variable=self.tk_brightness, orient="horizontal",
                  command=lambda _: self._update_bri_lbl()).pack(side="left", fill="x", expand=True)
        self.bri_lbl = tk.Label(bri_frame, text="100%",
                                font=("Microsoft YaHei", 9, "bold"),
                                fg=C["accent"], bg=C["card"], width=6)
        self.bri_lbl.pack(side="right")
        self._update_bri_lbl()

        tk_switches = tk.Frame(ctk, bg=C["card"])
        tk_switches.pack(fill="x", pady=(10, 0))
        self.tk_chaperone = tk.BooleanVar(
            value=bool(self.sv_settings.get_in_section("playstation_vr2_ex", "disableChaperone", False)))
        self.tk_sense = tk.BooleanVar(
            value=bool(self.sv_settings.get_in_section("playstation_vr2_ex", "disableSense", False)))
        self.tk_gaze = tk.BooleanVar(
            value=bool(self.sv_settings.get_in_section("playstation_vr2_ex", "disableGaze", False)))
        self.tk_sync = tk.BooleanVar(
            value=bool(self.sv_settings.get_in_section("playstation_vr2_ex", "useToolkitSync", True)))
        self.tk_haptics = tk.BooleanVar(
            value=bool(self.sv_settings.get_in_section("playstation_vr2_ex", "useEnhancedHaptics", True)))
        ttk.Checkbutton(tk_switches, text="禁用安全区边界", variable=self.tk_chaperone,
                        style="TCheckbutton").grid(row=0, column=0, sticky="w", padx=(0, 12))
        ttk.Checkbutton(tk_switches, text="禁用 Sense 控制器", variable=self.tk_sense,
                        style="TCheckbutton").grid(row=0, column=1, sticky="w")
        ttk.Checkbutton(tk_switches, text="禁用眼动追踪", variable=self.tk_gaze,
                        style="TCheckbutton").grid(row=1, column=0, sticky="w", padx=(0, 12), pady=(4, 0))
        ttk.Checkbutton(tk_switches, text="Toolkit LED 同步", variable=self.tk_sync,
                        style="TCheckbutton").grid(row=1, column=1, sticky="w", pady=(4, 0))
        ttk.Checkbutton(tk_switches, text="增强触觉", variable=self.tk_haptics,
                        style="TCheckbutton").grid(row=2, column=0, sticky="w", padx=(0, 12), pady=(4, 0))

        btn_frame_tk = tk.Frame(ctk, bg=C["card"])
        btn_frame_tk.pack(fill="x", pady=(10, 0))
        btn(btn_frame_tk, "💾 应用 Toolkit 设置", self._apply_toolkit_settings, "green", 16).pack(anchor="w")

        if not self.sv_settings.path:
            tk.Label(c, text="⚠ SteamVR 设置文件未找到",
                     font=("Microsoft YaHei", 8), fg=C["yellow"],
                     bg=C["card"], anchor="w").pack(pady=(8, 0))

        # 开机启动
        _, c2 = card(p, "⚡ 系统选项")
        self.auto_start_var = tk.BooleanVar(value=auto_start_enabled())
        auto_start_frame = tk.Frame(c2, bg=C["card"])
        auto_start_frame.pack(fill="x", pady=(0, 8))
        tk.Label(auto_start_frame, text="开机自动启动",
                 font=("Microsoft YaHei", 9), fg=C["text"], bg=C["card"]).pack(side="left")
        auto_start_cb = ttk.Checkbutton(auto_start_frame,
                                         variable=self.auto_start_var,
                                         style="TCheckbutton",
                                         command=self._toggle_auto_start)
        auto_start_cb.pack(side="right")
        # 托盘最小化
        self.minimize_tray_var = tk.BooleanVar(value=True)
        tray_frame = tk.Frame(c2, bg=C["card"])
        tray_frame.pack(fill="x", pady=(0, 0))
        tk.Label(tray_frame, text="关闭按钮最小化到托盘",
                 font=("Microsoft YaHei", 9), fg=C["text"], bg=C["card"]).pack(side="left")
        ttk.Checkbutton(tray_frame, variable=self.minimize_tray_var,
                        style="TCheckbutton").pack(side="right")

        # 一键启动
        _, c3 = card(p, "🚀 快速启动")
        btn(c3, "🚀 启动 SteamVR + VRCFT", self._launch_all, "green").pack(fill="x", pady=2)
        startup_frame = tk.Frame(c3, bg=C["card"])
        startup_frame.pack(fill="x", pady=(4, 0))
        btn(startup_frame, "SteamVR", self._launch_steamvr, "accent", 9).pack(side="left", padx=(0, 4))
        btn(startup_frame, "VRCFT", self._launch_vrcft, "accent", 9).pack(side="left")
        btn(startup_frame, "VRCFT (Steam)", self._open_vrcft_steam, "gray", 12).pack(side="right")
        stop_frame = tk.Frame(c3, bg=C["card"])
        stop_frame.pack(fill="x", pady=(4, 0))
        btn(stop_frame, "⏹ 关闭 SteamVR", self._stop_steamvr, "red", 14).pack(anchor="w")

        # VRCFT 升级
        _, c4 = card(p, "⬆️ VRCFT 升级")
        ver_row = tk.Frame(c4, bg=C["card"])
        ver_row.pack(fill="x")
        tk.Label(ver_row, text="本地版本:", font=("Microsoft YaHei", 9),
                 fg=C["text_sub"], bg=C["card"]).pack(side="left")
        self.vrcft_local_lbl = tk.Label(ver_row, text="—",
                                        font=("Microsoft YaHei", 9, "bold"),
                                        fg=C["text"], bg=C["card"])
        self.vrcft_local_lbl.pack(side="left", padx=(6, 12))
        tk.Label(ver_row, text="最新版本:", font=("Microsoft YaHei", 9),
                 fg=C["text_sub"], bg=C["card"]).pack(side="left")
        self.vrcft_latest_lbl = tk.Label(ver_row, text="未检查",
                                         font=("Microsoft YaHei", 9, "bold"),
                                         fg=C["text"], bg=C["card"])
        self.vrcft_latest_lbl.pack(side="left", padx=(6, 0))
        btn(ver_row, "🔍 检查", self._check_vrcft_update, "accent", 8).pack(side="right")
        dl_row = tk.Frame(c4, bg=C["card"])
        dl_row.pack(fill="x", pady=(6, 0))
        self.vrcft_install_btn = btn(dl_row, "⬇️ 下载安装包", self._install_vrcft,
                                     "green", 14)
        self.vrcft_install_btn.pack(side="left", padx=(0, 6))
        self.vrcft_install_btn.config(state="disabled")
        self.vrcft_status_lbl = tk.Label(dl_row, text="先检查更新",
                                         font=("Microsoft YaHei", 8),
                                         fg=C["text_sub"], bg=C["card"])
        self.vrcft_status_lbl.pack(side="left", fill="x", expand=True)

        # VRCFT 眼动模块（PSVR2）
        _, c5 = card(p, "🧩 VRCFT 眼动模块 (PSVR2)")
        mod_row = tk.Frame(c5, bg=C["card"])
        mod_row.pack(fill="x")
        tk.Label(mod_row, text="模块状态:", font=("Microsoft YaHei", 9),
                 fg=C["text_sub"], bg=C["card"]).pack(side="left")
        self.vrcft_module_lbl = tk.Label(mod_row, text="检测中...",
                                         font=("Microsoft YaHei", 9, "bold"),
                                         fg=C["text"], bg=C["card"])
        self.vrcft_module_lbl.pack(side="left", padx=(6, 0))
        self.vrcft_module_btn = btn(mod_row, "📦 下载安装", self._install_vrcft_module,
                                    "green", 12)
        self.vrcft_module_btn.pack(side="right")
        tk.Label(c5, text="用于 VRChat 眼动追踪；VRCFT 内置模块注册表亦可一键安装，安装后重启 VRCFT 生效",
                 font=("Microsoft YaHei", 8),
                 fg=C["text_sub"], bg=C["card"]).pack(anchor="w", pady=(4, 0))

    def _build_log_section(self):
        section(self.scroll_frame, "📝 日志", C["gray_hi"])
        p = self.scroll_frame
        _, c = card(p, "")
        self.log_text = tk.Text(c, font=("Consolas", 8), bg=C["bg"], fg=C["text_sub"],
                                 height=6, wrap="word", relief=tk.FLAT, bd=0,
                                 insertbackground=C["text"])
        self.log_text.pack(fill="x")
        lbf = tk.Frame(c, bg=C["card"])
        lbf.pack(fill="x", pady=(4, 0))
        btn(lbf, "🔄 刷新", self._refresh_log, "gray", 8).pack(side="left", padx=(0, 4))
        btn(lbf, "📂 打开日志", self._open_log_file, "gray", 10).pack(side="left")
        self._refresh_log()

    # ── 检测与监控 ──────────────────────────────────────
    def _run_detection(self):
        def detect():
            self.detector.detect_all()
            module = self.detector.vrcft.get_module_status()
            self.root.after(0, self._update_ui)
            self.root.after(0, self._on_module_status, module)
        threading.Thread(target=detect, daemon=True).start()

    def _update_ui(self):
        d = self.detector

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

        self._update_runtime_ui()

        color_map = {"green": C["green"], "red": C["red"],
                     "yellow": C["yellow"], "gray": C["text_sub"]}
        for k, lbl in self.feat_labels.items():
            v = d.features.get(k, {})
            lbl.config(text=v.get("status", "—"),
                       fg=color_map.get(v.get("color", "gray"), C["text_sub"]))

        tk_info = d.toolkit
        if tk_info.driver_installed:
            self.drv_version_lbl.config(text=tk_info.driver_version,
                                         fg=C["green"] if tk_info.toolkit_active else C["yellow"])
            bg = C["accent"] if tk_info.toolkit_active else C["orange"]
            ah = C["accent_hi"] if tk_info.toolkit_active else C["orange_hi"]
            self.drv_switch_btn.config(
                text="⏪ 恢复官方" if tk_info.toolkit_active else "🔄 切换Toolkit",
                bg=bg, activebackground=ah)
            self.drv_switch_btn.bind("<Enter>", lambda e, _b=self.drv_switch_btn, _c=ah: _b.config(bg=_c))
            self.drv_switch_btn.bind("<Leave>", lambda e, _b=self.drv_switch_btn, _c=bg: _b.config(bg=_c))
            self.drv_dir_lbl.config(text=tk_info.driver_dir or "—")
        else:
            self.drv_version_lbl.config(text="❌ 未安装驱动", fg=C["red"])
            self.drv_switch_btn.config(text="切换驱动", state="disabled")
            self.drv_dir_lbl.config(text="未找到驱动目录")

    def _start_monitor(self):
        def loop():
            conn_ticks = 0
            while not self._stop_monitor.wait(3):
                self.detector.refresh_runtime()
                # 连接检测需启动 PowerShell（开销大），降频至约 20 秒一次
                conn_ticks += 1
                if conn_ticks >= 7:
                    conn_ticks = 0
                    if self.detector.refresh_connection():
                        self.root.after(0, self._on_connection_changed)
                    self.root.after(0, self._update_ui)
                self.root.after(0, self._update_runtime_ui)
        t = threading.Thread(target=loop, daemon=True)
        t.start()

    def _update_runtime_ui(self):
        sv = self.detector.steamvr
        self.steamvr_lbl.config(
            text="▶ 运行中" if sv.is_running else "⏹ 未运行",
            fg=C["green"] if sv.is_running else C["text_sub"])
        vrcft = self.detector.vrcft
        tag = "内置" if vrcft.bundled else ""
        if vrcft.is_running:
            self.vrcft_lbl.config(text=f"▶ 运行中{tag}", fg=C["green"])
        elif vrcft.installed:
            self.vrcft_lbl.config(text=f"已安装{tag}", fg=C["text"])
        else:
            self.vrcft_lbl.config(text="❌ 未安装", fg=C["red"])

    def _on_connection_changed(self):
        """PSVR2 连接/断开通知"""
        if self.detector.connected:
            try:
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            except Exception as e:
                log.warning(f"蜂鸣器失败: {e}")
            log.info("🔔 PS VR2 已连接")
        else:
            try:
                winsound.MessageBeep(winsound.MB_ICONHAND)
            except Exception as e:
                log.warning(f"蜂鸣器失败: {e}")
            log.info("🔔 PS VR2 已断开")
        self._update_ui()

    # ── 健康检查 ────────────────────────────────────────
    def _run_health_check(self):
        def diagnose():
            self.detector.detect_all()
            lines = []
            tk = self.detector.toolkit
            if tk.driver_installed:
                lines.append(("✅", f"驱动目录: {tk.driver_dir}"))
                lines.append(("✅" if tk.toolkit_active else "⚠️",
                              f"当前驱动: {tk.driver_version}"))
            else:
                lines.append(("❌", "驱动目录: 未找到（PlayStation VR2 App 未安装？）"))
            if self.detector.connected:
                name = self.detector.device_info.get("name", "PS VR2")
                lines.append(("✅", f"PS VR2 连接: 已连接（{name}）"))
            else:
                lines.append(("❌", "PS VR2 连接: 未检测到"))
            lines.append(("✅" if self.detector.steamvr.is_running else "⚠️",
                          "SteamVR: 运行中" if self.detector.steamvr.is_running
                          else "SteamVR: 未运行"))
            vrcft = self.detector.vrcft
            if vrcft.installed:
                lines.append(("✅", f"VRCFT: 已安装（{vrcft.path}）"))
                module = vrcft.get_module_status()
                lines.append(("✅" if module else "⚠️",
                              f"VRCFT 眼动模块: {module}" if module
                              else "VRCFT 眼动模块: 未安装"))
            else:
                lines.append(("❌", "VRCFT: 未安装"))
            n = len(tk.list_backups())
            lines.append(("✅" if n else "⚠️", f"驱动备份: {n} 份"))
            lines.append(("ℹ️", f"开机自启: {'开启' if auto_start_enabled() else '关闭'}"))
            if self.sv_settings.load():
                lines.append(("✅", f"SteamVR 设置: {self.sv_settings.path}"))
            else:
                lines.append(("❌", "SteamVR 设置: 文件未找到"))
            ok_tk, latest_tk, _ = tk.check_update()
            if ok_tk:
                lines.append(("ℹ️", f"Toolkit 最新版本: {latest_tk}"))
            self.root.after(0, self._show_health_report, lines)
        threading.Thread(target=diagnose, daemon=True).start()

    def _show_health_report(self, lines):
        sep = "=" * 32
        report = "\n".join(f"{icon} {text}" for icon, text in lines)
        report = f"🩺 健康检查报告\n{sep}\n{report}\n{sep}"
        self.root.clipboard_clear()
        self.root.clipboard_append(report)
        log.info("健康检查完成:\n" + report)
        messagebox.showinfo("健康检查", report +
                            f"\n\n生成时间: {datetime.now():%Y-%m-%d %H:%M:%S}"
                            "\n\n📋 报告已复制到剪贴板")

    # ── 驱动操作 ────────────────────────────────────────
    def _switch_driver(self):
        tk_info = self.detector.toolkit
        to_toolkit = not tk_info.toolkit_active
        action = "切换到 PSVR2Toolkit" if to_toolkit else "切换回官方驱动"
        if self.detector.steamvr.is_running:
            if not messagebox.askyesno("SteamVR 运行中",
                    "SteamVR 正在运行，驱动文件可能被占用导致切换失败。\n\n"
                    "建议先点击「⏹ 关闭 SteamVR」。\n\n仍要继续切换吗？"):
                return
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

    def _install_toolkit(self):
        """下载并安装 PSVR2Toolkit"""
        if not self.detector.toolkit.driver_dir:
            messagebox.showwarning("未找到", "未检测到驱动目录，无法安装")
            return
        self.install_btn.config(state="disabled", text="下载中...")
        self.install_status_lbl.config(text="正在从 GitHub 下载...", fg=C["text_sub"])

        def do_install():
            ok, ver, url = self.detector.toolkit.check_update()
            if not ok or not url:
                self.root.after(0, self._on_install_result, False, f"检查更新失败: {ver}")
                return
            progress_cb = lambda d, t: self.root.after(
                0, self._on_download_progress, d, t)
            success, msg = self.detector.toolkit.download_toolkit(url, progress_cb)
            self.root.after(0, self._on_install_result, success, msg)

        threading.Thread(target=do_install, daemon=True).start()

    def _on_download_progress(self, downloaded: int, total: int):
        pct = int(downloaded * 100 / total) if total else 0
        self.install_status_lbl.config(text=f"下载中... {pct}%", fg=C["accent"])

    def _on_install_result(self, success: bool, msg: str):
        self.install_btn.config(state="normal", text="⬇️ 下载安装")
        if success:
            self.install_status_lbl.config(text="✅ 下载完成", fg=C["green"])
            messagebox.showinfo("安装成功", f"{msg}\n\n请使用「切换驱动」切换到 Toolkit")
            self._run_detection()
        else:
            self.install_status_lbl.config(text="❌ 失败", fg=C["red"])
            messagebox.showerror("安装失败", msg)

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
        # 健壮提取时间戳：第2个空格之前的内容（即 📦 和第一个空格之间的 timestamp）
        # label = "📦 YYYYMMDD_HHMMSS  [active]  N个文件"
        # split on "  " (两个空格) to separate emoji+ts from rest
        parts = label.split("  ", 1)
        ts = parts[0].replace("📦 ", "").strip()
        confirm = messagebox.askyesno("确认",
            f"从备份 [{ts}] 恢复？\n需要重启 SteamVR 生效")
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
        parts = label.split("  ", 1)
        ts = parts[0].replace("📦 ", "").strip()
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

    # ── Toolkit 调节 ────────────────────────────────────
    def _update_bri_lbl(self):
        self.bri_lbl.config(text=f"{int(self.tk_brightness.get() * 100)}%")

    def _apply_toolkit_settings(self):
        self.sv_settings.load()
        self.sv_settings.set_in_section("steamvr", "analogGain",
                                        self.tk_brightness.get())
        self.sv_settings.set_in_section("playstation_vr2_ex", "disableChaperone",
                                        self.tk_chaperone.get())
        self.sv_settings.set_in_section("playstation_vr2_ex", "disableSense",
                                        self.tk_sense.get())
        self.sv_settings.set_in_section("playstation_vr2_ex", "disableGaze",
                                        self.tk_gaze.get())
        self.sv_settings.set_in_section("playstation_vr2_ex", "useToolkitSync",
                                        self.tk_sync.get())
        self.sv_settings.set_in_section("playstation_vr2_ex", "useEnhancedHaptics",
                                        self.tk_haptics.get())
        success, msg = self.sv_settings.save()
        if success:
            messagebox.showinfo("Toolkit 设置", "已保存（重启 SteamVR 生效）")
        else:
            messagebox.showerror("Toolkit 设置", msg)

    # ── 系统选项 ────────────────────────────────────────
    def _save_profile(self):
        name = self.profile_combo.get()
        if not name:
            name = simpledialog.askstring("预设名称", "请输入预设名称:", parent=self.root)
        if name:
            success, msg = self.sv_settings.save_profile(name)
            if success:
                self.profile_combo.config(values=self.sv_settings.list_profiles())
                messagebox.showinfo("预设", msg)
            else:
                messagebox.showerror("失败", msg)

    def _load_profile(self):
        name = self.profile_combo.get()
        if not name:
            messagebox.showwarning("提示", "请先选择一个预设")
            return
        success, msg = self.sv_settings.load_profile(name)
        if success:
            self.sv_settings.load()
            self.sample_scale.set(float(self.sv_settings.get("renderTargetMultiplier", 1.0)))
            self.cb_filter.set(bool(self.sv_settings.get("allowSupersampleFiltering", True)))
            self.cb_smooth.set(bool(self.sv_settings.get("motionSmoothing", True)))
            self._update_scale_lbl()
            messagebox.showinfo("预设", msg)
        else:
            messagebox.showerror("失败", msg)

    def _delete_profile(self):
        name = self.profile_combo.get()
        if not name:
            messagebox.showwarning("提示", "请先选择一个预设")
            return
        if messagebox.askyesno("确认", f"删除预设「{name}」？"):
            success, msg = self.sv_settings.delete_profile(name)
            self.profile_combo.config(values=self.sv_settings.list_profiles())
            self.profile_combo.set("")
            messagebox.showinfo("预设", msg)

    def _toggle_auto_start(self):
        enabled = self.auto_start_var.get()
        success = set_auto_start(enabled)
        if success:
            msg = "开机自动启动已开启" if enabled else "开机自动启动已关闭"
            log.info(msg)
        else:
            self.auto_start_var.set(not enabled)
            messagebox.showerror("失败", "无法修改开机启动设置")

    def _refresh_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        log_file = LOG_DIR / "psvr2_panel.log"
        if log_file.exists():
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                for line in lines[-30:]:
                    self.log_text.insert("end", line)
            except Exception:
                self.log_text.insert("end", "读取日志失败")
        else:
            self.log_text.insert("end", "暂无日志")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _open_log_file(self):
        log_file = LOG_DIR / "psvr2_panel.log"
        if log_file.exists():
            os.startfile(str(log_file))
        else:
            messagebox.showinfo("提示", "日志文件不存在")

    # ── 启动操作 ────────────────────────────────────────
    def _launch_steamvr(self):
        threading.Thread(target=self._do_launch_steamvr, daemon=True).start()

    def _do_launch_steamvr(self):
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
            self.root.after(0, lambda: messagebox.showwarning("未找到", "SteamVR 未安装"))

    def _launch_vrcft(self):
        threading.Thread(target=self._do_launch_vrcft, daemon=True).start()

    def _do_launch_vrcft(self):
        if self.detector.vrcft.launch():
            time.sleep(1)
            self._run_detection()
        else:
            self.root.after(0, lambda: messagebox.showwarning("未安装",
                "VRCFaceTracking 未安装\n可点击「VRCFT (Steam)」安装"))

    def _launch_all(self):
        threading.Thread(target=self._do_launch_all, daemon=True).start()

    def _do_launch_all(self):
        self._do_launch_steamvr()
        time.sleep(2)
        self._do_launch_vrcft()

    def _open_vrcft_steam(self):
        try:
            os.startfile(VRCFT_STEAM_URL)
        except Exception:
            os.startfile("https://store.steampowered.com/app/658580/VRCFaceTracking/")

    def _stop_steamvr(self):
        def do_stop():
            r = _run(["taskkill", "/F", "/IM", "vrserver.exe"], timeout=10)
            closed = r.returncode == 0
            if closed:
                log.info("SteamVR 已关闭")
                time.sleep(1)
            self.root.after(0, self._on_steamvr_stopped, closed)
        threading.Thread(target=do_stop, daemon=True).start()

    def _on_steamvr_stopped(self, closed: bool):
        self._run_detection()
        if closed:
            messagebox.showinfo("提示", "SteamVR 已关闭\n\n现在可以安全切换驱动")
        else:
            messagebox.showwarning("提示", "SteamVR 未在运行或关闭失败")

    # ── VRCFT 升级 ──────────────────────────────────────
    def _check_vrcft_update(self):
        def do_check():
            vrcft = self.detector.vrcft
            local = vrcft.get_local_version()
            ok, latest, url = vrcft.check_update()
            self.root.after(0, self._on_vrcft_check, local, ok, latest, url)
        threading.Thread(target=do_check, daemon=True).start()

    def _on_vrcft_check(self, local: Optional[str], ok: bool,
                        latest: str, url: Optional[str]):
        self.vrcft_local_lbl.config(text=local or "未知")
        if ok:
            self.vrcft_latest_lbl.config(text=latest, fg=C["green"])
            self._vrcft_dl_url = url
            if url:
                self.vrcft_install_btn.config(state="normal")
                self.vrcft_status_lbl.config(text="可下载", fg=C["text_sub"])
            else:
                self.vrcft_status_lbl.config(text="Release 未提供 exe 安装包",
                                             fg=C["yellow"])
        else:
            self.vrcft_latest_lbl.config(text="检查失败", fg=C["red"])
            self.vrcft_status_lbl.config(text="网络错误，稍后重试", fg=C["red"])

    def _install_vrcft(self):
        url = getattr(self, "_vrcft_dl_url", None)
        if not url:
            return
        self.vrcft_install_btn.config(state="disabled")
        self.vrcft_status_lbl.config(text="正在下载...", fg=C["text_sub"])

        def do_install():
            progress_cb = lambda d, t: self.root.after(0, self._on_vrcft_progress, d, t)
            ok, result = self.detector.vrcft.download_installer(url, progress_cb)
            self.root.after(0, self._on_vrcft_install_done, ok, result)
        threading.Thread(target=do_install, daemon=True).start()

    def _on_vrcft_progress(self, downloaded: int, total: int):
        pct = int(downloaded * 100 / total) if total else 0
        self.vrcft_status_lbl.config(text=f"下载中... {pct}%", fg=C["accent"])

    def _on_vrcft_install_done(self, ok: bool, result: str):
        self.vrcft_install_btn.config(state="normal")
        if ok:
            self.vrcft_status_lbl.config(text="✅ 下载完成，启动安装程序", fg=C["green"])
            _popen([result])
            log.info(f"VRCFT 安装程序已启动: {result}")
        else:
            self.vrcft_status_lbl.config(text=f"❌ {result}", fg=C["red"])
            messagebox.showerror("VRCFT 升级", result)

    # ── VRCFT 眼动模块 ──────────────────────────────────
    def _on_module_status(self, name: Optional[str]):
        if name:
            self.vrcft_module_lbl.config(text=f"已安装 {name}", fg=C["green"])
            self.vrcft_module_btn.config(text="🔄 更新模块")
        else:
            self.vrcft_module_lbl.config(text="未安装", fg=C["text_sub"])
            self.vrcft_module_btn.config(text="📦 下载安装")

    def _install_vrcft_module(self):
        self.vrcft_module_btn.config(state="disabled")
        self.vrcft_module_lbl.config(text="正在获取...", fg=C["text_sub"])

        def do_install():
            ok, ver, url = self.detector.vrcft.check_module_update()
            if not ok or not url:
                self.root.after(0, self._on_module_install_done, False,
                                f"检查失败: {ver}")
                return
            success, msg = self.detector.vrcft.install_module(url)
            self.root.after(0, self._on_module_install_done, success, msg)
        threading.Thread(target=do_install, daemon=True).start()

    def _on_module_install_done(self, success: bool, msg: str):
        self.vrcft_module_btn.config(state="normal")
        if success:
            messagebox.showinfo("模块安装", f"{msg}\n\n请重启 VRCFaceTracking 生效")
        else:
            messagebox.showerror("模块安装", msg)
        self._refresh_module_status()

    def _refresh_module_status(self):
        def do_check():
            name = self.detector.vrcft.get_module_status()
            self.root.after(0, self._on_module_status, name)
        threading.Thread(target=do_check, daemon=True).start()

    # ── 窗口关闭/托盘 ────────────────────────────────────
    def _on_close_request(self):
        if self.minimize_tray_var.get():
            self._minimize_to_tray()
        else:
            self.destroy()

    def _minimize_to_tray(self):
        try:
            import pystray
            from PIL import Image, ImageDraw
        except ImportError:
            # pystray 未安装，降级为直接退出
            messagebox.showinfo("提示",
                "系统托盘功能需要安装 pystray 和 Pillow\npip install pystray Pillow")
            self.destroy()
            return

        # 创建托盘图标
        img = Image.new("RGB", (64, 64), color=C["bg"])
        draw = ImageDraw.Draw(img)
        draw.rectangle((8, 8, 56, 56), fill=C["accent"])
        draw.text((20, 22), "PS", fill="white")

        menu = pystray.Menu(
            pystray.MenuItem("显示窗口", self._restore_from_tray, default=True),
            pystray.MenuItem("刷新状态", lambda _: self._run_detection()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("切换驱动", lambda _: self.root.after(0, self._switch_driver)),
            pystray.MenuItem("关闭 SteamVR", lambda _: self._stop_steamvr()),
            pystray.MenuItem("健康检查", lambda _: self._run_health_check()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", lambda _: self.destroy()),
        )

        self._tray_icon = pystray.Icon(APP_NAME, img, APP_NAME, menu)
        self.root.withdraw()
        self._tray_icon.run_detached()
        log.info("已最小化到系统托盘")

    def _restore_from_tray(self, icon=None, item=None):
        if hasattr(self, "_tray_icon"):
            self._tray_icon.stop()
        self.root.after(0, lambda: self.root.deiconify())

    def destroy(self):
        self._stop_monitor.set()
        if hasattr(self, "_tray_icon"):
            try:
                self._tray_icon.stop()
            except Exception as e:
                log.warning(f"托盘图标停止失败: {e}")
        self.root.destroy()

    # ── 关于 ────────────────────────────────────────────
    def _show_about(self):
        messagebox.showinfo(
            f"关于 {APP_NAME}",
            f"{APP_NAME} v{APP_VERSION}\n\n"
            f"PlayStation VR2 PC 控制面板\n"
            f"深度集成 PSVR2Toolkit 工具链\n\n"
            f"v4.7.0 更新：\n"
            f"  🎛 Toolkit 调节面板（亮度 + 5 项开关）\n\n"
            f"v4.6.0 更新：眼动模块部署 / Steam 路径检测 / 托盘增强\n"
            f"v4.5.0 更新：关闭 SteamVR / 操作容错 / 备份清理\n"
            f"v4.3.0 更新：PROFILE_DIR Bug 修复 / 规范整理\n"
            f"v4.2.0 更新：PlayStation 深色主题 / 驱动切换\n"
            f"v4.1.0 更新：系统托盘 / 开机启动 / 滚动界面\n\n"
            f"作者: {APP_AUTHOR}\n"
            f"{GITHUB_URL}"
        )

    def _check_toolkit_update(self):
        """检查 PSVR2Toolkit 最新版本"""
        self.update_btn.config(state="disabled")
        self.update_lbl.config(text="检查中...", fg=C["text_sub"])

        def do_check():
            ok, ver, url = self.detector.toolkit.check_update()
            self.root.after(0, self._on_toolkit_check, ok, ver, url)
        threading.Thread(target=do_check, daemon=True).start()

    def _on_toolkit_check(self, ok: bool, ver: str, url: Optional[str]):
        self.update_btn.config(state="normal")
        if ok:
            self.update_lbl.config(text=ver, fg=C["green"])
            if url:
                messagebox.showinfo("版本检查",
                    f"PSVR2Toolkit 最新版本: {ver}\n\n"
                    "可点击「⬇️ 下载安装」进行更新")
            else:
                messagebox.showinfo("版本检查",
                    f"PSVR2Toolkit 最新版本: {ver}\n\n"
                    "Release 未提供 DLL 下载")
        else:
            self.update_lbl.config(text="检查失败", fg=C["red"])
            messagebox.showwarning("版本检查", f"检查失败: {ver}")

    def _check_app_update(self):
        """后台检查更新"""
        def _on_update(new_ver, updater):
            changelog = updater.get_changelog()
            msg = f"发现新版本 v{new_ver}！\n当前版本: v{APP_VERSION}\n\n"
            if changelog:
                msg += f"更新内容:\n{changelog[:300]}\n\n"
            msg += "是否立即下载更新？"
            result = messagebox.askyesno("📦 发现新版本", msg, parent=self.root)
            if result:
                if updater.download_and_update(new_ver):
                    messagebox.showinfo("更新", "下载完成！点击确定重启应用。", parent=self.root)
                    updater.apply_update()
        
        check_update_background(
            app_name=APP_NAME,
            current_version=APP_VERSION,
            gitee_owner="cpufreestyle",
            gitee_repo="psvr2-panel",
            exe_pattern="PSVR2-Panel-v{version}.exe",
            callback=_on_update
        )

    def run(self):
        self.root.after(2000, self._check_app_update)
        self.root.mainloop()


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