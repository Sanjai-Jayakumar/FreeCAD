# SPDX-License-Identifier: LGPL-2.1-or-later
"""BNCClassA — Class-A Surface workbench for Anvil CAD.

Alias-style CV modeling, surface matching and optical analysis.
"""
import os

ICONS_DIR = os.path.join(os.path.dirname(__file__), "Resources", "icons")
_FALLBACK_ICON = os.path.join(ICONS_DIR, "BNCClassA.svg")


def icon(name):
    """Absolute path of a command icon SVG, falling back to the workbench icon."""
    path = os.path.join(ICONS_DIR, name if name.endswith(".svg") else name + ".svg")
    return path if os.path.exists(path) else _FALLBACK_ICON
