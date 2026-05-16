===============================================
  BNC CAD INSTALLATION - SMARTSCREEN BYPASS
===============================================

IMPORTANT: The Windows warning is NORMAL for unsigned software!

-----------------------------------------------
WHEN YOU SEE "Windows protected your PC":
-----------------------------------------------

1. Click "More info" (bottom left of blue window)
2. Click "Run anyway" button (appears after step 1)
3. Installer will start normally

-----------------------------------------------
WHY THIS WARNING APPEARS:
-----------------------------------------------

- BNC CAD installer is NOT digitally signed
- Code signing certificates cost $150-500/year
- The software is SAFE - warning only for unsigned files
- Common for open-source software

-----------------------------------------------
ALTERNATIVE METHOD (if blocked):
-----------------------------------------------

1. Right-click on "BNC CAD.exe"
2. Select "Properties"
3. Check "Unblock" box at bottom
4. Click "Apply" and "OK"
5. Double-click to install

-----------------------------------------------
EXTRACTION ERROR? TRY THIS:
-----------------------------------------------

1. Right-click installer → "Run as administrator"
2. Free up 3GB space on C: drive
3. Temporarily disable antivirus during install
4. Re-download if file hash doesn't match

-----------------------------------------------
VERIFY FILE INTEGRITY:
-----------------------------------------------

SHA256: C718FB00F2C2E627CBBA2BEAC8F98ABE7C1DC03C2F8FA6515A6A4270750F9887

To check (in PowerShell):
Get-FileHash -Path "BNC CAD.exe" -Algorithm SHA256

If hash matches = file is safe and unmodified

-----------------------------------------------
INSTALLER INFO:
-----------------------------------------------

File: BNC CAD.exe
Size: 840.41 MB
Publisher: BNC Corporation
Product: BNC CAD 1.1
Date: April 18, 2026

-----------------------------------------------
FOR HELP:
-----------------------------------------------

Send email with:
- Screenshot of error
- Windows version
- Error message text

===============================================
