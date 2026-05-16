# SPDX-License-Identifier: LGPL-2.1-or-later
import os
import threading
import tempfile
import urllib.request
import subprocess
import FreeCAD
import FreeCADGui

try:
    from PySide2 import QtCore, QtWidgets, QtGui
    _QWidget      = QtWidgets.QWidget
    _QHBoxLayout  = QtWidgets.QHBoxLayout
    _QLabel       = QtWidgets.QLabel
    _QPushButton  = QtWidgets.QPushButton
    _QProgressBar = QtWidgets.QProgressBar
    _QMsgBox      = QtWidgets.QMessageBox
except ImportError:
    from PySide import QtCore, QtGui
    QtWidgets     = QtGui
    _QWidget      = QtGui.QWidget
    _QHBoxLayout  = QtGui.QHBoxLayout
    _QLabel       = QtGui.QLabel
    _QPushButton  = QtGui.QPushButton
    _QProgressBar = QtGui.QProgressBar
    _QMsgBox      = QtGui.QMessageBox

_active_banner = None


class _UpdateBanner(_QWidget):
    """Blue banner at the top of the FreeCAD window with Download + progress."""

    def __init__(self, message, download_url, parent):
        super().__init__(parent)
        self._download_url = download_url
        self._alive = True          # set False in _dismiss so polls stop safely

        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: #0F62FE;")
        self.setFixedHeight(44)

        layout = _QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)

        self._lbl = _QLabel(
            f"<span style='color:white;font-size:13px;font-weight:bold;'>"
            f"  {message or 'A new version of BNC CAD is available.'}</span>"
        )
        self._lbl.setWordWrap(False)
        layout.addWidget(self._lbl, 1)

        self._progress = _QProgressBar()
        self._progress.setFixedWidth(160)
        self._progress.setFixedHeight(18)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setStyleSheet(
            "QProgressBar{border:1px solid white;border-radius:3px;"
            "background:rgba(255,255,255,0.2);color:white;font-size:11px;}"
            "QProgressBar::chunk{background:white;border-radius:2px;}"
        )
        self._progress.hide()
        layout.addWidget(self._progress)

        if download_url:
            self._update_btn = _QPushButton("Update Now")
            self._update_btn.setFixedHeight(28)
            self._update_btn.setStyleSheet(
                "QPushButton{background:white;color:#0F62FE;border:none;"
                "border-radius:4px;padding:0 14px;font-size:12px;font-weight:bold;}"
                "QPushButton:hover{background:#e8e8e8;}"
                "QPushButton:disabled{background:rgba(255,255,255,0.4);color:#aaa;}"
            )
            self._update_btn.clicked.connect(self._start_download)
            layout.addWidget(self._update_btn)

        close_btn = _QPushButton("X")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(
            "QPushButton{background:transparent;color:white;border:none;"
            "font-size:14px;font-weight:bold;}"
            "QPushButton:hover{background:rgba(255,255,255,0.25);border-radius:4px;}"
        )
        close_btn.clicked.connect(self._dismiss)
        layout.addWidget(close_btn)

        self._reposition()
        parent.installEventFilter(self)

    # ── layout ────────────────────────────────────────────────────────────────

    def _reposition(self):
        mw = self.parent()
        try:
            menu_h = mw.menuBar().height()
        except Exception:
            menu_h = 30
        self.setGeometry(0, menu_h, mw.width(), self.height())
        self.raise_()
        self.show()

    def eventFilter(self, obj, event):
        if obj is self.parent() and event.type() == QtCore.QEvent.Resize:
            self._reposition()
        return False

    # ── dismiss ───────────────────────────────────────────────────────────────

    def _dismiss(self):
        global _active_banner
        self._alive = False
        _active_banner = None
        try:
            import AutoCheckUpdates
            AutoCheckUpdates.stop_update_polling()
        except Exception:
            pass
        self.hide()
        self.deleteLater()

    # ── download & install ────────────────────────────────────────────────────

    def _start_download(self):
        # Stop auto-checker immediately so no second banner appears during download
        try:
            import AutoCheckUpdates
            AutoCheckUpdates.stop_update_polling()
        except Exception:
            pass

        self._update_btn.setEnabled(False)
        self._update_btn.setText("Preparing…")
        self._progress.show()
        self._lbl.setText(
            "<span style='color:white;font-size:13px;font-weight:bold;'>"
            "  Fetching download link…</span>"
        )

        # Shared state between background thread and main-thread poll
        _state = {"progress": None, "done": False, "error": None, "path": None}
        _alive = [True]   # closure flag — independent of widget lifetime

        def _worker():
            """Background: get fresh signed URL then stream-download the EXE."""
            try:
                import json, ssl
                import UpdateChecker

                # 1. Fresh signed URL
                payload = json.dumps(
                    {"version": UpdateChecker.CURRENT_VERSION}
                ).encode("utf-8")
                req = urllib.request.Request(
                    "https://bnc-ai.com/api/software/latest",
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "x-api-key": "dt_159391eaf5d473b843d92dc765b2668a386d756d54302c4a5951b7d38f6a558a",
                    },
                    method="POST",
                )
                ctx = ssl.create_default_context()
                with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                fresh_url = body.get("data", body).get("download_url", "")
                if not fresh_url:
                    _state["error"] = "No download URL returned by server."
                    return

                # 2. Stream download with progress
                # IMPORTANT: avoid words like "update","setup","install","patch" in the
                # filename — Windows UAC compatibility shim auto-elevates any EXE whose
                # name contains those words, overriding the per-user manifest.
                tmp_path = os.path.join(tempfile.gettempdir(), "BNC_CAD.exe")

                with urllib.request.urlopen(fresh_url, timeout=300) as src:
                    total = int(src.headers.get("Content-Length", 0))
                    downloaded = 0
                    chunk = 1024 * 256   # 256 KB chunks
                    with open(tmp_path, "wb") as f:
                        while _alive[0]:
                            data = src.read(chunk)
                            if not data:
                                break
                            f.write(data)
                            downloaded += len(data)
                            if total > 0:
                                _state["progress"] = min(
                                    int(downloaded * 100 / total), 99
                                )

                if not _alive[0]:
                    return   # user dismissed mid-download
                _state["path"] = tmp_path
                _state["done"] = True

            except Exception as exc:
                _state["error"] = str(exc)

        threading.Thread(target=_worker, daemon=True).start()

        def _poll():
            # Stop if banner was dismissed
            if not _alive[0]:
                return

            if _state["error"]:
                err = _state["error"]
                FreeCAD.Console.PrintError(f"BNC: Download failed: {err}\n")
                _alive[0] = False
                try:
                    _QMsgBox.critical(
                        FreeCADGui.getMainWindow(), "Download Failed",
                        f"Could not download the update:\n{err}"
                    )
                    self._update_btn.setEnabled(True)
                    self._update_btn.setText("Update Now")
                    self._progress.hide()
                    self._lbl.setText(
                        "<span style='color:white;font-size:13px;font-weight:bold;'>"
                        "  Update available — try again.</span>"
                    )
                except RuntimeError:
                    pass
                return

            if _state["done"]:
                path = _state["path"]
                _alive[0] = False
                FreeCAD.Console.PrintMessage(f"BNC: Download complete — {path}\n")
                try:
                    self._progress.setValue(100)
                    self._lbl.setText(
                        "<span style='color:white;font-size:13px;font-weight:bold;'>"
                        "  Download complete! Launching installer…</span>"
                    )
                except RuntimeError:
                    pass
                QtCore.QTimer.singleShot(300, lambda: _launch(path))
                return

            # Show progress while downloading
            if _state["progress"] is not None:
                try:
                    self._progress.setValue(_state["progress"])
                    self._lbl.setText(
                        "<span style='color:white;font-size:13px;font-weight:bold;'>"
                        f"  Downloading… {_state['progress']}%</span>"
                    )
                except RuntimeError:
                    _alive[0] = False
                    return

            # Still waiting — reschedule
            QtCore.QTimer.singleShot(400, _poll)

        def _launch(path):
            try:
                # Per-user install default: %LOCALAPPDATA%\BNC_CAD (no UAC needed)
                local_appdata = os.environ.get(
                    "LOCALAPPDATA",
                    os.path.join(os.path.expanduser("~"), "AppData", "Local")
                )
                freecad_exe = os.path.join(local_appdata, "BNC_CAD", "bin", "FreeCAD.exe")

                try:
                    import winreg
                    # HKCU = per-user install. HKLM = legacy system install fallback.
                    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                        try:
                            key = winreg.OpenKey(hive, r"Software\BNC CAD")
                            install_dir = winreg.QueryValueEx(key, "InstallLocation")[0]
                            winreg.CloseKey(key)
                            candidate = os.path.join(install_dir, "bin", "FreeCAD.exe")
                            if os.path.exists(candidate):
                                freecad_exe = candidate
                                break
                        except Exception:
                            continue
                except Exception:
                    pass

                FreeCAD.Console.PrintMessage(f"BNC: Relaunch target: {freecad_exe}\n")

                tmp      = tempfile.gettempdir()
                log_path = os.path.join(tmp, "bnc_update.log")
                bat_path = os.path.join(tmp, "bnc_update.bat")
                vbs_path = os.path.join(tmp, "bnc_update.vbs")

                # Batch file: run installer silently, then read registry for actual
                # install path (installer may land in Program Files or LocalAppData
                # depending on version). Falls back to the pre-computed path.
                bat = (
                    "@echo off\r\n"
                    f'echo %DATE% %TIME%: starting >> "{log_path}"\r\n'
                    f'"{path}" /S\r\n'
                    f'echo %DATE% %TIME%: installed >> "{log_path}"\r\n'
                    "timeout /t 1 /nobreak > nul\r\n"
                    "set INSTDIR=\r\n"
                    'for /f "tokens=2*" %%a in (\'reg query "HKCU\\Software\\BNC CAD" /v InstallLocation 2^>nul\') do set INSTDIR=%%b\r\n'
                    "if not defined INSTDIR (\r\n"
                    '  for /f "tokens=2*" %%a in (\'reg query "HKLM\\Software\\BNC CAD" /v InstallLocation 2^>nul\') do set INSTDIR=%%b\r\n'
                    ")\r\n"
                    f'if not defined INSTDIR set INSTDIR={os.path.join(local_appdata, "BNC_CAD")}\r\n'
                    f'echo %DATE% %TIME%: launching %INSTDIR% >> "{log_path}"\r\n'
                    'start "" "%INSTDIR%\\bin\\FreeCAD.exe"\r\n'
                    f'echo %DATE% %TIME%: done >> "{log_path}"\r\n'
                )
                with open(bat_path, "w", encoding="utf-8") as f:
                    f.write(bat)
                FreeCAD.Console.PrintMessage(f"BNC: Batch written: {bat_path}\n")

                # VBScript launches the batch hidden with bWaitOnReturn=False.
                # WScript.Shell.Run spawns a completely independent process that
                # is NOT in FreeCAD's job object and will NOT be killed when
                # FreeCAD exits — this is the Windows-native detach mechanism.
                vbs = (
                    'Set ws = CreateObject("WScript.Shell")\r\n'
                    f'ws.Run Chr(34) & "{bat_path}" & Chr(34), 0, False\r\n'
                )
                with open(vbs_path, "w", encoding="utf-8") as f:
                    f.write(vbs)
                FreeCAD.Console.PrintMessage(f"BNC: VBS written: {vbs_path}\n")

                wscript = os.path.join(
                    os.environ.get("SystemRoot", r"C:\Windows"),
                    "System32", "wscript.exe"
                )
                subprocess.Popen(
                    [wscript, "/nologo", vbs_path],
                    shell=False,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                FreeCAD.Console.PrintMessage("BNC: Update agent launched — closing BNC CAD\n")

            except Exception as exc:
                FreeCAD.Console.PrintError(f"BNC: Launch installer failed: {exc}\n")

            import time
            time.sleep(0.3)  # give wscript a moment to start before FreeCAD closes
            try:
                FreeCADGui.getMainWindow().close()
            except Exception:
                pass

        QtCore.QTimer.singleShot(400, _poll)


# ── public helpers ─────────────────────────────────────────────────────────────

def show_update_banner(message="", download_url=""):
    global _active_banner
    try:
        mw = FreeCADGui.getMainWindow()
        if not mw:
            FreeCAD.Console.PrintError("BNC: show_update_banner — no main window\n")
            return
        if _active_banner is not None:
            try:
                _active_banner._dismiss()
            except Exception:
                _active_banner = None
        _active_banner = _UpdateBanner(message, download_url, mw)
        FreeCAD.Console.PrintMessage("BNC: Update banner shown\n")
    except Exception as exc:
        FreeCAD.Console.PrintError(f"BNC: show_update_banner error: {exc}\n")


def hide_update_banner():
    global _active_banner
    if _active_banner is not None:
        try:
            _active_banner._dismiss()
        except Exception:
            _active_banner = None
