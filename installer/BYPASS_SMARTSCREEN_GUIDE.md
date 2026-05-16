# How to Install BNC CAD (Bypass Windows SmartScreen)

## IMPORTANT: This warning is NORMAL for unsigned software!

---

## Step-by-Step Instructions

### When you see this screen:

```
┌─────────────────────────────────────────┐
│ Windows protected your PC               │
│                                         │
│ Microsoft Defender SmartScreen          │
│ prevented an unrecognized app from      │
│ starting. Running this app might put    │
│ your PC at risk.                        │
│                                         │
│ Application: BNC_CAD.exe                │
│ Publisher: Unknown publisher            │
│                                         │
│            [Don't run]                  │
└─────────────────────────────────────────┘
```

### DO THIS:

**1. Click "More info" link** (bottom left of the blue window)

**2. A new button appears: "Run anyway"**

**3. Click "Run anyway"** 

**4. The installer will start!**

---

## Why This Happens

- **Not digitally signed**: Code signing certificates cost $150-500/year
- **Safe to install**: The warning is only for unsigned files
- **Common for open-source**: Many free/open-source software shows this

---

## Alternative Method

If SmartScreen blocks completely:

1. **Right-click** on `BNC CAD.exe`
2. Select **"Properties"**
3. Check **"Unblock"** at the bottom
4. Click **"Apply"** and **"OK"**
5. **Double-click** to install

---

## Still Having Issues?

**Extraction Error (error 2)?**
- Run as Administrator (right-click → Run as administrator)
- Free up 3GB disk space on C: drive
- Temporarily disable antivirus

**Contact Support:**
- Email: your-support@email.com
- Include: Screenshot, Windows version, error message

---

**SHA256 Hash** (verify file integrity):
```
C718FB00F2C2E627CBBA2BEAC8F98ABE7C1DC03C2F8FA6515A6A4270750F9887
```

To verify:
```powershell
Get-FileHash -Path "BNC CAD.exe" -Algorithm SHA256
```

If the hash **matches**, the file is safe and unmodified.
