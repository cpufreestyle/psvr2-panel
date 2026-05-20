# -*- coding: utf-8 -*-
"""
通用自动更新模块 - Gitee Release 自动检查与下载
适用于所有 PyInstaller 打包的 Windows GUI 应用

使用方法:
    from auto_updater import AutoUpdater

    updater = AutoUpdater(
        app_name="MyApp",
        current_version="1.0.0",
        gitee_owner="yourname",
        gitee_repo="myapp",
        exe_pattern="MyApp-v{version}.exe"  # Release 中的 exe 文件名模式
    )

    # 检查更新（返回 None 或新版本号）
    new_ver = updater.check_update()

    # 如果有更新，下载并安装
    if new_ver:
        if updater.download_and_update(new_ver):
            # 需要重启应用
            import os, sys
            os.execv(sys.executable, sys.argv)
"""

import os
import sys
import json
import shutil
import threading
import tempfile
import zipfile
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime


class AutoUpdater:
    """基于 Gitee Release 的自动更新器"""

    def __init__(self, app_name, current_version, gitee_owner, gitee_repo,
                 exe_pattern=None, check_on_start=True, silent=True):
        """
        参数:
            app_name: 应用名称（用于日志和标题）
            current_version: 当前版本号 (如 "1.0.0")
            gitee_owner: Gitee 用户名
            gitee_repo: Gitee 仓库名
            exe_pattern: Release 中 exe 的文件名模式，{version} 会被替换为版本号
                         如果为 None，自动从 Release assets 中查找 .exe 文件
            check_on_start: 是否在构造时自动检查更新
            silent: 静默模式（不弹窗提示，仅返回结果）
        """
        self.app_name = app_name
        self.current_version = self._parse_version(current_version)
        self.current_version_str = current_version
        self.gitee_owner = gitee_owner
        self.gitee_repo = gitee_repo
        self.exe_pattern = exe_pattern
        self.silent = silent

        # 本地更新状态文件
        self.state_file = os.path.join(
            os.environ.get('APPDATA', os.path.expanduser('~')),
            app_name, 'update_state.json'
        )

        self._latest_release = None
        self._latest_version = None
        self._download_dir = None

        if check_on_start:
            self.check_update()

    @staticmethod
    def _parse_version(v):
        """解析版本号为元组，方便比较"""
        return tuple(int(x) for x in v.replace('v', '').split('.')[:3])

    @property
    def api_url(self):
        return f"https://gitee.com/api/v5/repos/{self.gitee_owner}/{self.gitee_repo}/releases/latest"

    def check_update(self, force=False):
        """
        检查是否有新版本
        返回: 新版本号字符串，无更新返回 None
        """
        try:
            # 节流：24 小时内不重复检查（除非 force）
            if not force:
                last_check = self._get_state('last_check')
                if last_check:
                    last_dt = datetime.fromisoformat(last_check)
                    if (datetime.now() - last_dt).total_seconds() < 86400:
                        cached = self._get_state('latest_version')
                        if cached and self._parse_version(cached) > self.current_version:
                            return cached
                        return None

            req = urllib.request.Request(
                self.api_url,
                headers={'User-Agent': f'{self.app_name}-AutoUpdater/1.0'}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                self._latest_release = json.loads(resp.read().decode('utf-8'))

            tag = self._latest_release.get('tag_name', '').replace('v', '')
            if not tag:
                return None

            self._latest_version = tag
            self._set_state('last_check', datetime.now().isoformat())
            self._set_state('latest_version', tag)

            if self._parse_version(tag) > self.current_version:
                return tag
            return None

        except Exception as e:
            print(f"[AutoUpdater] 检查更新失败: {e}")
            return None

    def get_changelog(self):
        """获取最新版本的更新日志"""
        if self._latest_release:
            return self._latest_release.get('body', '')
        return ''

    def get_download_url(self, version=None):
        """
        获取下载链接
        返回: (asset_name, download_url) 或 (None, None)
        """
        if not self._latest_release:
            self.check_update(force=True)
        if not self._latest_release:
            return None, None

        assets = self._latest_release.get('assets', [])
        ver = version or self._latest_version or self.current_version_str

        # 如果指定了 exe_pattern，直接匹配
        if self.exe_pattern:
            target = self.exe_pattern.replace('{version}', ver)
            target = target.replace('{Version}', ver.capitalize() if ver[0].islower() else ver)
            for a in assets:
                if a.get('name', '') == target:
                    return a['name'], a['browser_download_url']

        # 否则找第一个 .exe 文件
        for a in assets:
            name = a.get('name', '')
            if name.lower().endswith('.exe'):
                return a['name'], a['browser_download_url']

        # 最后找任何文件
        for a in assets:
            return a['name'], a['browser_download_url']

        return None, None

    def download_and_update(self, version=None, progress_callback=None):
        """
        下载新版本并准备更新
        返回: True 表示下载成功，准备就绪

        参数:
            version: 目标版本（默认为最新版）
            progress_callback: 进度回调 callback(downloaded_bytes, total_bytes)
        """
        asset_name, download_url = self.get_download_url(version)
        if not download_url:
            print(f"[AutoUpdater] 未找到下载链接")
            return False

        ver = version or self._latest_version or 'unknown'
        self._download_dir = os.path.join(tempfile.gettempdir(), f"{self.app_name}_update_{ver}")
        os.makedirs(self._download_dir, exist_ok=True)

        target_path = os.path.join(self._download_dir, asset_name)
        print(f"[AutoUpdater] 正在下载 {asset_name}...")

        try:
            req = urllib.request.Request(
                download_url,
                headers={'User-Agent': f'{self.app_name}-AutoUpdater/1.0'}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get('Content-Length', 0))
                downloaded = 0
                chunk_size = 8192

                with open(target_path, 'wb') as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total)

            print(f"[AutoUpdater] 下载完成: {target_path}")
            return True

        except Exception as e:
            print(f"[AutoUpdater] 下载失败: {e}")
            return False

    def apply_update(self, callback=None):
        """
        执行更新（替换当前 exe）
        注意：必须在新进程中执行，因为当前 exe 正在运行

        参数:
            callback: 更新完成后的回调函数路径（字符串）
        """
        if not self._download_dir or not os.path.isdir(self._download_dir):
            print("[AutoUpdater] 没有已下载的更新包")
            return False

        # 找到下载的 exe
        exe_files = list(Path(self._download_dir).glob('*.exe'))
        if not exe_files:
            print("[AutoUpdater] 更新包中未找到 exe 文件")
            return False

        new_exe = str(exe_files[0])
        current_exe = sys.executable if getattr(sys, 'frozen', False) else None
        if not current_exe:
            # 开发模式，使用当前脚本
            current_exe = os.path.abspath(sys.argv[0])

        # 生成更新脚本
        update_script = f'''@echo off
echo 正在更新 {self.app_name}...
timeout /t 2 /nobreak >nul

:wait_loop
tasklist /fi "imagename eq {os.path.basename(current_exe)}" 2>nul | find /i "{os.path.basename(current_exe)}" >nul
if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait_loop
)

copy /y "{new_exe}" "{current_exe}" >nul 2>&1
echo 更新完成！
{"start \"\" \"" + current_exe + "\"" if not self.silent else ""}
rmdir /s /q "{self._download_dir}" >nul 2>&1
'''

        script_path = os.path.join(self._download_dir, 'apply_update.bat')
        with open(script_path, 'w', encoding='gbk') as f:
            f.write(update_script)

        # 启动更新脚本并退出当前程序
        subprocess.Popen(
            f'cmd /c "{script_path}"',
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
            close_fds=True
        )

        if callback:
            try:
                callback()
            except:
                pass

        return True

    def _get_state(self, key):
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    return json.load(f).get(key)
        except:
            pass
        return None

    def _set_state(self, key, value):
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            state = {}
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
            state[key] = value
            with open(self.state_file, 'w') as f:
                json.dump(state, f)
        except:
            pass


def check_update_background(app_name, current_version, gitee_owner, gitee_repo,
                            exe_pattern=None, callback=None):
    """
    后台线程检查更新（非阻塞）
    callback(new_version, updater) - 有更新时回调
    """
    def _check():
        try:
            updater = AutoUpdater(
                app_name=app_name,
                current_version=current_version,
                gitee_owner=gitee_owner,
                gitee_repo=gitee_repo,
                exe_pattern=exe_pattern,
                check_on_start=False,
                silent=True
            )
            new_ver = updater.check_update(force=True)
            if new_ver and callback:
                callback(new_ver, updater)
        except Exception as e:
            print(f"[AutoUpdater] 后台检查失败: {e}")

    t = threading.Thread(target=_check, daemon=True)
    t.start()
    return t
