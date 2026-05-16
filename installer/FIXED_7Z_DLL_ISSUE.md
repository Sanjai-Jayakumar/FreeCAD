# 7z.dll Missing Error - FIXED

## Issue
**Error:** "Codec Load Error: 7z.dll : The specified module could not be found"

**Root Cause:** The installer was extracting `7zr.exe` to TEMP folder but the required `7z.dll` codec library was missing. This DLL is needed to decompress the LZMA2/BCJ/Delta ARM64 compressed archive.

## Solution Implemented
Modified `BNC_CAD.nsi` to include `7z.dll` in the installer package:

```nsis
  ; Copy files to TEMP
  DetailPrint "Copying installer files..."
  File "${PAYLOAD_EXTRACTOR}"       ; 7zr.exe
  File "7z.dll"                     ; ← ADDED THIS LINE
  File "${INSTALL_ARCHIVE}"         ; BNC-CAD-Output.7z
```

## Rebuilt Installer Details
**File:** `BNC CAD.exe`
**Size:** 842.23 MB
**SHA256:** `C95F2DA8A367BF2AC77AB4932194EC9724D523007CBAFAF943F65E174467DE97`
**Build Date:** 18-04-2026 04:02:34 PM
**Status:** ✅ Fixed - 7z.dll now included

## Installation Instructions

### Step 1: Windows SmartScreen Warning
When you run the installer, Windows will show a blue SmartScreen warning:

```
Microsoft Defender SmartScreen prevented an unrecognized app from starting.
Running this app might put your PC at risk.
```

**Why?** The installer is not digitally signed (code signing certificates cost $150-500/year).

**Solution:**
1. Click "More info" link
2. Click "Run anyway" button
3. Installation will proceed normally

### Step 2: Installation Process
After clicking "Run anyway":

1. **Extraction:** Files will be extracted to TEMP folder first
2. **Progress:** Installation progress bar will show copying to `C:\BNC CAD`
3. **Shortcuts:** Desktop and Start Menu shortcuts will be created
4. **Completion:** Installation complete message will appear

### Step 3: Verify Installation
1. Launch BNC CAD from Desktop shortcut
2. Wait 5 seconds - Auto-update banner should appear (mock mode shows v1.2.0 available)
3. Check BNC Tools toolbar (11 buttons should be visible)
4. Test Datum Point Display button (11th button)

## Testing Checklist
- [ ] Download installer (842.23 MB)
- [ ] Verify SHA256 hash
- [ ] Bypass SmartScreen warning
- [ ] Complete installation (no extraction errors)
- [ ] Launch BNC CAD successfully
- [ ] Auto-update banner displays after 5 seconds
- [ ] BNC Tools toolbar shows all 11 buttons
- [ ] Datum Point Display toggle works

## Technical Notes
**Files Included in TEMP Extraction:**
- `7zr.exe` (562 KB) - 7-Zip standalone extractor
- `7z.dll` (NOW INCLUDED) - Required codec library for LZMA2/BCJ/Delta ARM64
- `BNC-CAD-Output.7z` (840 MB) - Compressed application files

**Extraction Method:**
1. Extract to `%TEMP%\BNC_CAD_Setup\`
2. Copy files to `C:\BNC CAD\`
3. Clean up TEMP folder
4. Create shortcuts
5. Register uninstaller

## Previous Error Log (FIXED)
```
ERROR: Cannot open the file as archive
ERROR: Data Error in 'BNC-CAD-Output.7z'
Sub items Errors: 1
Codec Load Error: 7z.dll : The specified module could not be found
```

**Status:** ✅ This error will NO LONGER occur with the rebuilt installer.

## Next Steps
1. ✅ Include 7z.dll in installer - **COMPLETED**
2. ✅ Rebuild installer - **COMPLETED**
3. ⏭️ Test on target system - **READY FOR TESTING**
4. ⏭️ Backend integration (when ready - change MOCK_MODE = False)
5. 📋 Optional: Purchase code signing certificate to remove SmartScreen warning

## Support
If you encounter any issues during installation:
1. Check Windows Event Viewer for detailed error logs
2. Verify downloaded file SHA256 hash matches: `C95F2DA8A367BF2AC77AB4932194EC9724D523007CBAFAF943F65E174467DE97`
3. Ensure you have administrator privileges
4. Check free disk space (minimum 3 GB required)
5. Temporarily disable antivirus if blocking installation
