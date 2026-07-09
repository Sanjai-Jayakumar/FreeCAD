==================================================================
ANVIL CAD - Global Macro System
==================================================================

These 5 macros provide a professional version-controlled workflow:

1. SetWorkingDirectory.FCMacro
   - Set the working directory for your project
   - Keyboard: Ctrl+Shift+W

2. New_File.FCMacro
   - Create new file with Sketch/Part/Assembly/Drawing options
   - Keyboard: Ctrl+N

3. Version_Save.FCMacro
   - Smart save with automatic version control (file.001, file.002, etc.)
   - Keyboard: Ctrl+S

4. Save_As.FCMacro
   - Save As with version control
   - Keyboard: Ctrl+Shift+S

5. OPEN_File.FCMacro
   - Open files with version filtering (show latest or all versions)
   - Keyboard: Ctrl+O

==================================================================
HOW TO USE:
==================================================================

METHOD 1: Keyboard Shortcuts (Recommended)
------------------------------------------
The shortcuts above are pre-configured for quick access.

METHOD 2: Macro Menu
------------------------------------------
1. Go to: Macro → Macros...
2. Select the macro you want to run
3. Click "Execute"

METHOD 3: Custom Toolbar
------------------------------------------
1. Right-click on toolbar area
2. Select "Customize..."
3. Go to "Macros" tab
4. Drag macros to your toolbar

==================================================================
WORKFLOW:
==================================================================

Typical workflow for a new project:

1. Press Ctrl+Shift+W → Set Working Directory
2. Press Ctrl+N → Create New File (choose type)
3. Design your part...
4. Press Ctrl+S → Version Save (creates file.001.FCStd)
5. Make changes...
6. Press Ctrl+S → Version Save (creates file.002.FCStd)
7. Press Ctrl+O → Open File (shows only latest versions)

==================================================================
VERSION CONTROL SYSTEM:
==================================================================

Files are automatically versioned:
  MyPart.001.FCStd  (first save)
  MyPart.002.FCStd  (second save)
  MyPart.003.FCStd  (third save)

- Only saves new version if document was actually modified
- Prevents breaking assembly links
- Easy to revert to previous versions
- Clean file organization in working directory

==================================================================
For support: contact ANVIL CAD team
==================================================================
