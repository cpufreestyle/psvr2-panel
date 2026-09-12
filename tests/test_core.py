# -*- coding: utf-8 -*-
"""PSVR2Panel 核心逻辑单元测试（无头运行，不依赖显示器）

覆盖 review 指出的两个纯逻辑单元：
- PSVR2Toolkit.auto_backup_if_stale（过期判断数学 + 容错）
- PSVR2Shortcuts（add/remove/持久化/launch 分发/损坏文件恢复）
"""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import main
    MAIN_IMPORTABLE = True
except Exception as e:  # tkinter 缺失等环境问题
    MAIN_IMPORTABLE = False
    _import_error = e


@unittest.skipUnless(MAIN_IMPORTABLE, f"main 不可导入: {_import_error if not MAIN_IMPORTABLE else ''}")
class AutoBackupStaleTest(unittest.TestCase):
    """auto_backup_if_stale：过期判断 + 容错"""

    def setUp(self):
        self.tk = main.PSVR2Toolkit()
        self.tk.driver_installed = True

    def test_no_backups_triggers_backup(self):
        with mock.patch.object(self.tk, "list_backups", return_value=[]), \
             mock.patch.object(self.tk, "backup", return_value=(True, "ok")) as bk:
            self.assertTrue(self.tk.auto_backup_if_stale(interval_days=7))
            bk.assert_called_once()

    def test_recent_backup_skips(self):
        recent = datetime.now().strftime("%Y%m%d_%H%M%S")
        with mock.patch.object(self.tk, "list_backups",
                               return_value=[{"timestamp": recent}]), \
             mock.patch.object(self.tk, "backup") as bk:
            self.assertFalse(self.tk.auto_backup_if_stale(interval_days=7))
            bk.assert_not_called()

    def test_old_backup_triggers(self):
        old = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d_%H%M%S")
        with mock.patch.object(self.tk, "list_backups",
                               return_value=[{"timestamp": old}]), \
             mock.patch.object(self.tk, "backup", return_value=(True, "ok")) as bk:
            self.assertTrue(self.tk.auto_backup_if_stale(interval_days=7))
            bk.assert_called_once()

    def test_garbage_timestamp_falls_through_to_backup(self):
        with mock.patch.object(self.tk, "list_backups",
                               return_value=[{"timestamp": "garbage"}]), \
             mock.patch.object(self.tk, "backup", return_value=(True, "ok")) as bk:
            self.assertTrue(self.tk.auto_backup_if_stale(interval_days=7))
            bk.assert_called_once()

    def test_disabled_when_not_installed(self):
        self.tk.driver_installed = False
        with mock.patch.object(self.tk, "backup") as bk:
            self.assertFalse(self.tk.auto_backup_if_stale(interval_days=7))
            bk.assert_not_called()

    def test_disabled_when_interval_zero(self):
        with mock.patch.object(self.tk, "backup") as bk:
            self.assertFalse(self.tk.auto_backup_if_stale(interval_days=0))
            bk.assert_not_called()


@unittest.skipUnless(MAIN_IMPORTABLE, f"main 不可导入: {_import_error if not MAIN_IMPORTABLE else ''}")
class ShortcutsTest(unittest.TestCase):
    """PSVR2Shortcuts：add/remove/持久化/launch 分发/损坏恢复"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.file = Path(self.tmp.name) / "shortcuts.json"
        self.patcher = mock.patch.object(main, "SHORTCUTS_FILE", self.file)
        self.patcher.start()
        self.sc = main.PSVR2Shortcuts()

    def tearDown(self):
        self.patcher.stop()
        self.tmp.cleanup()

    def test_add_and_persist_roundtrip(self):
        ok, _ = self.sc.add("Demo", r"D:\Games\PSVR2RhythmDemo.exe")
        self.assertTrue(ok)
        again = main.PSVR2Shortcuts()  # 新实例从磁盘加载
        self.assertEqual(len(again.items), 1)
        self.assertEqual(again.items[0]["name"], "Demo")

    def test_duplicate_target_rejected(self):
        self.sc.add("Demo", r"D:\Games\game.exe")
        ok, msg = self.sc.add("Other", r"D:\GAMES\game.EXE")  # 大小写不敏感
        self.assertFalse(ok)
        self.assertIn("目标", msg)

    def test_duplicate_name_rejected(self):
        self.sc.add("Demo", r"D:\a.exe")
        ok, msg = self.sc.add("Demo", r"D:\b.exe")
        self.assertFalse(ok)
        self.assertIn("同名", msg)

    def test_remove_by_name(self):
        self.sc.add("Demo", r"D:\a.exe")
        self.assertTrue(self.sc.remove("Demo"))
        self.assertEqual(self.sc.items, [])

    def test_remove_missing_returns_false(self):
        self.assertFalse(self.sc.remove("nope"))

    def test_add_rollback_when_save_fails(self):
        # 把 SHORTCUTS_FILE 指到不可写路径，模拟磁盘写入失败
        bad = mock.patch.object(main, "SHORTCUTS_FILE",
                                Path(self.tmp.name) / "no_dir" / "s.json")
        # 制造写入失败：把文件路径指到一个目录
        bad_dir = Path(self.tmp.name) / "as_dir.json"
        bad_dir.mkdir()
        with mock.patch.object(main, "SHORTCUTS_FILE", bad_dir), \
             mock.patch.object(main, "SHORTCUTS_FILE", bad_dir):
            ok, msg = self.sc.add("X", r"D:\x.exe")
        self.assertFalse(ok)
        self.assertIn("保存失败", msg)
        self.assertEqual(self.sc.items, [])  # 内存态已回滚

    def test_launch_exe_via_popen(self):
        self.sc.add("Demo", r"D:\Games\game.exe")
        with mock.patch.object(main, "os") as mos, \
             mock.patch.object(main, "_popen") as mp:
            mos.path.exists.return_value = True
            self.assertTrue(self.sc.launch(0))
            mp.assert_called_once_with([r"D:\Games\game.exe"])

    def test_launch_steam_url_via_startfile(self):
        self.sc.add("SteamVR", "steam://rungameid/250820")
        with mock.patch.object(main.os, "startfile") as ms:
            self.assertTrue(self.sc.launch(0))
            ms.assert_called_once_with("steam://rungameid/250820")

    def test_launch_missing_exe_returns_false(self):
        self.sc.add("Ghost", r"D:\not\exist.exe")
        with mock.patch.object(main, "os") as mos:
            mos.path.exists.return_value = False
            self.assertFalse(self.sc.launch(0))

    def test_launch_bad_index_returns_false(self):
        self.assertFalse(self.sc.launch(99))

    def test_corrupt_json_backed_up_and_reset(self):
        self.file.write_text("{corrupt!!", encoding="utf-8")
        sc = main.PSVR2Shortcuts()
        self.assertEqual(sc.items, [])
        self.assertFalse(self.file.exists())          # 原文件已改名
        self.assertTrue(self.file.with_suffix(".json.bak").exists())


if __name__ == "__main__":
    unittest.main()
