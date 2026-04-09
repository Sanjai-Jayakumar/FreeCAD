; NSIS Modern UI installer for BNC CAD 1.1 (custom FreeCAD 1.1 build)

!include "MUI2.nsh"

!define PRODUCT_NAME "BNC CAD"
!define PRODUCT_VERSION "1.1"
!define PRODUCT_PUBLISHER "BNC"
!define INSTALL_ARCHIVE "BNC-CAD-Output.7z"
!define PAYLOAD_EXTRACTOR "7zr.exe"
!define OUTPUT_FILE "BNC CAD.exe"
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
InstallDir "$PROGRAMFILES\BNC_CAD"
InstallDirRegKey HKLM "${PRODUCT_REGKEY}" "InstallLocation"
RequestExecutionLevel admin
SetCompress off
VIProductVersion "1.1.0.0"
VIAddVersionKey "ProductName" "${PRODUCT_NAME}"
VIAddVersionKey "ProductVersion" "${PRODUCT_VERSION}"
VIAddVersionKey "CompanyName" "${PRODUCT_PUBLISHER}"
VIAddVersionKey "FileDescription" "${PRODUCT_NAME} Installer"
VIAddVersionKey "FileVersion" "1.1.0.0"
VIAddVersionKey "LegalCopyright" "(c) 2026 ${PRODUCT_PUBLISHER}"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "English"

Section "${PRODUCT_NAME}" SEC01
  SetShellVarContext all
  SetOutPath "$INSTDIR"
  File "${PAYLOAD_EXTRACTOR}"
  File "${INSTALL_ARCHIVE}"
  File "default_toolbar_layout.json"
  File "BNC_CAD.ico"
  
  SetOutPath "$INSTDIR"
  
  DetailPrint "Extracting application files..."
  nsExec::ExecToLog '"$INSTDIR\7zr.exe" x "$INSTDIR\BNC-CAD-Output.7z" -o"$INSTDIR" -y -aoa'
  Pop $0
  StrCmp $0 "0" +3
    MessageBox MB_ICONSTOP "Extraction failed (error $0)."
    Abort
  Delete "$INSTDIR\7zr.exe"
  Delete "$INSTDIR\BNC-CAD-Output.7z"

  ; Remove old user.cfg so fresh defaults apply (Assembly enabled by default)
  DetailPrint "Resetting workbench settings for fresh install..."
  Delete "$APPDATA\\FreeCAD\\user.cfg"

  WriteRegStr HKLM "${PRODUCT_REGKEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${PRODUCT_REGKEY}" "Version" "${PRODUCT_VERSION}"

  WriteRegStr HKLM "${PRODUCT_UNREG}" "DisplayName" "${PRODUCT_NAME} ${PRODUCT_VERSION}"
  WriteRegStr HKLM "${PRODUCT_UNREG}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKLM "${PRODUCT_UNREG}" "Publisher" "${PRODUCT_PUBLISHER}"
  WriteRegStr HKLM "${PRODUCT_UNREG}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${PRODUCT_UNREG}" "UninstallString" "$INSTDIR\\Uninstall.exe"
  WriteRegDWORD HKLM "${PRODUCT_UNREG}" "NoModify" 1
  WriteRegDWORD HKLM "${PRODUCT_UNREG}" "NoRepair" 1

  CreateDirectory "$SMPROGRAMS\\${PRODUCT_NAME}"
    CreateShortCut "$SMPROGRAMS\\${PRODUCT_NAME}\\${PRODUCT_NAME}.lnk" "$INSTDIR\\bin\\FreeCAD.exe" "" "$INSTDIR\\BNC_CAD.ico"
    CreateShortCut "$DESKTOP\\${PRODUCT_NAME}.lnk" "$INSTDIR\\bin\\FreeCAD.exe" "" "$INSTDIR\\BNC_CAD.ico"

  WriteUninstaller "$INSTDIR\\Uninstall.exe"

  ; Import default toolbar layout for new users
  nsExec::ExecToLog 'powershell -Command "Copy-Item \"$INSTDIR\\default_toolbar_layout.json\" -Destination \"$APPDATA\\FreeCAD\\default_toolbar_layout.json\" -Force"'
  ; You can add a script to read this JSON and update FreeCAD user parameters on first launch
SectionEnd

Section "Uninstall"
  SetShellVarContext all
  
  Delete "$DESKTOP\\${PRODUCT_NAME}.lnk"
  Delete "$SMPROGRAMS\\${PRODUCT_NAME}\\${PRODUCT_NAME}.lnk"
  RMDir "$SMPROGRAMS\\${PRODUCT_NAME}"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKLM "${PRODUCT_UNREG}"
  DeleteRegKey HKLM "${PRODUCT_REGKEY}"

  ; Remove saved BNC CAD auth session (email/login data)
  ; Must switch to current-user context so $APPDATA points to the real user folder
  ; FreeCAD 1.1 stores user data under APPDATA/FreeCAD/v1-1/
  SetShellVarContext current
  Delete "$APPDATA\FreeCAD\v1-1\bnc_auth.json"
  Delete "$APPDATA\FreeCAD\bnc_auth.json"
  SetShellVarContext all
SectionEnd
