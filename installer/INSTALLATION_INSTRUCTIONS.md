# ANVIL CAD Installation Instructions

## Windows Defender SmartScreen Warning

When you run the ANVIL CAD installer, you may see a **Windows SmartScreen warning** that says:
```
"Windows protected your PC"
"Microsoft Defender SmartScreen prevented an unrecognized app from starting"
Publisher: Unknown publisher
```

**This is NORMAL and EXPECTED** for unsigned installers.

---

## How to Install (Bypass SmartScreen)

### Method 1: Click "More info" and "Run anyway"

1. **Double-click** the installer `ANVIL CAD.exe`
2. **Click "More info"** link in the blue SmartScreen window
3. **Click "Run anyway"** button that appears
4. The installer will start normally

### Method 2: Right-click and "Run as administrator"

1. **Right-click** on `ANVIL CAD.exe`
2. Select **"Run as administrator"**
3. If SmartScreen appears, click **"More info"** → **"Run anyway"**
4. The installer will start with admin privileges

---

## Why This Warning Appears

- ANVIL CAD installer is **not digitally signed** with a code signing certificate
- Code signing certificates cost **$150-500/year**
- The software is **safe** - the warning is only because it's unsigned
- Many open-source and small company software shows this warning

---

## System Requirements

- **Windows 10/11** (64-bit)
- **3 GB free disk space** (for installation)
- **Administrator privileges** (for installation)
- **Internet connection** (for update checks - optional)

---

## Installation Steps

1. **Bypass SmartScreen** (see above)
2. Click **"Next"** to start installation
3. Choose installation folder (default: `C:\Program Files\BNC_CAD`)
4. Wait for extraction (may take **2-5 minutes**)
5. Click **"Finish"** to complete

---

## Troubleshooting

### If extraction fails:

1. **Run as Administrator** (right-click → Run as administrator)
2. **Disable antivirus temporarily** during installation
3. **Free up disk space** (need 3GB free on C: and TEMP drives)
4. **Verify file integrity**: Check SHA256 hash matches the published hash
5. **Re-download installer** if hash doesn't match

### If SmartScreen blocks completely:

1. Go to **Windows Security** → **App & browser control**
2. Click **"Reputation-based protection settings"**
3. Temporarily turn **OFF** "Check apps and files"
4. Install ANVIL CAD
5. Turn protection **back ON** after installation

---

## After Installation

### First Launch
- ANVIL CAD may take **30-60 seconds** to start the first time
- Subsequent launches will be faster

### Update Banner
- After **5 seconds** of launch, an automatic update check runs
- If an update is available, a **blue banner** will appear at the top
- You can also check manually: **BNC menu → Check for Updates** (Ctrl+U)

### Features
- **BNC Tools Toolbar** - 11 custom buttons for quick access
- **Auto Update System** - Checks weekly for new versions
- **Custom BNC Menu** - Access to update features

---

## Contact Support

If you encounter any issues:
- Email: support@bnc-cad.com (example)
- Include: Error message, Windows version, screenshot

---

**Version**: 1.1.0  
**Date**: April 18, 2026  
**Publisher**: BNC Corporation
