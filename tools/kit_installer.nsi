; NSIS script for the iamar developer kit Windows installer.
; Built by tools/build_kit_release.sh when makensis is installed:
;   makensis -DVERSION=<n.n.n> -DSRC=<dir holding the kit folder> -DOUTFILE=<setup.exe> tools/kit_installer.nsi
; Per-user install (no administrator rights): %LOCALAPPDATA%\iamar\kit.
Unicode true
!ifndef VERSION
  !error "pass -DVERSION=n.n.n"
!endif
!ifndef SRC
  !error "pass -DSRC=<dir that contains the kit folder>"
!endif
!ifndef OUTFILE
  !define OUTFILE "iamar-kit-setup.exe"
!endif

Name "iamar developer kit ${VERSION}"
OutFile "${OUTFILE}"
RequestExecutionLevel user
InstallDir "$LOCALAPPDATA\iamar\kit"
SetCompressor /SOLID lzma

Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

; Refuse any existing folder that is not empty and not a previous install of this
; kit (it has our marker iamar-kit.installed, or the old layout: uninstall.exe plus the
; kit's own iamar-world.cmd; uninstall.exe alone is the NSIS default name): the uninstaller removes $INSTDIR recursively, so
; it must only ever remove a folder this installer created.
Function .onVerifyInstDir
  IfFileExists "$INSTDIR\iamar-kit.installed" ok
  IfFileExists "$INSTDIR\uninstall.exe" 0 +2
  IfFileExists "$INSTDIR\iamar-world.cmd" ok
  IfFileExists "$INSTDIR\*.*" 0 ok
  FindFirst $0 $1 "$INSTDIR\*.*"
  loop:
    StrCmp $1 "" done
    StrCmp $1 "." next
    StrCmp $1 ".." next
    FindClose $0
    Abort
  next:
    FindNext $0 $1
    Goto loop
  done:
    FindClose $0
  ok:
FunctionEnd

Section "Install"
  SetOutPath "$INSTDIR"
  File /r "${SRC}\kit\*.*"
  WriteUninstaller "$INSTDIR\uninstall.exe"
  FileOpen $0 "$INSTDIR\iamar-kit.installed" w
  FileWrite $0 "iamar developer kit ${VERSION}$\r$\n"
  FileClose $0
  CreateDirectory "$SMPROGRAMS\iamar"
  CreateShortcut "$SMPROGRAMS\iamar\iamar developer kit.lnk" "$INSTDIR"
  CreateShortcut "$SMPROGRAMS\iamar\Uninstall iamar developer kit.lnk" "$INSTDIR\uninstall.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\iamar-kit" "DisplayName" "iamar developer kit"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\iamar-kit" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\iamar-kit" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\iamar-kit" "NoModify" 1
SectionEnd

Section "Uninstall"
  Delete "$SMPROGRAMS\iamar\iamar developer kit.lnk"
  Delete "$SMPROGRAMS\iamar\Uninstall iamar developer kit.lnk"
  RMDir "$SMPROGRAMS\iamar"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\iamar-kit"
  ; Only a folder carrying the kit marker (or the old kit layout) is ours to remove.
  IfFileExists "$INSTDIR\iamar-kit.installed" remove
  IfFileExists "$INSTDIR\iamar-world.cmd" 0 skip
  IfFileExists "$INSTDIR\uninstall.exe" 0 skip
  remove:
  RMDir /r "$INSTDIR"
  skip:
SectionEnd
