# SPDX-License-Identifier: LGPL-2.1-or-later

import os

# Add FreeCAD DLL directories to the search path before importing AssemblyApp.
# Python 3.8+ isolates DLL loading for .pyd extensions — neither PATH nor
# SetDllDirectory affect it. os.add_dll_directory() is the only mechanism.
# Cookies MUST be kept alive at module level — GC removes the dirs otherwise.
_dll_cookies = []
try:
    import FreeCAD as _FC
    _home = _FC.getHomePath()
    for _subdir in ("bin", "lib"):
        _d = os.path.join(_home, _subdir)
        if os.path.isdir(_d):
            _dll_cookies.append(os.add_dll_directory(_d))
    del _FC, _home, _subdir, _d
except Exception:
    pass

try:
    import AssemblyApp
except ImportError:
    pass  # Already loaded by FreeCAD's C++ module loader at startup
