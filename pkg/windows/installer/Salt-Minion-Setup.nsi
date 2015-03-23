!define PRODUCT_NAME "Salt Minion"
!define PRODUCT_VERSION "{{ salt_version }}"
!define PRODUCT_PUBLISHER "SaltStack, Inc"
!define PRODUCT_WEB_SITE "http://saltstack.org"
!define PRODUCT_DIR_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\salt-minion.exe"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define PRODUCT_UNINST_ROOT_KEY "HKLM"

; MUI 1.67 compatible ------
!include "MUI.nsh"

!include "nsDialogs.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"
!include "x64.nsh"

!if "$%PROCESSOR_ARCHITECTURE%" == "AMD64"
  !define CPUARCH "AMD64"
!else if "$%PROCESSOR_ARCHITEW6432%" == "AMD64"
  !define CPUARCH "AMD64"
!else
  !define CPUARCH "x86"
!endif

Var Dialog
Var Label
Var MasterHost
Var MasterHost_State
Var MinionName
Var MinionName_State

; MUI Settings
!define MUI_ABORTWARNING
!define MUI_ICON "salt.ico"
!define MUI_UNICON "salt.ico"

; Welcome page
!insertmacro MUI_PAGE_WELCOME
; License page
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
; Directory page
#!insertmacro MUI_PAGE_DIRECTORY
Page custom nsDialogsPage nsDialogsPageLeave
; Instfiles page
!insertmacro MUI_PAGE_INSTFILES
; Finish page
!define MUI_FINISHPAGE_RUN "sc"
!define MUI_FINISHPAGE_RUN_PARAMETERS "start salt-minion"
!insertmacro MUI_PAGE_FINISH

; Uninstaller pages
!insertmacro MUI_UNPAGE_INSTFILES

; Language files
!insertmacro MUI_LANGUAGE "English"

; MUI end ------

Function nsDialogsPage
  nsDialogs::Create 1018
  Pop $Dialog

  ${If} $Dialog == error
    Abort
  ${EndIf}

  ${NSD_CreateLabel} 0 0 100% 12u "Master IP or Hostname:"
  Pop $Label

  ${NSD_CreateText} 0 13u 100% 12u $MasterHost_State
  Pop $MasterHost

  ${NSD_CreateLabel} 0 30u 100% 12u "Minion Name:"
  Pop $Label

  ${NSD_CreateText} 0 43u 100% 12u $MinionName_State
  Pop $MinionName

  nsDialogs::Show

FunctionEnd

Function nsDialogsPageLeave

  ${NSD_GetText} $MasterHost $MasterHost_State
  #MessageBox MB_OK "Master Hostname is:$\n$\n$MasterHost_State"
  ${NSD_GetText} $MinionName $MinionName_State
  #MessageBox MB_OK "Minion name is:$\n$\n$MinionName_State"

FunctionEnd

Function updateMinionConfig

  ClearErrors
  FileOpen $0 "$INSTDIR\conf\minion" "r"                     ; open target file for reading
  GetTempFileName $R0                           ; get new temp file name
  FileOpen $1 $R0 "w"                            ; open temp file for writing
  loop:
     FileRead $0 $2                              ; read line from target file
     IfErrors done
     ${If} $MasterHost_State != ""
     ${AndIf} $MasterHost_State != "salt"                                ; check if end of file reached
       StrCmp $2 "#master: salt$\r$\n" 0 +2      ; compare line with search string with CR/LF
          StrCpy $2 "master: $MasterHost_State$\r$\n"    ; change line
       StrCmp $2 "#master: salt" 0 +2            ; compare line with search string without CR/LF (at the end of the file)
          StrCpy $2 "master: $MasterHost_State"          ; change line
     ${EndIf}
     ${If} $MinionName_State != ""
     ${AndIf} $MinionName_State != "hostname"
       StrCmp $2 "#id:$\r$\n" 0 +2      ; compare line with search string with CR/LF
          StrCpy $2 "id: $MinionName_State$\r$\n"    ; change line
       StrCmp $2 "#id:" 0 +2            ; compare line with search string without CR/LF (at the end of the file)
          StrCpy $2 "id: $MinionName_State"          ; change line
     ${EndIf}
     FileWrite $1 $2                             ; write changed or unchanged line to temp file
     Goto loop

  done:
     FileClose $0                                ; close target file
     FileClose $1                                ; close temp file
     Delete "$INSTDIR\conf\minion"                           ; delete target file
     CopyFiles /SILENT $R0 "$INSTDIR\conf\minion"            ; copy temp file to target file
     Delete $R0

FunctionEnd

Function MsiQueryProductState

  !define INSTALLSTATE_DEFAULT "5"
  Var /GLOBAL NeedVcRedist                       ; used as a return value

  Pop $R0
  StrCpy $NeedVcRedist "False"
  System::Call "msi::MsiQueryProductStateA(t '$R0') i.r0"
  StrCmp $0 ${INSTALLSTATE_DEFAULT} +2 0
  StrCpy $NeedVcRedist "True"

FunctionEnd

Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "Salt-Minion-${PRODUCT_VERSION}-${CPUARCH}-Setup.exe"
InstallDir "c:\salt"
InstallDirRegKey HKLM "${PRODUCT_DIR_REGKEY}" ""
ShowInstDetails show
ShowUnInstDetails show

; Check and install Visual C++ 2008 SP1 MFC Security Update redist packages
; See http://blogs.msdn.com/b/astebner/archive/2009/01/29/9384143.aspx for more info
Section -Prerequisites

;  !define VC_REDIST_X64_GUID "{5FCE6D76-F5DC-37AB-B2B8-22AB8CEDB1D4}"
;  !define VC_REDIST_X86_GUID "{9BE518E6-ECC6-35A9-88E4-87755C07200F}"
;  !define VC_REDIST_X64_URI "http://download.microsoft.com/download/5/D/8/5D8C65CB-C849-4025-8E95-C3966CAFD8AE/vcredist_x64.exe"
;  !define VC_REDIST_X86_URI "http://download.microsoft.com/download/5/D/8/5D8C65CB-C849-4025-8E95-C3966CAFD8AE/vcredist_x86.exe"

;  Var /GLOBAL VcRedistGuid
;  Var /GLOBAL VcRedistUri
;  ${If} ${RunningX64}
;    StrCpy $VcRedistGuid ${VC_REDIST_X64_GUID}
;    StrCpy $VcRedistUri  ${VC_REDIST_X64_URI}
;  ${Else}
;    StrCpy $VcRedistGuid ${VC_REDIST_X86_GUID}
;    StrCpy $VcRedistUri  ${VC_REDIST_X86_URI}
;  ${EndIf}

;  Push $VcRedistGuid
  Call MsiQueryProductState
;  ${If} $NeedVcRedist == "True"
;    NSISdl::download /TIMEOUT=30000 $VcRedistUri $TEMP\vcredist.exe
;    Pop $R0
;    StrCmp $R0 "success" +2
;      MessageBox MB_OK "VC redist package download failed: $R0" /SD IDOK    ; just report, do not break installation
;    Execwait '"$TEMP\vcredist.exe" /q'
;  ${EndIf}

SectionEnd

Section "MainSection" SEC01

  ExecWait "net stop salt-minion" ;stopping service before upgrading
  Sleep 3000
  SetOutPath "$INSTDIR\"
  SetOverwrite try
  CreateDirectory $INSTDIR\conf\pki\minion
  File /r "..\buildenv\"
  Exec 'icacls c:\salt /inheritance:r /grant:r "BUILTIN\Administrators":(OI)(CI)F /grant:r "NT AUTHORITY\SYSTEM":(OI)(CI)F'

SectionEnd

Section -Post
  WriteUninstaller "$INSTDIR\uninst.exe"
  WriteRegStr HKLM "${PRODUCT_DIR_REGKEY}" "" "$INSTDIR\bin\Scripts\salt-minion.exe"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayName" "$(^Name)"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\uninst.exe"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayIcon" "$INSTDIR\salt.ico"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
  WriteRegStr HKLM "SYSTEM\CurrentControlSet\services\salt-minion" "DependOnService" "nsi"
  Call updateMinionConfig
SectionEnd

Function .onInstSuccess
  Exec "nssm.exe install salt-minion $INSTDIR\bin\python.exe $INSTDIR\bin\Scripts\salt-minion -c $INSTDIR\conf -l quiet"
  RMDir /R "$INSTDIR\var\cache\salt" ; removing cache from old version
  ExecWait "net start salt-minion"
FunctionEnd

Function un.onUninstSuccess
  HideWindow
  MessageBox MB_ICONINFORMATION|MB_OK "$(^Name) was successfully removed from your computer." /SD IDOK
FunctionEnd

Function un.onInit
  MessageBox MB_ICONQUESTION|MB_YESNO|MB_DEFBUTTON2 "Are you sure you want to completely remove $(^Name) and all of its components?" /SD IDYES IDYES +2
  Abort
FunctionEnd

Function .onInit
  Push $R0
  Push $R1
  Push $R2
  ${GetParameters} $R0
  ${GetOptions} $R0 "/master=" $R1
  ${GetOptions} $R0 "/minion-name=" $R2
  ${If} $R1 == ""
    StrCpy $MasterHost_State "salt"
  ${Else}
    StrCpy $MasterHost_State $R1
  ${EndIf}
  ${If} $R2 == ""
    StrCpy $MinionName_State "hostname"
  ${Else}
    StrCpy $MinionName_State $R2
  ${EndIf}
  Pop $R2
  Pop $R1
  Pop $R0
FunctionEnd

Section Uninstall
  ExecWait "net stop salt-minion"
  ExecWait "sc delete salt-minion"
  Delete "$INSTDIR\uninst.exe"
  Delete "$INSTDIR\nssm.exe"
  Delete "$INSTDIR\salt*"
  Delete "$INSTDIR\bin"

  #Delete "$SMPROGRAMS\Salt Minion\Uninstall.lnk"
  #RMDir /r "$SMPROGRAMS\Salt Minion"
  ${If} $INSTDIR != 'Program Files'
  ${AndIf} $INSTDIR != 'Program Files (x86)'
    RMDir /r "$INSTDIR"
  ${EndIf}


  DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}"
  DeleteRegKey HKLM "${PRODUCT_DIR_REGKEY}"
  SetAutoClose true
SectionEnd
