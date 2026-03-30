import os
from functools import lru_cache

import FreeCAD
import FreeCADGui


def insert_part_from_library(relative_path):
    parts_lib_path = os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "parts_library")
    part_path = os.path.join(parts_lib_path, relative_path)

    if not os.path.exists(part_path):
        raise FileNotFoundError("Not found: {}".format(part_path))

    FreeCADGui.ActiveDocument.mergeProject(part_path)


@lru_cache(maxsize=1)
def get_parts_list():
    parts_lib_path = os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "parts_library")

    if not os.path.exists(parts_lib_path):
        raise FileNotFoundError("Not found: {}".format(parts_lib_path))

    parts = []

    for root, _, files in os.walk(parts_lib_path):
        for file in files:
            if file.endswith(".FCStd"):
                relative_path = os.path.relpath(os.path.join(root, file), parts_lib_path)
                parts.append(relative_path)

    return parts
