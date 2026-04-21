# BNC CAD Update System - Frontend Implementation

## Overview
This is a **frontend-only demonstration** of the BNC CAD auto-update system. It provides the complete user interface (VS Code-style update banner, dialogs) without requiring backend infrastructure.

## Mock Mode Status
✅ **Currently in MOCK MODE** - Simulates update availability for demonstration purposes

## Files Created

### 1. UpdateChecker.py
- Handles version checking logic
- **MOCK_MODE = True** - Returns simulated update data
- **MOCK_UPDATE_AVAILABLE = True** - Controls whether mock update appears
- Ready to switch to real backend (set MOCK_MODE = False)

### 2. UpdateUI.py
- VS Code-style notification banner (blue background, white text)
- Release notes dialog
- Download confirmation dialog
- Integrates into FreeCAD main window

### 3. CommandCheckForUpdates.py
- FreeCAD command registration
- Adds "Check for Updates..." to Help menu
- Keyboard shortcut: Ctrl+U

### 4. Resources/icons/update-icon.svg
- Blue circular icon with download arrow
- Used in Help menu

### 5. InitGui.py (modified)
- Loads CommandCheckForUpdates on startup

## How to Use (Frontend Demo)

### Testing the Update Banner
1. Build BNC CAD with the new files
2. Launch BNC CAD
3. Go to **Help → Check for Updates** (or press Ctrl+U)
4. The update banner will appear at the top of the window

### Banner Features
- Shows current version and new version
- Three action buttons:
  - **Release Notes** - View what's new
  - **Download Update** - Simulate download (shows mock message)
  - **Later** - Dismiss banner
- Close button (×) in top-right corner

### Customizing Mock Data
Edit `UpdateChecker.py` to change mock behavior:

```python
# Line 11-12: Control mock behavior
MOCK_MODE = True                    # Set to False when backend is ready
MOCK_UPDATE_AVAILABLE = True        # Set to False to test "no update" scenario

# Line 42-56: Edit mock update details
self.available_version = "1.2.0"    # New version number
self.release_notes = """..."""       # Markdown-formatted notes
self.file_size = 850 * 1024 * 1024  # File size in bytes
```

## Switching to Real Backend

When your backend team has the EC2 server ready:

### Step 1: Update Configuration
Edit `UpdateChecker.py`:
```python
MOCK_MODE = False  # Line 11
UPDATE_SERVER_URL = "https://your-actual-domain.com/api/version"  # Line 15
```

### Step 2: Backend API Requirements
Your backend must return JSON in this format:
```json
{
  "version": "1.2.0",
  "download_url": "https://your-domain.com/updates/BNC_CAD_1.2.0.exe",
  "release_notes": "**What's New**\n\n• Feature 1\n• Feature 2",
  "file_size": 891289600,
  "checksum": "sha256:abc123..."
}
```

### Step 3: No Other Code Changes Needed
- The UI automatically switches from mock to real data
- Download functionality will activate (currently shows mock message)

## Current Limitations (Mock Mode)

1. **No Actual Downloads** - "Download Update" shows info message instead
2. **No Version Persistence** - Doesn't remember "Later" dismissal
3. **No Auto-Check** - Manual check only via Help menu
4. **No Background Download** - Will be implemented when backend ready

## Future Implementation (When Backend Ready)

When you switch to real backend, you can implement:
- Background downloading with progress bar
- SHA256 checksum verification
- Automatic silent installation
- Auto-check on startup (weekly)
- Download resume capability

## Testing Scenarios

### Scenario 1: Update Available
```python
MOCK_UPDATE_AVAILABLE = True
```
Result: Banner appears with update notification

### Scenario 2: No Update
```python
MOCK_UPDATE_AVAILABLE = False
```
Result: Dialog says "You are using the latest version"

### Scenario 3: Release Notes
Click "Release Notes" button → Shows formatted markdown notes

### Scenario 4: Download (Mock)
Click "Download Update" → Confirm → Shows mock message with URL

## Demo for Backend Team

Show your backend team:
1. The banner UI design and behavior
2. The expected JSON response format (in `_real_check()` method)
3. The API endpoint structure
4. File size and checksum requirements

## Version Information

- **Current Mock Version**: 1.1.0
- **Mock Update Version**: 1.2.0
- **Update Check Interval**: 7 days (when auto-check implemented)

## Technical Notes

- Uses PySide/Qt for UI components
- Integrates with FreeCAD's main window layout
- Non-blocking UI (doesn't freeze application)
- Banner auto-removes when dismissed
- Compatible with FreeCAD 1.1+ and Qt 4.8+

## Questions?

For backend integration questions, refer to:
- `/memories/session/auto-update-plan.md` - Complete implementation plan
- `/memories/session/update-alert-system-plan.md` - EC2 backend setup guide

---

**Status**: ✅ Frontend Complete - Ready for Backend Integration
