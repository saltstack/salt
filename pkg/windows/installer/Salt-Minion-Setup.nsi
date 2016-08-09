!define PRODUCT_NAME "Salt"
!define PRODUCT_NAME_OLD "Salt Minion"
!define PRODUCT_PUBLISHER "SaltStack, Inc"
!define PRODUCT_WEB_SITE "http://saltstack.org"
!define PRODUCT_CALL_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\salt-call.exe"
!define PRODUCT_CP_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\salt-cp.exe"
!define PRODUCT_KEY_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\salt-key.exe"
!define PRODUCT_MASTER_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\salt-master.exe"
!define PRODUCT_MINION_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\salt-minion.exe"
!define PRODUCT_RUN_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\salt-run.exe"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define PRODUCT_UNINST_KEY_OLD "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME_OLD}"
!define PRODUCT_UNINST_ROOT_KEY "HKLM"

# Import Libraries
!include "MUI2.nsh"
!include "nsDialogs.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"
!include "StrFunc.nsh"
!include "x64.nsh"
!include "WinMessages.nsh"
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
;
; Choose Install page
Page custom pageChooseInstall pageChooseInstall_Leave

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
Var Warning
Var CheckBox_Minion
Var CheckBox_Minion_State
Var CheckBox_Master
Var CheckBox_Master_State
Var MasterHost
Var MasterHost_State
Var MinionName
Var MinionName_State
Var StartMinion
Var StartMaster


###############################################################################
# Choose Installation Page
###############################################################################
Function pageChooseInstall

    # Set Page Title
    !insertmacro MUI_HEADER_TEXT "Choose Install" "Select components to install"
    nsDialogs::Create 1018
    Pop $Dialog

    ${If} $Dialog == error
        Abort
    ${EndIf}

    # Add Label
    ${NSD_CreateLabel} 0 0 100% 12u "Choose Installation:"
    Pop $Label

    # Add Install Minion Checkbox
    ${NSD_CreateCheckBox} 0 13u 100% 12u "Install &Minion"
    Pop $CheckBox_Minion
    ${NSD_OnClick} $CheckBox_Minion pageChooseInstall_OnClick

    # Add Install Master Checkbox
    ${NSD_CreateCheckBox} 0 26u 100% 12u "Install M&aster"
    Pop $CheckBox_Master
    ${NSD_OnClick} $CheckBox_Master pageChooseInstall_OnClick

    # Add warning label
    ${NSD_CreateLabel} 0 50u 100% 12u "You must select at least one item..."
    Pop $Warning
    CreateFont $0 "Arial" 9 600 /ITALIC
    SendMessage $Warning ${WM_SETFONT} $0 1
    SetCtlColors $Warning 0xBB0000 transparent
    ShowWindow $Warning ${SW_HIDE}

    # Set the minion to be checked by default if nothing set
    ${If} $CheckBox_Minion_State != ${BST_CHECKED}
    ${AndIf} $CheckBox_Master_State != ${BST_CHECKED}
        StrCpy $CheckBox_Minion_State ${BST_CHECKED}
    ${EndIf}

    # Load current settings for Minion
    ${If} $CheckBox_Minion_State == ${BST_CHECKED}
        ${NSD_Check} $CheckBox_Minion
    ${EndIf}

    # Load current settings for Master
    ${If} $CheckBox_Master_State == ${BST_CHECKED}
        ${NSD_Check} $CheckBox_Master
    ${EndIf}

    # Show the Page
    nsDialogs::Show

FunctionEnd


Function pageChooseInstall_OnClick

    # You have to pop the top handle to keep the stack clean
    Pop $R0

    # Assign the current checkbox states to the state variables
    ${NSD_GetState} $CheckBox_Minion $CheckBox_Minion_State
    ${NSD_GetState} $CheckBox_Master $CheckBox_Master_State

    # MessageBox MB_OK "Minion: $CheckBox_Minion_State$\n$\nMaster: $CheckBox_Master_State"

    # Get the handle to the next button
    GetDlgItem $0 $HWNDPARENT 1

    # Validate the checkboxes
    ${If} $CheckBox_Minion_State == 0
    ${AndIf} $CheckBox_Master_State == 0
        # Neither is checked, show warning and disable next
        ShowWindow $Warning ${SW_SHOW}
        EnableWindow $0 0
    ${Else}
        # At least one is checked, clear the warning and enable next
        ShowWindow $Warning ${SW_HIDE}
        EnableWindow $0 1
    ${EndIf}

FunctionEnd


Function pageChooseInstall_Leave

    # Set the State Variables when Next is clicked
    ${NSD_GetState} $CheckBox_Minion $CheckBox_Minion_State
    ${NSD_GetState} $CheckBox_Master $CheckBox_Master_State

FunctionEnd


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
    #MessageBox MB_OK "Master Hostname is:$\n$\n$MasterHost_State"

    ${NSD_GetText} $MinionName $MinionName_State
    #MessageBox MB_OK "Minion name is:$\n$\n$MinionName_State"

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
    Pop $CheckBox_Minion
    SetCtlColors $CheckBox_Minion "" "ffffff"
    # This command required to bring the checkbox to the front
    System::Call "User32::SetWindowPos(i, i, i, i, i, i, i) b ($CheckBox_Minion, ${HWND_TOP}, 0, 0, 0, 0, ${SWP_NOSIZE}|${SWP_NOMOVE})"

    # Create Start Master Checkbox
    ${NSD_CreateCheckbox} 120u 105u 100% 12u "&Start salt-master"
    Pop $CheckBox_Master
    SetCtlColors $CheckBox_Master "" "ffffff"
    # This command required to bring the checkbox to the front
    System::Call "User32::SetWindowPos(i, i, i, i, i, i, i) b ($CheckBox_Master, ${HWND_TOP}, 0, 0, 0, 0, ${SWP_NOSIZE}|${SWP_NOMOVE})"

    # Load current settings for Minion
    ${If} $CheckBox_Minion_State == ${BST_CHECKED}
        ${If} $StartMinion == 1
            ${NSD_Check} $CheckBox_Minion
        ${EndIf}
    ${Else}
        EnableWindow $CheckBox_Minion 0
        ${NSD_UnCheck} $CheckBox_Minion
    ${EndIf}

    # Load current settings for Master
    ${If} $CheckBox_Master_State == ${BST_CHECKED}
        ${If} $StartMaster == 1
            ${NSD_Check} $CheckBox_Master
        ${EndIf}
    ${Else}
        EnableWindow $CheckBox_Master 0
        ${NSD_UnCheck} $CheckBox_Master
    ${EndIf}

FunctionEnd


Function pageFinish_Leave

    # Assign the current checkbox states
    ${NSD_GetState} $CheckBox_Minion $StartMinion
    ${NSD_GetState} $CheckBox_Master $StartMaster

FunctionEnd


###############################################################################
# Installation Settings
###############################################################################
Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "Salt-${PRODUCT_VERSION}-${CPUARCH}-Setup.exe"
InstallDir "c:\salt"
InstallDirRegKey HKLM "${PRODUCT_DIR_REGKEY}" ""
ShowInstDetails show
ShowUnInstDetails show


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
    ReadRegStr $R0 HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "UninstallString"
    StrCmp $R0 "" skipUninstall Uninstall
    ; Check for existing installation old
    ReadRegStr $R0 HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME_OLD}" "UninstallString"
    StrCmp $R0 "" skipUninstall

    Uninstall:
    ; Found existing installation, prompt to uninstall
    MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION "${PRODUCT_NAME} is already installed.$\n$\nClick `OK` to remove the existing installation." /SD IDOK IDOK uninst
    Abort

    uninst:
        ; Make sure we're in the right directory
        ${If} $INSTDIR == "c:\salt\bin\Scripts"
          StrCpy $INSTDIR "C:\salt"
        ${EndIf}

        ; Stop and remove the salt-minion service
        nsExec::Exec 'net stop salt-minion'
        nsExec::Exec 'sc delete salt-minion'

        ; Stop and remove the salt-master service
        nsExec::Exec 'net stop salt-master'
        nsExec::Exec 'sc delete salt-master'

        ; Remove salt binaries and batch files
        Delete "$INSTDIR\uninst.exe"
        Delete "$INSTDIR\nssm.exe"
        Delete "$INSTDIR\salt*"
        RMDir /r "$INSTDIR\bin"

        ; Remove registry entries
        DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}"
        DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY_OLD}"
        DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_CALL_REGKEY}"
        DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_CP_REGKEY}"
        DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_KEY_REGKEY}"
        DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_MASTER_REGKEY}"
        DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_MINION_REGKEY}"
        DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_RUN_REGKEY}"

    skipUninstall:

FunctionEnd


Section -Post

    WriteUninstaller "$INSTDIR\uninst.exe"

    ; Uninstall Registry Entries
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayName" "$(^Name)"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\uninst.exe"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayIcon" "$INSTDIR\salt.ico"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
    WriteRegStr HKLM "SYSTEM\CurrentControlSet\services\salt-minion" "DependOnService" "nsi"

    # Setup Salt-Minion if Installed
    ${If} $CheckBox_Minion_State == ${BST_CHECKED}

        ; Commandline Registry Entries
        WriteRegStr HKLM "${PRODUCT_CALL_REGKEY}" "" "$INSTDIR\salt-call.bat"
        WriteRegStr HKLM "${PRODUCT_CALL_REGKEY}" "Path" "$INSTDIR\bin\"
        WriteRegStr HKLM "${PRODUCT_MINION_REGKEY}" "" "$INSTDIR\salt-minion.bat"
        WriteRegStr HKLM "${PRODUCT_MINION_REGKEY}" "Path" "$INSTDIR\bin\"

        ; Register the Salt-Minion Service
        nsExec::Exec "nssm.exe install salt-minion $INSTDIR\bin\python.exe $INSTDIR\bin\Scripts\salt-minion -c $INSTDIR\conf -l quiet"
        nsExec::Exec "nssm.exe set salt-minion AppEnvironmentExtra PYTHONHOME="
        nsExec::Exec "nssm.exe set salt-minion Description Salt Minion from saltstack.com"

    ${Else}

        # Remove Salt Minion Files
        Delete "$INSTDIR\salt-call.bat"
        Delete "$INSTDIR\bin\Scripts\salt-call"
        Delete "$INSTDIR\salt-minion*"
        Delete "$INSTDIR\bin\Scripts\salt-minion"

    ${EndIf}

    # Setup Salt-Master if Installed
    ${If} $CheckBox_Master_State == ${BST_CHECKED}

        ; Command Line Registry Entries
        WriteRegStr HKLM "${PRODUCT_CP_REGKEY}" "" "$INSTDIR\salt-cp.bat"
        WriteRegStr HKLM "${PRODUCT_CP_REGKEY}" "Path" "$INSTDIR\bin\"
        WriteRegStr HKLM "${PRODUCT_KEY_REGKEY}" "" "$INSTDIR\salt-key.bat"
        WriteRegStr HKLM "${PRODUCT_KEY_REGKEY}" "Path" "$INSTDIR\bin\"
        WriteRegStr HKLM "${PRODUCT_MASTER_REGKEY}" "" "$INSTDIR\salt-master.bat"
        WriteRegStr HKLM "${PRODUCT_MASTER_REGKEY}" "Path" "$INSTDIR\bin\"
        WriteRegStr HKLM "${PRODUCT_RUN_REGKEY}" "" "$INSTDIR\salt-run.bat"
        WriteRegStr HKLM "${PRODUCT_RUN_REGKEY}" "Path" "$INSTDIR\bin\"

        ; Register the Salt-Master Service
        nsExec::Exec "nssm.exe install salt-master $INSTDIR\bin\python.exe $INSTDIR\bin\Scripts\salt-master -c $INSTDIR\conf -l quiet"
        nsExec::Exec "nssm.exe set salt-master AppEnvironmentExtra PYTHONHOME="
        nsExec::Exec "nssm.exe set salt-master Description Salt Master from saltstack.com"

    ${Else}

        # Remove Salt Master Files
        Delete "$INSTDIR\salt-cp.bat"
        Delete "$INSTDIR\bin\Scripts\salt-cp"
        Delete "$INSTDIR\salt-key.bat"
        Delete "$INSTDIR\bin\Scripts\salt-key"
        Delete "$INSTDIR\salt-master.bat"
        Delete "$INSTDIR\bin\Scripts\salt-master"
        Delete "$INSTDIR\salt-run.bat"
        Delete "$INSTDIR\bin\Scripts\salt-run"

    ${EndIf}

    RMDir /R "$INSTDIR\var\cache\salt" ; removing cache from old version

    Call updateMinionConfig

SectionEnd


Function .onInstSuccess

    ; If start-minion is 1, then start the service
    ${If} $StartMinion == 1
        nsExec::Exec 'net start salt-minion'
    ${EndIf}

    ${If} $StartMaster == 1
        nsExec::Exec 'net start salt-master'
    ${EndIf}

FunctionEnd


Function un.onInit
    MessageBox MB_ICONQUESTION|MB_YESNO|MB_DEFBUTTON2 "Are you sure you want to completely remove $(^Name) and all of its components?" /SD IDYES IDYES +2
    Abort
FunctionEnd


Section Uninstall
    ; Stop and Remove salt-minion service
    nsExec::Exec 'net stop salt-minion'
    nsExec::Exec 'sc remove salt-minion'

    ; Stop and Remove salt-master service
    nsExec::Exec 'net stop salt-master'
    nsExec::Exec 'sc delete salt-master'

    ; Remove files
    Delete "$INSTDIR\uninst.exe"
    Delete "$INSTDIR\nssm.exe"
    Delete "$INSTDIR\salt*"

    ; Remove salt directory, you must check to make sure you're not removing
    ; the Program Files directory
    ${If} $INSTDIR != 'Program Files'
    ${AndIf} $INSTDIR != 'Program Files (x86)'
        RMDir /r "$INSTDIR"
    ${EndIf}

    ; Remove Uninstall Entries
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}"

    ; Remove Commandline Entries
    DeleteRegKey HKLM "${PRODUCT_CALL_REGKEY}"
    DeleteRegKey HKLM "${PRODUCT_KEY_REGKEY}"
    DeleteRegKey HKLM "${PRODUCT_MASTER_REGKEY}"
    DeleteRegKey HKLM "${PRODUCT_MINION_REGKEY}"
    DeleteRegKey HKLM "${PRODUCT_RUN_REGKEY}"

    ; Automatically close when finished
    SetAutoClose true

SectionEnd


Function un.onUninstSuccess
    HideWindow
    MessageBox MB_ICONINFORMATION|MB_OK "$(^Name) was successfully removed from your computer." /SD IDOK
FunctionEnd


###############################################################################
# Helper Functions
###############################################################################

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
        ; If start-service was passed something, then set it
        StrCpy $StartMinion $R1
    ${Else}
        ; Otherwise default to 1
        StrCpy $StartMinion 1
    ${EndIf}

    # Service: Start Salt Master
    ${GetOptions} $R0 "/start-master=" $R1
    ${IfNot} $R1 == ""
        ; If start-master was passed something, then set it
        StrCpy $StartMaster $R1
    ${Else}
        ; Otherwise default to 1
        StrCpy $StartMaster 1
    ${EndIf}

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

    # Installation Defaults
    StrCpy $CheckBox_Master_State 0
    StrCpy $CheckBox_Minion_State 1

    # Installation: Install Master
    ${GetOptions} $R0 "/install-master" $R1
    IfErrors install_master_not_found
        StrCpy $CheckBox_Master_State 1
    install_master_not_found:

    # Installation: Install Master Only
    ${GetOptions} $R0 "/master-only" $R1
    IfErrors master_only_not_found
        StrCpy $CheckBox_Master_State 1
        StrCpy $CheckBox_Minion_State 0
    master_only_not_found:

FunctionEnd
