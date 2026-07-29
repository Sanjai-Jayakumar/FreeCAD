# SPDX-License-Identifier: LGPL-2.1-or-later
"""Headless test runner for the BNCClassA geometry core.

Run with:  FreeCADCmd.exe <path>/run_all.py
"""
import os
import sys
import traceback

_tests_dir = os.path.dirname(os.path.abspath(__file__))
_mod_dir = os.path.dirname(os.path.dirname(_tests_dir))   # .../Mod/BNCClassA
if _mod_dir not in sys.path:
    sys.path.insert(0, _mod_dir)

TEST_MODULES = [
    "BNCClassA.tests.test_bezier",
    "BNCClassA.tests.test_nurbs_io",
    "BNCClassA.tests.test_continuity",
    "BNCClassA.tests.test_fairing",
    "BNCClassA.tests.test_builders",
    "BNCClassA.tests.test_match",
    "BNCClassA.tests.test_blends",
]


def main():
    import importlib
    failures = []
    ran = 0
    for name in TEST_MODULES:
        try:
            mod = importlib.import_module(name)
        except ImportError as e:
            print("SKIP  %s (%s)" % (name, e))
            continue
        for attr in sorted(dir(mod)):
            if not attr.startswith("test_"):
                continue
            ran += 1
            try:
                getattr(mod, attr)()
                print("PASS  %s.%s" % (name.rsplit('.', 1)[-1], attr))
            except Exception:
                failures.append("%s.%s" % (name, attr))
                print("FAIL  %s.%s" % (name.rsplit('.', 1)[-1], attr))
                traceback.print_exc()
    print("\n%d tests, %d failures" % (ran, len(failures)))
    if failures:
        for f in failures:
            print("  FAILED: " + f)
    return 1 if failures else 0


# FreeCADCmd executes scripts with __name__ != "__main__", so run directly.
_rc = main()
if _rc:
    sys.exit(_rc)
