"""Extract all SVGs from Assembly_rc.py via Qt's resource system, recolor by
region, and save to Resources/icons/recolored/."""
import os
import re
import sys

ROOT = r"D:\Freecad 1.1 installed\Mod\Assembly"
OUT_DIR = os.path.join(ROOT, "Resources", "icons", "recolored")

# Target colors
BLUE    = "#3D8BC7"
YELLOW  = "#FFCC00"
OUTLINE = "#0A2E60"

# Make Assembly_rc importable
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from PySide6 import QtCore
import Assembly_rc  # registers Qt resources under :/


def _hsl_classify(hex_color):
    """Return BLUE/YELLOW/OUTLINE/None based on color hue/lightness."""
    h = hex_color.lstrip("#").lower()
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return None
    try:
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
    except ValueError:
        return None
    mx = max(r, g, b)
    mn = min(r, g, b)
    L = (mx + mn) / 2 / 255.0
    if mx == mn:
        if L < 0.30:
            return OUTLINE
        return None
    d = mx - mn
    if mx == r:
        hue = ((g - b) / d) % 6
    elif mx == g:
        hue = (b - r) / d + 2
    else:
        hue = (r - g) / d + 4
    hue *= 60
    if 180 <= hue <= 260:
        return BLUE
    if 30 <= hue <= 70:
        return YELLOW
    if L < 0.20:
        return OUTLINE
    return None


def recolor_svg(svg_text):
    """Replace hex colors throughout the SVG."""
    def _hex_repl(m):
        new = _hsl_classify(m.group(0))
        return new if new else m.group(0)
    return re.sub(r"#[0-9A-Fa-f]{3,6}\b", _hex_repl, svg_text)


def _walk(prefix):
    """Yield all file paths under prefix in the Qt resource system."""
    d = QtCore.QDir(prefix)
    for entry in d.entryList(QtCore.QDir.Files):
        yield prefix.rstrip("/") + "/" + entry
    for sub in d.entryList(QtCore.QDir.Dirs | QtCore.QDir.NoDotAndDotDot):
        yield from _walk(prefix.rstrip("/") + "/" + sub)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    total_files = 0
    saved = 0
    skipped = 0
    for path in _walk(":"):
        total_files += 1
        if not path.lower().endswith(".svg"):
            continue
        f = QtCore.QFile(path)
        if not f.open(QtCore.QIODevice.ReadOnly):
            continue
        try:
            data = bytes(f.readAll().data()).decode("utf-8", errors="replace")
        finally:
            f.close()
        if "<svg" not in data:
            skipped += 1
            continue
        recolored = recolor_svg(data)
        base = os.path.basename(path)
        out_path = os.path.join(OUT_DIR, base)
        with open(out_path, "w", encoding="utf-8") as out:
            out.write(recolored)
        saved += 1
    print(f"Walked {total_files} files in Qt resource tree")
    print(f"Saved {saved} recolored SVGs to: {OUT_DIR}")
    print(f"Skipped {skipped} non-SVG files")


if __name__ == "__main__":
    main()
