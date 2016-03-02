!define PRODUCT_NAME "Salt Minion"
!define PRODUCT_PUBLISHER "SaltStack, Inc"
!define PRODUCT_WEB_SITE "http://saltstack.org"
!define PRODUCT_DIR_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\salt-minion.exe"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define PRODUCT_UNINST_ROOT_KEY "HKLM"

; MUI 1.67 compatible ------
!include "MUI2.nsh"

!include "nsDialogs.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"
!include "StrFunc.nsh"
!include "x64.nsh"
${StrLoc}
${StrStrAdv}

!ifdef SaltVersion
  !define PRODUCT_VERSION "${SaltVersion}"
!else
  !define PRODUCT_VERSION "Undefined Version"
!endif

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
Var StartService

; MUI Settings
!define MUI_ABORTWARNING
!define MUI_ICON "salt.ico"
!define MUI_UNICON "salt.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP "panel.bmp"

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
!define MUI_PAGE_CUSTOMFUNCTION_SHOW FinishPage.Show
!define MUI_FINISHPAGE_RUN "$INSTDIR\nssm"
!define MUI_FINISHPAGE_RUN_PARAMETERS "start salt-minion"
!insertmacro MUI_PAGE_FINISH

; Uninstaller pages
!insertmacro MUI_UNPAGE_INSTFILES

; Language files
!insertmacro MUI_LANGUAGE "English"

; Part of the Trim function for Strings
!define Trim "!insertmacro Trim"
!macro Trim ResultVar String
  Push "${String}"
  Call Trim
  Pop "${ResultVar}"
!macroend

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


Function getMinionConfig

  confFind:
  IfFileExists "$INSTDIR\conf\minion" confFound confNotFound

  confNotFound:
    ${If} $INSTDIR == "c:\salt\bin\Scripts"
      StrCpy $INSTDIR "C:\salt"
      goto confFind
    ${Else}
      goto confReallyNotFound
    ${EndIf}

  confFound:
    FileOpen $0 "$INSTDIR\conf\minion" r

    confLoop:
      FileRead $0 $1
      IfErrors EndOfFile
      ${StrLoc} $2 $1 "master:" ">"
      ${If} $2 == 0
        ${StrStrAdv} $2 $1 "master: " ">" ">" "0" "0" "0"
        ${Trim} $2 $2
          StrCpy $MasterHost_State $2
      ${EndIf}

      ${StrLoc} $2 $1 "id:" ">"
      ${If} $2 == 0
        ${StrStrAdv} $2 $1 "id: " ">" ">" "0" "0" "0"
        ${Trim} $2 $2
        StrCpy $MinionName_State $2
      ${EndIf}

      Goto confLoop

    EndOfFile:
      FileClose $0

  confReallyNotFound:
    Push $R0
    Push $R1
    Push $R2
    ${GetParameters} $R0
    ${GetOptions} $R0 "/master=" $R1
    ${GetOptions} $R0 "/minion-name=" $R2
    ${IfNot} $R1 == ""
      StrCpy $MasterHost_State $R1
    ${ElseIf} $MasterHost_State == ""
      StrCpy $MasterHost_State "salt"
    ${EndIf}
    ${IfNot} $R2 == ""
      StrCpy $MinionName_State $R2
    ${ElseIf} $MinionName_State == ""
      StrCpy $MinionName_State "hostname"
    ${EndIf}
    Pop $R2
    Pop $R1
    Pop $R0

FunctionEnd


Function updateMinionConfig

  ClearErrors
  FileOpen $0 "$INSTDIR\conf\minion" "r"              ; open target file for reading
  GetTempFileName $R0                                 ; get new temp file name
  FileOpen $1 $R0 "w"                                 ; open temp file for writing
  loop:
     FileRead $0 $2                                   ; read line from target file
     IfErrors done
     ${If} $MasterHost_State != ""
     ${AndIf} $MasterHost_State != "salt"             ; check if end of file reached
       StrCmp $2 "#master: salt$\r$\n" 0 +2           ; compare line with search string with CR/LF
          StrCpy $2 "master: $MasterHost_State$\r$\n" ; change line
       StrCmp $2 "#master: salt" 0 +2                 ; compare line with search string without CR/LF (at the end of the file)
          StrCpy $2 "master: $MasterHost_State"       ; change line
     ${EndIf}
     ${If} $MinionName_State != ""
     ${AndIf} $MinionName_State != "hostname"
       StrCmp $2 "#id:$\r$\n" 0 +2                    ; compare line with search string with CR/LF
          StrCpy $2 "id: $MinionName_State$\r$\n"     ; change line
       StrCmp $2 "#id:" 0 +2                          ; compare line with search string without CR/LF (at the end of the file)
          StrCpy $2 "id: $MinionName_State"           ; change line
     ${EndIf}
     FileWrite $1 $2                                  ; write changed or unchanged line to temp file
     Goto loop

  done:
     FileClose $0                                     ; close target file
     FileClose $1                                     ; close temp file
     Delete "$INSTDIR\conf\minion"                    ; delete target file
     CopyFiles /SILENT $R0 "$INSTDIR\conf\minion"     ; copy temp file to target file
     Delete $R0

FunctionEnd


Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "Salt-Minion-${PRODUCT_VERSION}-${CPUARCH}-Setup.exe"
InstallDir "c:\salt"
InstallDirRegKey HKLM "${PRODUCT_DIR_REGKEY}" ""
ShowInstDetails show
ShowUnInstDetails show


Section "MainSection" SEC01

  SetOutPath "$INSTDIR\"
  SetOverwrite off
  CreateDirectory $INSTDIR\conf\pki\minion
  File /r "..\buildenv\"
  Exec 'icacls c:\salt /inheritance:r /grant:r "*S-1-5-32-544":(OI)(CI)F /grant:r "*S-1-5-18":(OI)(CI)F'

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

  ExecWait "nssm.exe install salt-minion $INSTDIR\bin\python.exe $INSTDIR\bin\Scripts\salt-minion -c $INSTDIR\conf -l quiet"
  ExecWait "nssm.exe set salt-minion AppEnvironmentExtra PYTHONHOME="
  RMDir /R "$INSTDIR\var\cache\salt" ; removing cache from old version

  Call updateMinionConfig

  Call checkStartService

SectionEnd


Function FinishPage.Show

  ${IfNot} $StartService == 1
    SendMessage $mui.FinishPage.Run ${BM_SETCHECK} ${BST_UNCHECKED} 0
  ${EndIf}

FunctionEnd


Function checkStartService

    ; Check if the start-service option was passed
    Push $R0
    Push $R1
    ${GetParameters} $R0
    ${GetOptions} $R0 "/start-service=" $R1
    ; If start-service was passed something, then set it
    ${IfNot} $R1 == ""
      StrCpy $StartService $R1
    ; Otherwise default to 1
    ${Else}
      StrCpy $StartService 1
    ${EndIf}
    Pop $R0
    Pop $R1

FunctionEnd


Function .onInstSuccess
  ; If the installer is running Silently, start the service
  IfSilent silentOption notSilent

  silentOption:

    ; If start-service is 1, then start the service
    ${If} $StartService == 1
      Exec 'net start salt-minion'
    ${EndIf}

  notSilent:

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

  Call getMinionConfig

  ; Check for existing installation
  ReadRegStr $R0 HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "UninstallString"
  StrCmp $R0 "" skipUninstall

  ; Found existing installation, prompt to uninstall
  MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION "${PRODUCT_NAME} is already installed. $\n$\nClick `OK` to remove the existing installation." /SD IDOK IDOK uninst
  Abort

  uninst:
    ; Make sure we're in the right directory
    ${If} $INSTDIR == "c:\salt\bin\Scripts"
      StrCpy $INSTDIR "C:\salt"
    ${EndIf}

    ; Stop and remove the salt-minion service
    ExecWait "net stop salt-minion"
    ExecWait "sc delete salt-minion"

    ; Remove salt binaries and batch files
    Delete "$INSTDIR\uninst.exe"
    Delete "$INSTDIR\nssm.exe"
    Delete "$INSTDIR\salt*"
    RMDir /r "$INSTDIR\bin"

    ; Remove registry entries
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}"
    DeleteRegKey HKLM "${PRODUCT_DIR_REGKEY}"

  skipUninstall:

FunctionEnd


Function Trim

    Exch $R1 ; Original string
    Push $R2

  Loop:
    StrCpy $R2 "$R1" 1
    StrCmp "$R2" " " TrimLeft
    StrCmp "$R2" "$\r" TrimLeft
    StrCmp "$R2" "$\n" TrimLeft
    StrCmp "$R2" "$\t" TrimLeft
    GoTo Loop2
  TrimLeft:
    StrCpy $R1 "$R1" "" 1
    Goto Loop

  Loop2:
    StrCpy $R2 "$R1" 1 -1
    StrCmp "$R2" " " TrimRight
    StrCmp "$R2" "$\r" TrimRight
    StrCmp "$R2" "$\n" TrimRight
    StrCmp "$R2" "$\t" TrimRight
    GoTo Done
  TrimRight:
    StrCpy $R1 "$R1" -1
    Goto Loop2

  Done:
    Pop $R2
    Exch $R1

FunctionEnd


Section Uninstall
  ExecWait "net stop salt-minion"
  ExecWait "sc delete salt-minion"
  Delete "$INSTDIR\uninst.exe"
  Delete "$INSTDIR\nssm.exe"
  Delete "$INSTDIR\salt*"
  RMDir /r "$INSTDIR\bin"

  ${If} $INSTDIR != 'Program Files'
  ${AndIf} $INSTDIR != 'Program Files (x86)'
    RMDir /r "$INSTDIR"
  ${EndIf}

  DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}"
  DeleteRegKey HKLM "${PRODUCT_DIR_REGKEY}"
  SetAutoClose true
SectionEnd
