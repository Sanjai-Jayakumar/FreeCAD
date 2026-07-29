# SPDX-License-Identifier: LGPL-2.1-or-later
"""PySide2/PySide6 compatibility layer — every BNCClassA GUI file imports Qt
through this module (pattern from BNCGSD/panels/ModeSwitchPanel.py)."""

try:
    from PySide2 import QtWidgets, QtCore, QtGui
    Qt = QtCore.Qt
    TEXT_UNDER_ICON = Qt.ToolButtonTextUnderIcon
    SCROLL_AS_NEEDED = Qt.ScrollBarAsNeeded
    SCROLL_OFF = Qt.ScrollBarAlwaysOff
    NO_FRAME = QtWidgets.QFrame.NoFrame
    ALIGN_CENTER = Qt.AlignCenter
    ALIGN_RIGHT = Qt.AlignRight
    HORIZONTAL = Qt.Horizontal
    CHECKED = Qt.Checked
    BTN_CLOSE = int(QtWidgets.QDialogButtonBox.Close)
    BTN_OK = int(QtWidgets.QDialogButtonBox.Ok)
    BTN_CANCEL = int(QtWidgets.QDialogButtonBox.Cancel)
except ImportError:
    from PySide6 import QtWidgets, QtCore, QtGui
    Qt = QtCore.Qt
    TEXT_UNDER_ICON = Qt.ToolButtonStyle.ToolButtonTextUnderIcon
    SCROLL_AS_NEEDED = Qt.ScrollBarPolicy.ScrollBarAsNeeded
    SCROLL_OFF = Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    NO_FRAME = QtWidgets.QFrame.Shape.NoFrame
    ALIGN_CENTER = Qt.AlignmentFlag.AlignCenter
    ALIGN_RIGHT = Qt.AlignmentFlag.AlignRight
    HORIZONTAL = Qt.Orientation.Horizontal
    CHECKED = Qt.CheckState.Checked
    # .value: these enums are not int()-convertible in this shiboken build
    BTN_CLOSE = int(QtWidgets.QDialogButtonBox.StandardButton.Close.value)
    BTN_OK = int(QtWidgets.QDialogButtonBox.StandardButton.Ok.value)
    BTN_CANCEL = int(QtWidgets.QDialogButtonBox.StandardButton.Cancel.value)

__all__ = [
    "QtWidgets", "QtCore", "QtGui", "Qt",
    "TEXT_UNDER_ICON", "SCROLL_AS_NEEDED", "SCROLL_OFF", "NO_FRAME",
    "ALIGN_CENTER", "ALIGN_RIGHT", "HORIZONTAL", "CHECKED",
    "BTN_CLOSE", "BTN_OK", "BTN_CANCEL",
]
