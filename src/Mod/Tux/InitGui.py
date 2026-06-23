# SPDX-License-Identifier: LGPL-2.1-or-later

# Tux module for FreeCAD
# Copyright (C) 2017  triplus @ FreeCAD
#
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA

"""Tux module for FreeCAD."""

import FreeCAD
import FreeCADGui
import os

try:  # Prefer PySide but allow PySide2 fallback
    from PySide import QtCore, QtGui
    QtWidgets = QtGui
except ImportError:  # pragma: no cover - depends on runtime binding
    from PySide2 import QtCore, QtGui, QtWidgets


_THEME_SETTINGS_CACHE = None


def _theme_settings():
    """Return theme metadata ensuring it is always available."""
    global _THEME_SETTINGS_CACHE
    if _THEME_SETTINGS_CACHE is None:
        _THEME_SETTINGS_CACHE = {
            "dark": {
                "stylesheet": "BNC Theme Dark.qss",
                "overlay": "BNC Theme Dark Overlay.qss",
                "theme_label": "BNC Theme Dark",
                "icon": ":/icons/bnc_theme_toggle_light.svg",
                "tooltip": "Switch to BNC Theme Light",
                "view_unsigned": {
                    "BackgroundColor": 556083711,
                    "BackgroundColor2": 876232959,
                    "BackgroundColor3": 556083711,
                    "BackgroundColor4": 556083711,
                    "SelectionColor": 582537215,
                    "DefaultShapeColor": 1920565503,
                    "DefaultShapeLineColor": 2914369023,
                    "HighlightColor": 363511807,
                },
                "view_bools": {"Gradient": False, "RadialGradient": True},
            },
            "light": {
                "stylesheet": "BNC Theme Light.qss",
                "overlay": "BNC Theme Light Overlay.qss",
                "theme_label": "BNC Theme Light",
                "icon": ":/icons/bnc_theme_toggle_dark.svg",
                "tooltip": "Switch to BNC Theme Dark",
                "view_unsigned": {
                    "BackgroundColor": 2896692223,  # Light gray #ACACAC (172, 172, 172)
                    "BackgroundColor2": 3235906047,  # Slightly lighter for gradient top
                    "BackgroundColor3": 2896692223,  # Light gray #ACACAC
                    "BackgroundColor4": 2896692223,  # Light gray #ACACAC
                    "SelectionColor": 210082303,
                    "DefaultShapeColor": 2914369023,
                    "DefaultShapeLineColor": 421075455,
                    "HighlightColor": 192054783,
                },
                "view_bools": {"Gradient": False, "RadialGradient": False},
            },
        }
    return _THEME_SETTINGS_CACHE


p = FreeCAD.ParamGet("User parameter:Tux")

_THEME_PREFS = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/BNC")
_theme_toggle_button = None
_qss_search_path_ready = False
_stylesheet_dir = None


def _ensure_stylesheet_search_path():
    """Make sure Qt can resolve qss: resource paths for bundled assets."""
    global _qss_search_path_ready
    if _qss_search_path_ready:
        return
    try:
        base_dir = FreeCAD.getResourceDir()
    except AttributeError:
        return
    if not base_dir:
        return
    stylesheets_dir = os.path.join(base_dir, "Gui", "Stylesheets")
    if not os.path.isdir(stylesheets_dir):
        return
    QtCore.QDir.addSearchPath("qss", QtCore.QDir.toNativeSeparators(stylesheets_dir))
    global _stylesheet_dir
    _stylesheet_dir = stylesheets_dir
    _qss_search_path_ready = True


def _rename_legacy_opentheme_files():
    """Promote leftover OpenTheme stylesheets to the new BNC naming."""
    try:
        user_dir = FreeCAD.getUserAppDataDir()
    except AttributeError:
        return
    if not user_dir:
        return
    stylesheet_dir = os.path.join(user_dir, "Gui", "Stylesheets")
    if not os.path.isdir(stylesheet_dir):
        return
    migration_map = {
        "OpenDark.qss": "BNC Theme Dark.qss",
        "OpenLight.qss": "BNC Theme Light.qss",
        "OpenDark_Overlay.qss": "BNC Theme Dark Overlay.qss",
        "OpenLight_Overlay.qss": "BNC Theme Light Overlay.qss",
    }
    for legacy, target in migration_map.items():
        legacy_path = os.path.join(stylesheet_dir, legacy)
        if not os.path.isfile(legacy_path):  # Nothing to migrate
            continue
        target_path = os.path.join(stylesheet_dir, target)
        if os.path.exists(target_path):
            try:
                os.remove(legacy_path)
            except OSError:
                pass
            continue
        try:
            os.rename(legacy_path, target_path)
        except OSError:
            # Fall back to leaving the legacy file in place if rename fails
            pass


def _load_stylesheet(stylesheet):
    """Apply the selected stylesheet immediately from disk."""
    if not _stylesheet_dir:
        _ensure_stylesheet_search_path()
    if not _stylesheet_dir:
        return False
    file_path = os.path.join(_stylesheet_dir, stylesheet)
    if not os.path.isfile(file_path):
        FreeCAD.Console.PrintWarning(
            f"Stylesheet '{stylesheet}' not found at {file_path}. Using default look instead.\n"
        )
        return False
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            QtWidgets.QApplication.instance().setStyleSheet(handle.read())
    except Exception as err:  # pragma: no cover - relies on runtime
        FreeCAD.Console.PrintWarning(
            f"Failed to load stylesheet '{stylesheet}': {err}. Using default look instead.\n"
        )
        return False
    return True


def _apply_view_settings(mode):
    settings = _theme_settings()[mode]
    view_prefs = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/View")
    for key, value in settings.get("view_unsigned", {}).items():
        view_prefs.SetUnsigned(key, int(value))
    for key, value in settings.get("view_bools", {}).items():
        view_prefs.SetBool(key, bool(value))


def _apply_theme_mode(mode):
    _ensure_stylesheet_search_path()
    settings = _theme_settings().get(mode, _theme_settings()["dark"])
    main_prefs = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/MainWindow")
    if main_prefs.GetString("StyleSheet", "") != settings["stylesheet"]:
        main_prefs.SetString("StyleSheet", settings["stylesheet"])
    if main_prefs.GetString("OverlayActiveStyleSheet", "") != settings["overlay"]:
        main_prefs.SetString("OverlayActiveStyleSheet", settings["overlay"])
    if main_prefs.GetString("Theme", "") != settings["theme_label"]:
        main_prefs.SetString("Theme", settings["theme_label"])
    _load_stylesheet(settings["stylesheet"])
    _apply_view_settings(mode)
    _THEME_PREFS.SetString("Mode", mode)
    try:
        FreeCADGui.runCommand("Std_ApplyCurrentPreferences", 0)
    except Exception:
        FreeCAD.Console.PrintWarning(
            "Unable to refresh preferences immediately. Restart to ensure theme changes apply.\n"
        )


def _current_mode():
    stored = _THEME_PREFS.GetString("Mode", "")
    stylesheet = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/MainWindow").GetString(
        "StyleSheet", ""
    )
    theme_settings = _theme_settings()
    if stylesheet == theme_settings["light"]["stylesheet"]:
        return "light"
    if stylesheet == theme_settings["dark"]["stylesheet"]:
        return "dark"
    return stored if stored in theme_settings else "dark"


def _update_toggle_button():
    if not _theme_toggle_button:
        return
    mode = _current_mode()
    settings = _theme_settings()[mode]
    try:
        _theme_toggle_button.blockSignals(True)
        _theme_toggle_button.setChecked(mode == "light")
        _theme_toggle_button.setIcon(QtGui.QIcon(settings["icon"]))
        _theme_toggle_button.setToolTip(settings["tooltip"])
    finally:
        _theme_toggle_button.blockSignals(False)


def _toggle_theme():
    new_mode = "light" if _current_mode() == "dark" else "dark"
    _apply_theme_mode(new_mode)
    _update_toggle_button()


def _ensure_toggle_button():
    global _theme_toggle_button
    if not FreeCAD.GuiUp:
        return
    main_window = FreeCADGui.getMainWindow()
    if not main_window:
        return
    if _theme_toggle_button is None:
        button = QtWidgets.QToolButton(main_window)
        button.setObjectName("bncThemeToggleButton")
        button.setCheckable(True)
        button.clicked.connect(_toggle_theme)
        main_window.menuBar().setCornerWidget(button, QtCore.Qt.TopRightCorner)
        _theme_toggle_button = button
    _update_toggle_button()


def _initialise_theme():
    # All sibling-function calls are wrapped in try/except NameError because
    # FreeCADGuiInit.RunInitGuiPy uses exec() without an explicit globals dict,
    # so functions' __globals__ is FreeCADGuiInit's module dict — not the dict
    # where sibling functions were defined.  The fallback paths keep the theme
    # initialisation working even when name lookup fails.
    try:
        _rename_legacy_opentheme_files()
    except Exception:
        FreeCAD.Console.PrintWarning(
            "Theme migration helper missing; proceeding without renaming legacy OpenTheme files.\n"
        )

    stylesheet = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/MainWindow").GetString(
        "StyleSheet", ""
    )

    try:
        theme_settings = _theme_settings()
    except NameError:
        theme_settings = {
            "dark": {"stylesheet": "BNC Theme Dark.qss"},
            "light": {"stylesheet": "BNC Theme Light.qss"},
        }

    bnc_stylesheets = (
        theme_settings["dark"]["stylesheet"],
        theme_settings["light"]["stylesheet"],
    )

    if stylesheet not in bnc_stylesheets:
        # BNC CAD: Default to light theme instead of dark
        try:
            _apply_theme_mode("light")
        except NameError:
            _mp = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/MainWindow")
            _mp.SetString("StyleSheet", "BNC Theme Light.qss")
            _mp.SetString("OverlayActiveStyleSheet", "BNC Theme Light Overlay.qss")
            _mp.SetString("Theme", "BNC Theme Light")
    else:
        try:
            _THEME_PREFS.SetString("Mode", _current_mode())
            _apply_view_settings(_current_mode())
        except NameError:
            pass

    try:
        QtCore.QTimer.singleShot(0, _ensure_toggle_button)
    except NameError:
        pass


# Ensure BNC Theme is used by default and prepare toggle UI
if FreeCAD.GuiUp:
    try:
        _initialise_theme()
    except Exception as _e:
        FreeCAD.Console.PrintWarning(f"BNC: theme initialisation failed: {_e}\n")


# Navigation indicator
if p.GetGroup("NavigationIndicator").GetBool("Enabled", 1):
    import NavigationIndicatorGui
else:
    pass


# Persistent toolbars
# BNC CAD CUSTOMIZATION: Forcibly disable PersistentToolbars to prevent toolbar grouping
p.GetGroup("PersistentToolbars").SetBool("Enabled", False)

# Clear any existing cached toolbar positions
try:
    pUser = App.ParamGet("User parameter:Tux/PersistentToolbars/User")
    pSystem = App.ParamGet("User parameter:Tux/PersistentToolbars/System")
    for group in pUser.GetGroups():
        pUser.RemGroup(group)
    for group in pSystem.GetGroups():
        pSystem.RemGroup(group)
    App.Console.PrintMessage("BNC CAD: PersistentToolbars disabled to prevent grouping\n")
except:
    pass

# Original code - will now always skip loading PersistentToolbarsGui
if p.GetGroup("PersistentToolbars").GetBool("Enabled", 1):
    import PersistentToolbarsGui
else:
    pass

# Temporary - for FreeCAD v1.0
# Detect a possible clash between the built-in BIM WB in v1.0
# and the BIM addon. Resolve this by renaming the BIM add-on path
try:
    import Arch_rc

    # we could import Arch_rc, nothing to be done, either we are
    # running built-in BIM without the addon, or the addon without built-in BIM
except:
    # Arch_rc not importable: We have both the BIM addon and the built-in BIM
    from pathlib import Path

    bim_modpath = Path(FreeCAD.getUserAppDataDir(), "Mod", "BIM")
    try:
        bim_modpath.rename(bim_modpath.with_name("BIM021"))
    except FileNotFoundError:
        pass
    else:
        FreeCAD.Console.PrintWarning(
            "BIM addon path has been renamed to BIM021 to avoid conflicts with the builtin BIM workbench. Please restart FreeCAD\n"
        )
