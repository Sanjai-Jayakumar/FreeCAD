# ANVIL CAD Custom Tools Integration

## Overview

This module integrates custom file operations and tools into ANVIL CAD (FreeCAD) without creating a separate workbench. The tools appear as a persistent toolbar across all workbenches.

## Features

The following custom tools are added to ANVIL CAD:

### 1. **New File** (NEW_FILE.svg)
- Creates a new document with options for:
  - Sketch
  - Part Design
  - Assembly
  - Drawing (TechDraw)
- Allows entering part name and description
- Automatically switches to the selected workbench

### 2. **Open File** (Open.svg)
- Opens files with version control support
- Shows only latest versions by default
- Option to show all versions
- Filters files based on `.###.FCStd` version pattern

### 3. **Save** (save.svg)
- Saves document with automatic version control
- Creates versioned files (e.g., `PartName.001.FCStd`, `PartName.002.FCStd`)
- Only creates new version if document has been modified
- Tracks changes using undo counter

### 4. **Save As** (save_as.svg)
- Save As dialog with version control
- Allows changing file name and location
- Updates working directory if changed
- Maintains version numbering

### 5. **Set Working Directory** (SET_WD.svg)
- Sets the working directory for all file operations
- Updates window title to show current working directory
- Persists across FreeCAD sessions

### 6. **Pipe Bending** (pipe_bending.svg)
- Creates bent pipe designs with customizable parameters:
  - Outer radius
  - Wall thickness
  - Bend radius
  - Bend angle
  - Straight sections before and after bend

## Installation

The module is installed in:
```
BNC_CAD_1.0.2/data/Mod/BNCCustomTools/
```

### Files Structure:
```
BNCCustomTools/
├── __init__.py           # Module initialization
├── Init.py               # FreeCAD initialization
├── InitGui.py            # GUI initialization and toolbar setup
├── Commands.py           # Command implementations
├── NewFileDialog.py      # New file dialog
├── PipeBendingDialog.py  # Pipe bending dialog
└── Resources/
    └── icons/
        ├── NEW_FILE.svg
        ├── Open.svg
        ├── save.svg
        ├── save_as.svg
        ├── SET_WD.svg
        └── pipe_bending.svg
```

## How It Works

1. **Automatic Loading**: When ANVIL CAD (FreeCAD) starts, it automatically loads all modules in the `Mod` directory.

2. **Command Registration**: The `InitGui.py` file registers all commands globally using `FreeCADGui.addCommand()`.

3. **Toolbar Creation**: A custom toolbar named "BNC Custom Tools" is created and added to the main window.

4. **Icon Loading**: Icons are loaded from the `Resources/icons` directory and associated with each command.

5. **Persistent Toolbar**: The toolbar persists across all workbenches and is available at all times.

## Version Control System

The integrated version control system works as follows:

- Files are saved with the format: `FileName.###.FCStd` (e.g., `MyPart.001.FCStd`)
- Each time you save with modifications, a new version is created
- The system tracks changes using the undo counter
- Opening files shows only the latest version by default
- You can view all versions by checking "Show all versions"

## Usage

1. **First Time Setup**:
   - Click "Set Working Directory" to choose your project folder
   - This sets where all files will be saved and opened from

2. **Creating New Files**:
   - Click "New File"
   - Select the type of document you want to create
   - Enter part name and description
   - Click OK

3. **Saving Files**:
   - Use "Save" for regular saves (creates new version if modified)
   - Use "Save As" to change file name or location

4. **Opening Files**:
   - Click "Open File"
   - Select from available files (latest versions shown by default)
   - Check "Show all versions" to see all historical versions

## Benefits

- **Non-invasive**: Doesn't create a new workbench, just adds tools to existing UI
- **Always Available**: Toolbar appears in all workbenches
- **Version Control**: Built-in file versioning prevents data loss
- **Professional Workflow**: Streamlines common CAD operations

## Technical Notes

- Commands are registered globally using FreeCAD's command system
- Icons are SVG format for crisp display at any size
- The toolbar is created using Qt's QToolBar system
- Commands use PySide (Qt) for dialogs and UI

## Future Enhancements

Potential additions:
- Export to various formats
- Batch processing tools
- More specialized CAD tools
- Integration with external systems

---

**Note**: This is a custom module for ANVIL CAD. It extends FreeCAD's functionality without modifying core files.
