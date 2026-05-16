; NSIS Modern UI installer for BNC CAD 1.1 (custom FreeCAD 1.1 build)

!include "MUI2.nsh"

!define PRODUCT_NAME "BNC CAD"
!define PRODUCT_VERSION "1.1.1"
!define PRODUCT_PUBLISHER "BNC Corporation"
!define INSTALL_ARCHIVE "BNC-CAD-Output.7z"
!define PAYLOAD_EXTRACTOR "7zr.exe"
!define OUTPUT_FILE "BNC CAD 1.1.1.exe"
!define PRODUCT_REGKEY "Software\\${PRODUCT_NAME}"
!define PRODUCT_UNREG "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${PRODUCT_NAME}"
!define MUI_ABORTWARNING
!define MUI_ICON "BNC_CAD.ico"
!define MUI_UNICON "BNC_CAD.ico"
!define MUI_FINISHPAGE_NOAUTOCLOSE
!define MUI_FINISHPAGE_RUN "$INSTDIR\bin\FreeCAD.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Launch ${PRODUCT_NAME}"

Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "${OUTPUT_FILE}"
Icon "BNC_CAD.ico"
InstallDir "$LOCALAPPDATA\BNC_CAD"
InstallDirRegKey HKCU "${PRODUCT_REGKEY}" "InstallLocation"
RequestExecutionLevel user
SetCompress off
VIProductVersion "1.1.1.0"
VIAddVersionKey "ProductName" "${PRODUCT_NAME}"
VIAddVersionKey "ProductVersion" "${PRODUCT_VERSION}"
VIAddVersionKey "CompanyName" "${PRODUCT_PUBLISHER}"
VIAddVersionKey "FileDescription" "${PRODUCT_NAME} Installation Package"
VIAddVersionKey "FileVersion" "1.1.1.0"
VIAddVersionKey "LegalCopyright" "(c) 2026 ${PRODUCT_PUBLISHER}"
VIAddVersionKey "OriginalFilename" "${OUTPUT_FILE}"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "English"

Section "${PRODUCT_NAME}" SEC01
  SetShellVarContext current

  ; ── Step 1: stage extractor + archive to a small temp folder ─────────────────
  DetailPrint "Preparing installer files..."
  RMDir /r "$TEMP\BNC_CAD_Setup"
  CreateDirectory "$TEMP\BNC_CAD_Setup"
  SetOutPath "$TEMP\BNC_CAD_Setup"

  File "${PAYLOAD_EXTRACTOR}"
  File "7z.dll"
  File "${INSTALL_ARCHIVE}"

  ; ── Step 2: extract directly to install dir (single pass, no temp copy) ──────
  DetailPrint "Installing BNC CAD to $INSTDIR..."
  DetailPrint "This will take several minutes. Please wait..."
  CreateDirectory "$INSTDIR"

  ; -bso0 suppresses the per-file listing so the UI stays responsive.
  ; -bsp0 suppresses the progress % line (not useful in NSIS log pane).
  nsExec::ExecToLog '"$TEMP\BNC_CAD_Setup\7zr.exe" x "$TEMP\BNC_CAD_Setup\${INSTALL_ARCHIVE}" -o"$INSTDIR" -y -aoa -bso0 -bsp0'
  Pop $0
  StrCmp $0 "0" extract_ok
    MessageBox MB_ICONSTOP "Installation failed (7-Zip error $0).$\r$\n$\r$\nPossible causes:$\r$\n- Insufficient disk space (need ~3.5 GB)$\r$\n- Antivirus blocking extraction$\r$\n$\r$\nSolutions:$\r$\n1. Ensure you are running as Administrator$\r$\n2. Disable antivirus temporarily$\r$\n3. Free up disk space on the install drive"
    RMDir /r "$TEMP\BNC_CAD_Setup"
    Abort
  extract_ok:

  ; ── Step 3: copy small extra files ───────────────────────────────────────────
  DetailPrint "Copying additional files..."
  SetOutPath "$INSTDIR"
  File "default_toolbar_layout.json"
  File "BNC_CAD.ico"

  ; ── Step 4: clean up temp staging folder ─────────────────────────────────────
  DetailPrint "Cleaning up temporary files..."
  RMDir /r "$TEMP\BNC_CAD_Setup"

  ; ── Step 5: clear Python bytecode cache so modules recompile cleanly ─────────
  DetailPrint "Finalising installation..."
  nsExec::ExecToLog 'powershell -WindowStyle Hidden -Command "Get-ChildItem \"$INSTDIR\Mod\" -Filter __pycache__ -Recurse -Directory -EA SilentlyContinue | Remove-Item -Recurse -Force -EA SilentlyContinue"'
  Pop $0

  ; ── Step 6: reset user config and auth cache so fresh defaults apply ──────────
  ; Use PowerShell so $$env:APPDATA always resolves to the real user (not admin profile)
  nsExec::ExecToLog 'powershell -WindowStyle Hidden -Command "Remove-Item \"$$env:APPDATA\FreeCAD\user.cfg\" -ErrorAction SilentlyContinue; Remove-Item \"$$env:APPDATA\FreeCAD\bnc_auth.json\" -ErrorAction SilentlyContinue; Remove-Item \"$$env:APPDATA\FreeCAD\v1-1\bnc_auth.json\" -ErrorAction SilentlyContinue"'
  Pop $0

  ; ── Step 7: registry + shortcuts ─────────────────────────────────────────────
  ; Per-user registry (HKCU) — no admin required, no UAC prompt
  WriteRegStr HKCU "${PRODUCT_REGKEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${PRODUCT_REGKEY}" "Version" "${PRODUCT_VERSION}"

  WriteRegStr HKCU "${PRODUCT_UNREG}" "DisplayName" "${PRODUCT_NAME} ${PRODUCT_VERSION}"
  WriteRegStr HKCU "${PRODUCT_UNREG}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKCU "${PRODUCT_UNREG}" "Publisher" "${PRODUCT_PUBLISHER}"
  WriteRegStr HKCU "${PRODUCT_UNREG}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${PRODUCT_UNREG}" "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteRegDWORD HKCU "${PRODUCT_UNREG}" "NoModify" 1
  WriteRegDWORD HKCU "${PRODUCT_UNREG}" "NoRepair" 1

  CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk" "$INSTDIR\bin\FreeCAD.exe" "" "$INSTDIR\BNC_CAD.ico"
  CreateShortCut "$DESKTOP\${PRODUCT_NAME}.lnk" "$INSTDIR\bin\FreeCAD.exe" "" "$INSTDIR\BNC_CAD.ico"

  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; Copy default toolbar layout for new users
  nsExec::ExecToLog 'powershell -WindowStyle Hidden -Command "Copy-Item \"$INSTDIR\default_toolbar_layout.json\" -Destination \"$APPDATA\FreeCAD\default_toolbar_layout.json\" -Force -EA SilentlyContinue"'
  Pop $0

  ; ── Step 8: register bnccad:// URL protocol handler ──────────────────────────
  ; Per-user registration under HKCU\Software\Classes (no admin needed).
  DetailPrint "Registering bnccad:// protocol handler..."
  WriteRegStr HKCU "Software\Classes\bnccad" "" "URL:BNC CAD"
  WriteRegStr HKCU "Software\Classes\bnccad" "URL Protocol" ""
  WriteRegStr HKCU "Software\Classes\bnccad\DefaultIcon" "" "$INSTDIR\bin\FreeCAD.exe,0"
  WriteRegStr HKCU "Software\Classes\bnccad\shell" "" "open"
  WriteRegStr HKCU "Software\Classes\bnccad\shell\open\command" "" '"$INSTDIR\bin\FreeCAD.exe" "%1"'

  DetailPrint "Installation complete."
SectionEnd

Section "Uninstall"
  SetShellVarContext current

  Delete "$DESKTOP\${PRODUCT_NAME}.lnk"
  Delete "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk"
  RMDir "$SMPROGRAMS\${PRODUCT_NAME}"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKCU "${PRODUCT_UNREG}"
  DeleteRegKey HKCU "${PRODUCT_REGKEY}"
  DeleteRegKey HKCU "Software\Classes\bnccad"

  ; Clear auth session and user config from the real user's AppData
  ; PowerShell ensures $$env:APPDATA resolves correctly even when running as admin
  nsExec::ExecToLog 'powershell -WindowStyle Hidden -Command "Remove-Item \"$$env:APPDATA\FreeCAD\bnc_auth.json\" -ErrorAction SilentlyContinue; Remove-Item \"$$env:APPDATA\FreeCAD\v1-1\bnc_auth.json\" -ErrorAction SilentlyContinue; Remove-Item \"$$env:APPDATA\FreeCAD\user.cfg\" -ErrorAction SilentlyContinue"'
  Pop $0
SectionEnd
