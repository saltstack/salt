!define PRODUCT_NAME "Salt Minion"
!define PRODUCT_NAME_OTHER "Salt"
!define PRODUCT_PUBLISHER "SaltStack, Inc"
!define PRODUCT_WEB_SITE "http://saltstack.org"
!define PRODUCT_CALL_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\salt-call.exe"
!define PRODUCT_CP_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\salt-cp.exe"
!define PRODUCT_KEY_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\salt-key.exe"
!define PRODUCT_MASTER_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\salt-master.exe"
!define PRODUCT_MINION_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\salt-minion.exe"
!define PRODUCT_RUN_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\salt-run.exe"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define PRODUCT_UNINST_KEY_OTHER "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME_OTHER}"
!define PRODUCT_UNINST_ROOT_KEY "HKLM"

# Import Libraries
!include "MUI2.nsh"
!include "nsDialogs.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"
!include "StrFunc.nsh"
!include "x64.nsh"
!include "WinMessages.nsh"
!include "WinVer.nsh"
${StrLoc}
${StrStrAdv}

!ifdef SaltVersion
    !define PRODUCT_VERSION "${SaltVersion}"
!else
    !define PRODUCT_VERSION "Undefined Version"
!endif

!ifdef PythonVersion
    !define PYTHON_VERSION "${PythonVersion}"
!else
    !define PYTHON_VERSION "2"
!endif

!if "$%PROCESSOR_ARCHITECTURE%" == "AMD64"
    !define CPUARCH "AMD64"
!else if "$%PROCESSOR_ARCHITEW6432%" == "AMD64"
    !define CPUARCH "AMD64"
!else
    !define CPUARCH "x86"
!endif

; Part of the Trim function for Strings
!define Trim "!insertmacro Trim"
!macro Trim ResultVar String
    Push "${String}"
    Call Trim
    Pop "${ResultVar}"
!macroend


###############################################################################
# Configure Pages, Ordering, and Configuration
###############################################################################
!define MUI_ABORTWARNING
!define MUI_ICON "salt.ico"
!define MUI_UNICON "salt.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP "panel.bmp"

; Welcome page
!insertmacro MUI_PAGE_WELCOME

; License page
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"

; Configure Minion page
Page custom pageMinionConfig pageMinionConfig_Leave

; Instfiles page
!insertmacro MUI_PAGE_INSTFILES

; Finish page (Customized)
!define MUI_PAGE_CUSTOMFUNCTION_SHOW pageFinish_Show
!define MUI_PAGE_CUSTOMFUNCTION_LEAVE pageFinish_Leave
!insertmacro MUI_PAGE_FINISH

; Uninstaller pages
!insertmacro MUI_UNPAGE_INSTFILES

; Language files
!insertmacro MUI_LANGUAGE "English"


###############################################################################
# Custom Dialog Box Variables
###############################################################################
Var Dialog
Var Label
Var CheckBox_Minion_Start
Var CheckBox_Minion_Start_Delayed
Var MasterHost
Var MasterHost_State
Var MinionName
Var MinionName_State
Var StartMinion
Var StartMinionDelayed
Var DeleteInstallDir


###############################################################################
# Minion Settings Dialog Box
###############################################################################
Function pageMinionConfig

    # Set Page Title and Description
    !insertmacro MUI_HEADER_TEXT "Minion Settings" "Set the Minion Master and ID"
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


Function pageMinionConfig_Leave

    ${NSD_GetText} $MasterHost $MasterHost_State
    ${NSD_GetText} $MinionName $MinionName_State

FunctionEnd


###############################################################################
# Custom Finish Page
###############################################################################
Function pageFinish_Show

    # Imports so the checkboxes will show up
    !define SWP_NOSIZE 0x0001
    !define SWP_NOMOVE 0x0002
    !define HWND_TOP 0x0000

    # Create Start Minion Checkbox
    ${NSD_CreateCheckbox} 120u 90u 100% 12u "&Start salt-minion"
    Pop $CheckBox_Minion_Start
    SetCtlColors $CheckBox_Minion_Start "" "ffffff"
    # This command required to bring the checkbox to the front
    System::Call "User32::SetWindowPos(i, i, i, i, i, i, i) b ($CheckBox_Minion_Start, ${HWND_TOP}, 0, 0, 0, 0, ${SWP_NOSIZE}|${SWP_NOMOVE})"

    # Create Start Minion Delayed ComboBox
    ${NSD_CreateCheckbox} 130u 102u 100% 12u "&Delayed Start"
    Pop $CheckBox_Minion_Start_Delayed
    SetCtlColors $CheckBox_Minion_Start_Delayed "" "ffffff"
    # This command required to bring the checkbox to the front
    System::Call "User32::SetWindowPos(i, i, i, i, i, i, i) b ($CheckBox_Minion_Start_Delayed, ${HWND_TOP}, 0, 0, 0, 0, ${SWP_NOSIZE}|${SWP_NOMOVE})"

    # Load current settings for Minion
    ${If} $StartMinion == 1
        ${NSD_Check} $CheckBox_Minion_Start
    ${EndIf}

    # Load current settings for Minion Delayed
    ${If} $StartMinionDelayed == 1
        ${NSD_Check} $CheckBox_Minion_Start_Delayed
    ${EndIf}

FunctionEnd


Function pageFinish_Leave

    # Assign the current checkbox states
    ${NSD_GetState} $CheckBox_Minion_Start $StartMinion
    ${NSD_GetState} $CheckBox_Minion_Start_Delayed $StartMinionDelayed

FunctionEnd


###############################################################################
# Installation Settings
###############################################################################
!if ${PYTHON_VERSION} == 3
    Name "${PRODUCT_NAME} ${PRODUCT_VERSION} (Python ${PYTHON_VERSION})"
!else
    Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
!endif
OutFile "Salt-Minion-${PRODUCT_VERSION}-Py${PYTHON_VERSION}-${CPUARCH}-Setup.exe"
InstallDir "c:\salt"
InstallDirRegKey HKLM "${PRODUCT_DIR_REGKEY}" ""
ShowInstDetails show
ShowUnInstDetails show


; Check and install Visual C++ redist packages
; See http://blogs.msdn.com/b/astebner/archive/2009/01/29/9384143.aspx for more info
Section -Prerequisites

    Var /GLOBAL VcRedistName
    Var /GLOBAL VcRedistGuid
    Var /GLOBAL NeedVcRedist
    Var /Global CheckVcRedist
    StrCpy $CheckVcRedist "False"

    ; Visual C++ 2015 redist packages
    !define PY3_VC_REDIST_NAME "VC_Redist_2015"
    !define PY3_VC_REDIST_X64_GUID "{50A2BC33-C9CD-3BF1-A8FF-53C10A0B183C}"
    !define PY3_VC_REDIST_X86_GUID "{BBF2AC74-720C-3CB3-8291-5E34039232FA}"

    ; Visual C++ 2008 SP1 MFC Security Update redist packages
    !define PY2_VC_REDIST_NAME "VC_Redist_2008_SP1_MFC"
    !define PY2_VC_REDIST_X64_GUID "{5FCE6D76-F5DC-37AB-B2B8-22AB8CEDB1D4}"
    !define PY2_VC_REDIST_X86_GUID "{9BE518E6-ECC6-35A9-88E4-87755C07200F}"

    ${If} ${PYTHON_VERSION} == 3
        StrCpy $VcRedistName ${PY3_VC_REDIST_NAME}
        ${If} ${CPUARCH} == "AMD64"
            StrCpy $VcRedistGuid ${PY3_VC_REDIST_X64_GUID}
        ${Else}
            StrCpy $VcRedistGuid ${PY3_VC_REDIST_X86_GUID}
        ${EndIf}
        StrCpy $CheckVcRedist "True"

    ${Else}

        StrCpy $VcRedistName ${PY2_VC_REDIST_NAME}
        ${If} ${CPUARCH} == "AMD64"
            StrCpy $VcRedistGuid ${PY2_VC_REDIST_X64_GUID}
        ${Else}
            StrCpy $VcRedistGuid ${PY2_VC_REDIST_X86_GUID}
        ${EndIf}

        ; VCRedist 2008 only needed on Windows Server 2008R2/Windows 7 and below
        ${If} ${AtMostWin2008R2}
            StrCpy $CheckVcRedist "True"
        ${EndIf}

    ${EndIf}

    ${If} $CheckVcRedist == "True"

        Push $VcRedistGuid
        Call MsiQueryProductState
        ${If} $NeedVcRedist == "True"
            MessageBox MB_ICONQUESTION|MB_YESNO|MB_DEFBUTTON2 \
                "$VcRedistName is currently not installed. Would you like to install?" \
                /SD IDYES IDNO endVcRedist

            ClearErrors
            ; The Correct version of VCRedist is copied over by "build_pkg.bat"
            SetOutPath "$INSTDIR\"
            File "..\prereqs\vcredist.exe"
            ; /passive used by 2015 installer
            ; /qb! used by 2008 installer
            ; It just ignores the unrecognized switches...
            ExecWait "$INSTDIR\vcredist.exe /qb! /passive"
            IfErrors 0 endVcRedist
                MessageBox MB_OK \
                    "$VcRedistName failed to install. Try installing the package manually." \
                    /SD IDOK

            endVcRedist:
        ${EndIf}

    ${EndIf}

SectionEnd


Section "MainSection" SEC01

    SetOutPath "$INSTDIR\"
    SetOverwrite off
    CreateDirectory $INSTDIR\conf\pki\minion
    CreateDirectory $INSTDIR\conf\minion.d
    File /r "..\buildenv\"
    nsExec::Exec 'icacls c:\salt /inheritance:r /grant:r "*S-1-5-32-544":(OI)(CI)F /grant:r "*S-1-5-18":(OI)(CI)F'

SectionEnd


Function .onInit

    Call getMinionConfig

    Call parseCommandLineSwitches

    ; Check for existing installation
    ReadRegStr $R0 HKLM \
        "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
        "UninstallString"
    StrCmp $R0 "" checkOther
    ; Found existing installation, prompt to uninstall
    MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION \
        "${PRODUCT_NAME} is already installed.$\n$\n\
        Click `OK` to remove the existing installation." \
        /SD IDOK IDOK uninst
    Abort

    checkOther:
        ; Check for existing installation of full salt
        ReadRegStr $R0 HKLM \
            "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME_OTHER}" \
            "UninstallString"
        StrCmp $R0 "" skipUninstall
        ; Found existing installation, prompt to uninstall
        MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION \
            "${PRODUCT_NAME_OTHER} is already installed.$\n$\n\
            Click `OK` to remove the existing installation." \
            /SD IDOK IDOK uninst
        Abort

    uninst:

        ; Get current Silent status
        StrCpy $R0 0
        ${If} ${Silent}
            StrCpy $R0 1
        ${EndIf}

        ; Turn on Silent mode
        SetSilent silent

        ; Don't remove all directories
        StrCpy $DeleteInstallDir 0

        ; Uninstall silently
        Call uninstallSalt

        ; Set it back to Normal mode, if that's what it was before
        ${If} $R0 == 0
            SetSilent normal
        ${EndIf}

    skipUninstall:

FunctionEnd


Section -Post

    WriteUninstaller "$INSTDIR\uninst.exe"

    ; Uninstall Registry Entries
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" \
        "DisplayName" "$(^Name)"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" \
        "UninstallString" "$INSTDIR\uninst.exe"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" \
        "DisplayIcon" "$INSTDIR\salt.ico"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" \
        "DisplayVersion" "${PRODUCT_VERSION}"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" \
        "URLInfoAbout" "${PRODUCT_WEB_SITE}"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" \
        "Publisher" "${PRODUCT_PUBLISHER}"
    WriteRegStr HKLM "SYSTEM\CurrentControlSet\services\salt-minion" \
        "DependOnService" "nsi"

    ; Set the estimated size
    ${GetSize} "$INSTDIR\bin" "/S=OK" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" \
        "EstimatedSize" "$0"

    ; Commandline Registry Entries
    WriteRegStr HKLM "${PRODUCT_CALL_REGKEY}" "" "$INSTDIR\salt-call.bat"
    WriteRegStr HKLM "${PRODUCT_CALL_REGKEY}" "Path" "$INSTDIR\bin\"
    WriteRegStr HKLM "${PRODUCT_MINION_REGKEY}" "" "$INSTDIR\salt-minion.bat"
    WriteRegStr HKLM "${PRODUCT_MINION_REGKEY}" "Path" "$INSTDIR\bin\"

    ; Register the Salt-Minion Service
    nsExec::Exec "nssm.exe install salt-minion $INSTDIR\bin\python.exe $INSTDIR\bin\Scripts\salt-minion -c $INSTDIR\conf -l quiet"
    nsExec::Exec "nssm.exe set salt-minion AppEnvironmentExtra PYTHONHOME="
    nsExec::Exec "nssm.exe set salt-minion Description Salt Minion from saltstack.com"
    nsExec::Exec "nssm.exe set salt-minion Start SERVICE_AUTO_START"
    nsExec::Exec "nssm.exe set salt-minion AppNoConsole 1"

    RMDir /R "$INSTDIR\var\cache\salt" ; removing cache from old version

    Call updateMinionConfig

    Push "C:\salt"
    Call AddToPath

    Delete "$INSTDIR\vcredist.exe"

SectionEnd


Function .onInstSuccess

    ; If StartMinionDelayed is 1, then set the service to start delayed
    ${If} $StartMinionDelayed == 1
        nsExec::Exec "nssm.exe set salt-minion Start SERVICE_DELAYED_AUTO_START"
    ${EndIf}

    ; If start-minion is 1, then start the service
    ${If} $StartMinion == 1
        nsExec::Exec 'net start salt-minion'
    ${EndIf}

FunctionEnd


Function un.onInit

    ; Load the parameters
    ${GetParameters} $R0

    # Uninstaller: Remove Installation Directory
    ${GetOptions} $R0 "/delete-install-dir" $R1
    IfErrors delete_install_dir_not_found
        StrCpy $DeleteInstallDir 1
    delete_install_dir_not_found:

    MessageBox MB_ICONQUESTION|MB_YESNO|MB_DEFBUTTON2 \
        "Are you sure you want to completely remove $(^Name) and all of its components?" \
        /SD IDYES IDYES +2
    Abort

FunctionEnd


Section Uninstall

    Call un.uninstallSalt

    ; Remove C:\salt from the Path
    Push "C:\salt"
    Call un.RemoveFromPath

SectionEnd


!macro uninstallSalt un
Function ${un}uninstallSalt

    ; Make sure we're in the right directory
    ${If} $INSTDIR == "c:\salt\bin\Scripts"
      StrCpy $INSTDIR "C:\salt"
    ${EndIf}

    ; Stop and Remove salt-minion service
    nsExec::Exec 'net stop salt-minion'
    nsExec::Exec 'sc delete salt-minion'

    ; Stop and remove the salt-master service
    nsExec::Exec 'net stop salt-master'
    nsExec::Exec 'sc delete salt-master'

    ; Remove files
    Delete "$INSTDIR\uninst.exe"
    Delete "$INSTDIR\nssm.exe"
    Delete "$INSTDIR\salt*"
    Delete "$INSTDIR\vcredist.exe"
    RMDir /r "$INSTDIR\bin"

    ; Remove Registry entries
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}"
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY_OTHER}"
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_CALL_REGKEY}"
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_CP_REGKEY}"
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_KEY_REGKEY}"
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_MASTER_REGKEY}"
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_MINION_REGKEY}"
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_RUN_REGKEY}"

    ; Automatically close when finished
    SetAutoClose true

    ; Prompt to remove the Installation directory
    ${IfNot} $DeleteInstallDir == 1
        MessageBox MB_ICONQUESTION|MB_YESNO|MB_DEFBUTTON2 \
            "Would you like to completely remove $INSTDIR and all of its contents?" \
            /SD IDNO IDNO finished
    ${EndIf}

    ; Make sure you're not removing Program Files
    ${If} $INSTDIR != 'Program Files'
    ${AndIf} $INSTDIR != 'Program Files (x86)'
        RMDir /r "$INSTDIR"
    ${EndIf}

    finished:

FunctionEnd
!macroend


!insertmacro uninstallSalt ""
!insertmacro uninstallSalt "un."


Function un.onUninstSuccess
    HideWindow
    MessageBox MB_ICONINFORMATION|MB_OK \
        "$(^Name) was successfully removed from your computer." \
        /SD IDOK
FunctionEnd


###############################################################################
# Helper Functions
###############################################################################
Function MsiQueryProductState

  !define INSTALLSTATE_DEFAULT "5"

  Pop $R0
  StrCpy $NeedVcRedist "False"
  System::Call "msi::MsiQueryProductStateA(t '$R0') i.r0"
  StrCmp $0 ${INSTALLSTATE_DEFAULT} +2 0
  StrCpy $NeedVcRedist "True"

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


;------------------------------------------------------------------------------
; StrStr Function
; - find substring in a string
;
; Usage:
;   Push "this is some string"
;   Push "some"
;   Call StrStr
;   Pop $0 ; "some string"
;------------------------------------------------------------------------------
!macro StrStr un
Function ${un}StrStr

    Exch $R1 ; $R1=substring, stack=[old$R1,string,...]
    Exch     ;                stack=[string,old$R1,...]
    Exch $R2 ; $R2=string,    stack=[old$R2,old$R1,...]
    Push $R3 ; $R3=strlen(substring)
    Push $R4 ; $R4=count
    Push $R5 ; $R5=tmp
    StrLen $R3 $R1 ; Get the length of the Search String
    StrCpy $R4 0 ; Set the counter to 0

    loop:
        StrCpy $R5 $R2 $R3 $R4 ; Create a moving window of the string that is
                               ; the size of the length of the search string
        StrCmp $R5 $R1 done    ; Is the contents of the window the same as
                               ; search string, then done
        StrCmp $R5 "" done     ; Is the window empty, then done
        IntOp $R4 $R4 + 1      ; Shift the windows one character
        Goto loop              ; Repeat

    done:
        StrCpy $R1 $R2 "" $R4
        Pop $R5
        Pop $R4
        Pop $R3
        Pop $R2
        Exch $R1 ; $R1=old$R1, stack=[result,...]

FunctionEnd
!macroend
!insertmacro StrStr ""
!insertmacro StrStr "un."


;------------------------------------------------------------------------------
; AddToPath Function
; - Adds item to Path for All Users
; - Overcomes NSIS ReadRegStr limitation of 1024 characters by using Native
;   Windows Commands
;
; Usage:
;   Push "C:\path\to\add"
;   Call AddToPath
;------------------------------------------------------------------------------
!define Environ 'HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"'
Function AddToPath

    Exch $0 ; Path to add
    Push $1 ; Current Path
    Push $2 ; Results of StrStr / Length of Path + Path to Add
    Push $3 ; Handle to Reg / Length of Path
    Push $4 ; Result of Registry Call

    ; Open a handle to the key in the registry, handle in $3, Error in $4
    System::Call "advapi32::RegOpenKey(i 0x80000002, t'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', *i.r3) i.r4"
    ; Make sure registry handle opened successfully (returned 0)
    IntCmp $4 0 0 done done

    ; Load the contents of path into $1, Error Code into $4, Path length into $2
    System::Call "advapi32::RegQueryValueEx(i $3, t'PATH', i 0, i 0, t.r1, *i ${NSIS_MAX_STRLEN} r2) i.r4"

    ; Close the handle to the registry ($3)
    System::Call "advapi32::RegCloseKey(i $3)"

    ; Check for Error Code 234, Path too long for the variable
    IntCmp $4 234 0 +4 +4 ; $4 == ERROR_MORE_DATA
        DetailPrint "AddToPath: original length $2 > ${NSIS_MAX_STRLEN}"
        MessageBox MB_OK "PATH not updated, original length $2 > ${NSIS_MAX_STRLEN}"
        Goto done

    ; If no error, continue
    IntCmp $4 0 +5 ; $4 != NO_ERROR
        ; Error 2 means the Key was not found
        IntCmp $4 2 +3 ; $4 != ERROR_FILE_NOT_FOUND
            DetailPrint "AddToPath: unexpected error code $4"
            Goto done
        StrCpy $1 ""

    ; Check if already in PATH
    Push "$1;"          ; The string to search
    Push "$0;"          ; The string to find
    Call StrStr
    Pop $2              ; The result of the search
    StrCmp $2 "" 0 done ; String not found, try again with ';' at the end
                        ; Otherwise, it's already in the path
    Push "$1;"          ; The string to search
    Push "$0\;"         ; The string to find
    Call StrStr
    Pop $2              ; The result
    StrCmp $2 "" 0 done ; String not found, continue (add)
                        ; Otherwise, it's already in the path

    ; Prevent NSIS string overflow
    StrLen $2 $0        ; Length of path to add ($2)
    StrLen $3 $1        ; Length of current path ($3)
    IntOp $2 $2 + $3    ; Length of current path + path to add ($2)
    IntOp $2 $2 + 2     ; Account for the additional ';'
                        ; $2 = strlen(dir) + strlen(PATH) + sizeof(";")

    ; Make sure the new length isn't over the NSIS_MAX_STRLEN
    IntCmp $2 ${NSIS_MAX_STRLEN} +4 +4 0
        DetailPrint "AddToPath: new length $2 > ${NSIS_MAX_STRLEN}"
        MessageBox MB_OK "PATH not updated, new length $2 > ${NSIS_MAX_STRLEN}."
        Goto done

    ; Append dir to PATH
    DetailPrint "Add to PATH: $0"
    StrCpy $2 $1 1 -1       ; Copy the last character of the existing path
    StrCmp $2 ";" 0 +2      ; Check for trailing ';'
        StrCpy $1 $1 -1     ; remove trailing ';'
    StrCmp $1 "" +2         ; Make sure Path is not empty
        StrCpy $0 "$1;$0"   ; Append new path at the end ($0)

    ; We can use the NSIS command here. Only 'ReadRegStr' is affected
    WriteRegExpandStr ${Environ} "PATH" $0

    ; Broadcast registry change to open programs
    SendMessage ${HWND_BROADCAST} ${WM_WININICHANGE} 0 "STR:Environment" /TIMEOUT=5000

    done:
        Pop $4
        Pop $3
        Pop $2
        Pop $1
        Pop $0

FunctionEnd


;------------------------------------------------------------------------------
; RemoveFromPath Function
; - Removes item from Path for All Users
; - Overcomes NSIS ReadRegStr limitation of 1024 characters by using Native
;   Windows Commands
;
; Usage:
;   Push "C:\path\to\add"
;   Call un.RemoveFromPath
;------------------------------------------------------------------------------
Function un.RemoveFromPath

    Exch $0
    Push $1
    Push $2
    Push $3
    Push $4
    Push $5
    Push $6

    ; Open a handle to the key in the registry, handle in $3, Error in $4
    System::Call "advapi32::RegOpenKey(i 0x80000002, t'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', *i.r3) i.r4"
    ; Make sure registry handle opened successfully (returned 0)
    IntCmp $4 0 0 done done

    ; Load the contents of path into $1, Error Code into $4, Path length into $2
    System::Call "advapi32::RegQueryValueEx(i $3, t'PATH', i 0, i 0, t.r1, *i ${NSIS_MAX_STRLEN} r2) i.r4"

    ; Close the handle to the registry ($3)
    System::Call "advapi32::RegCloseKey(i $3)"

    ; Check for Error Code 234, Path too long for the variable
    IntCmp $4 234 0 +4 +4 ; $4 == ERROR_MORE_DATA
        DetailPrint "AddToPath: original length $2 > ${NSIS_MAX_STRLEN}"
        MessageBox MB_OK "PATH not updated, original length $2 > ${NSIS_MAX_STRLEN}"
        Goto done

    ; If no error, continue
    IntCmp $4 0 +5 ; $4 != NO_ERROR
        ; Error 2 means the Key was not found
        IntCmp $4 2 +3 ; $4 != ERROR_FILE_NOT_FOUND
            DetailPrint "AddToPath: unexpected error code $4"
            Goto done
        StrCpy $1 ""

    ; Ensure there's a trailing ';'
    StrCpy $5 $1 1 -1   ; Copy the last character of the path
    StrCmp $5 ";" +2    ; Check for trailing ';', if found continue
        StrCpy $1 "$1;" ; ensure trailing ';'

    ; Check for our directory inside the path
    Push $1             ; String to Search
    Push "$0;"          ; Dir to Find
    Call un.StrStr
    Pop $2              ; The results of the search
    StrCmp $2 "" done   ; If results are empty, we're done, otherwise continue

    ; Remove our Directory from the Path
    DetailPrint "Remove from PATH: $0"
    StrLen $3 "$0;"       ; Get the length of our dir ($3)
    StrLen $4 $2          ; Get the length of the return from StrStr ($4)
    StrCpy $5 $1 -$4      ; $5 is now the part before the path to remove
    StrCpy $6 $2 "" $3    ; $6 is now the part after the path to remove
    StrCpy $3 "$5$6"      ; Combine $5 and $6

    ; Check for Trailing ';'
    StrCpy $5 $3 1 -1     ; Load the last character of the string
    StrCmp $5 ";" 0 +2    ; Check for ';'
        StrCpy $3 $3 -1     ; remove trailing ';'

    ; Write the new path to the registry
    WriteRegExpandStr ${Environ} "PATH" $3

    ; Broadcast the change to all open applications
    SendMessage ${HWND_BROADCAST} ${WM_WININICHANGE} 0 "STR:Environment" /TIMEOUT=5000

    done:
        Pop $6
        Pop $5
        Pop $4
        Pop $3
        Pop $2
        Pop $1
        Pop $0

FunctionEnd


###############################################################################
# Specialty Functions
###############################################################################
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

FunctionEnd


Function updateMinionConfig

    ClearErrors
    FileOpen $0 "$INSTDIR\conf\minion" "r"               ; open target file for reading
    GetTempFileName $R0                                  ; get new temp file name
    FileOpen $1 $R0 "w"                                  ; open temp file for writing

    loop:                                                ; loop through each line
    FileRead $0 $2                                       ; read line from target file
    IfErrors done                                        ; end if errors are encountered (end of line)

    ${If} $MasterHost_State != ""                        ; if master is empty
    ${AndIf} $MasterHost_State != "salt"                 ; and if master is not 'salt'
        ${StrLoc} $3 $2 "master:" ">"                    ; where is 'master:' in this line
        ${If} $3 == 0                                    ; is it in the first...
        ${OrIf} $3 == 1                                  ; or second position (account for comments)
            StrCpy $2 "master: $MasterHost_State$\r$\n"  ; write the master
        ${EndIf}                                         ; close if statement
    ${EndIf}                                             ; close if statement

    ${If} $MinionName_State != ""                        ; if minion is empty
    ${AndIf} $MinionName_State != "hostname"             ; and if minion is not 'hostname'
        ${StrLoc} $3 $2 "id:" ">"                        ; where is 'id:' in this line
        ${If} $3 == 0                                    ; is it in the first...
        ${OrIf} $3 == 1                                  ; or the second position (account for comments)
            StrCpy $2 "id: $MinionName_State$\r$\n"      ; change line
        ${EndIf}                                         ; close if statement
    ${EndIf}                                             ; close if statement

    FileWrite $1 $2                                      ; write changed or unchanged line to temp file
    Goto loop

    done:
    FileClose $0                                         ; close target file
    FileClose $1                                         ; close temp file
    Delete "$INSTDIR\conf\minion"                        ; delete target file
    CopyFiles /SILENT $R0 "$INSTDIR\conf\minion"         ; copy temp file to target file
    Delete $R0                                           ; delete temp file

FunctionEnd


Function parseCommandLineSwitches

    ; Load the parameters
    ${GetParameters} $R0

    ; Check for start-minion switches
    ; /start-service is to be deprecated, so we must check for both
    ${GetOptions} $R0 "/start-service=" $R1
    ${GetOptions} $R0 "/start-minion=" $R2

    # Service: Start Salt Minion
    ${IfNot} $R2 == ""
        ; If start-minion was passed something, then set it
        StrCpy $StartMinion $R2
    ${ElseIfNot} $R1 == ""
        ; If start-service was passed something, then set StartMinion to that
        StrCpy $StartMinion $R1
    ${Else}
        ; Otherwise default to 1
        StrCpy $StartMinion 1
    ${EndIf}

    # Service: Minion Startup Type Delayed
    ${GetOptions} $R0 "/start-minion-delayed" $R1
    IfErrors start_minion_delayed_not_found
        StrCpy $StartMinionDelayed 1
    start_minion_delayed_not_found:

    # Minion Config: Master IP/Name
    ${GetOptions} $R0 "/master=" $R1
    ${IfNot} $R1 == ""
        StrCpy $MasterHost_State $R1
    ${ElseIf} $MasterHost_State == ""
        StrCpy $MasterHost_State "salt"
    ${EndIf}

    # Minion Config: Minion ID
    ${GetOptions} $R0 "/minion-name=" $R1
    ${IfNot} $R1 == ""
        StrCpy $MinionName_State $R1
    ${ElseIf} $MinionName_State == ""
        StrCpy $MinionName_State "hostname"
    ${EndIf}

FunctionEnd
