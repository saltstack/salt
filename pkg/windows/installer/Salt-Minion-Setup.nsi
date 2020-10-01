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
!define OUTFILE "Salt-Minion-${PRODUCT_VERSION}-Py${PYTHON_VERSION}-${CPUARCH}-Setup.exe"

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
    !define PYTHON_VERSION "3"
!endif

!if "$%PROCESSOR_ARCHITECTURE%" == "AMD64"
    !define CPUARCH "AMD64"
!else if "$%PROCESSOR_ARCHITEW6432%" == "AMD64"
    !define CPUARCH "AMD64"
!else
    !define CPUARCH "x86"
!endif

# Part of the Trim function for Strings
!define Trim "!insertmacro Trim"
!macro Trim ResultVar String
    Push "${String}"
    Call Trim
    Pop "${ResultVar}"
!macroend

# Part of the Explode function for Strings
!define Explode "!insertmacro Explode"
!macro Explode Length Separator String
    Push    `${Separator}`
    Push    `${String}`
    Call    Explode
    Pop     `${Length}`
!macroend


###############################################################################
# Configure Pages, Ordering, and Configuration
###############################################################################
!define MUI_ABORTWARNING
!define MUI_ICON "salt.ico"
!define MUI_UNICON "salt.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP "panel.bmp"
!define MUI_UNWELCOMEFINISHPAGE_BITMAP "panel.bmp"


# Welcome page
!insertmacro MUI_PAGE_WELCOME

# License page
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"

# Configure Minion page
Page custom pageMinionConfig pageMinionConfig_Leave

# Instfiles page
!insertmacro MUI_PAGE_INSTFILES

# Finish page (Customized)
!define MUI_PAGE_CUSTOMFUNCTION_SHOW pageFinish_Show
!define MUI_PAGE_CUSTOMFUNCTION_LEAVE pageFinish_Leave
!insertmacro MUI_PAGE_FINISH

# Uninstaller pages
!insertmacro MUI_UNPAGE_INSTFILES

# Language files
!insertmacro MUI_LANGUAGE "English"


###############################################################################
# Custom Dialog Box Variables
###############################################################################
Var Dialog
Var Label
Var CheckBox_Minion_Start
Var CheckBox_Minion_Start_Delayed
Var ConfigMasterHost
Var MasterHost
Var MasterHost_State
Var ConfigMinionName
Var MinionName
Var MinionName_State
Var ExistingConfigFound
Var ConfigType
Var ConfigType_State
Var CustomConfig
Var CustomConfig_btn
Var CustomConfig_State
Var WarningCustomConfig
Var WarningExistingConfig
Var WarningDefaultConfig
Var StartMinion
Var StartMinionDelayed
Var DeleteInstallDir
Var ConfigWriteMinion
Var ConfigWriteMaster


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

    # Master IP or Hostname Dialog Control
    ${NSD_CreateLabel} 0 0 100% 12u "Master IP or Hostname:"
    Pop $Label

    ${NSD_CreateText} 0 13u 100% 12u $MasterHost_State
    Pop $MasterHost

    # Minion ID Dialog Control
    ${NSD_CreateLabel} 0 30u 100% 12u "Minion Name:"
    Pop $Label

    ${NSD_CreateText} 0 43u 100% 12u $MinionName_State
    Pop $MinionName

    # Config Drop List
    ${NSD_CreateDropList} 0 65u 25% 36u ""
    Pop $ConfigType
    ${NSD_CB_AddString} $ConfigType "Default Config"
    ${NSD_CB_AddString} $ConfigType "Custom Config"
    ${NSD_OnChange} $ConfigType pageMinionConfig_OnChange

    # Add Existing Config Warning Label
    ${NSD_CreateLabel} 0 80u 100% 60u "The values above are taken from an \
        existing configuration found in `c:\salt\conf\minion`. Configuration \
        settings defined in the `minion.d` directories, if they exist, are not \
        shown here.$\r$\n\
        $\r$\n\
        Clicking `Install` will leave the existing config unchanged."
    Pop $WarningExistingConfig
    CreateFont $0 "Arial" 10 500 /ITALIC
    SendMessage $WarningExistingConfig ${WM_SETFONT} $0 1
    SetCtlColors $WarningExistingConfig 0xBB0000 transparent

    # Add Default Config Warning Label
    ${NSD_CreateLabel} 0 80u 100% 60u "Clicking `Install` will backup the \
        the existing minion config file and minion.d directories. The values \
        above will be used in the new default config.$\r$\n\
            $\r$\n\
            NOTE: If Master IP is set to `salt` and Minion Name is set to \
            `hostname` no changes will be made."
    Pop $WarningDefaultConfig
    CreateFont $0 "Arial" 10 500 /ITALIC
    SendMessage $WarningDefaultConfig ${WM_SETFONT} $0 1
    SetCtlColors $WarningDefaultConfig 0xBB0000 transparent

    # Add Custom Config File Selector and Warning Label
    ${NSD_CreateText} 26% 65u 64% 12u $CustomConfig_State
    Pop $CustomConfig
    ${NSD_CreateButton} 91% 65u 9% 12u "..."
    Pop $CustomConfig_btn
    ${NSD_OnClick} $CustomConfig_btn pageCustomConfigBtn_OnClick

    ${If} $ExistingConfigFound == 0
        ${NSD_CreateLabel} 0 80u 100% 60u "Values entered above will be used \
            in the custom config.$\r$\n\
            $\r$\n\
            NOTE: If Master IP is set to `salt` and Minion Name is set to \
            `hostname` no changes will be made."
    ${Else}
        ${NSD_CreateLabel} 0 80u 100% 60u "Clicking `Install` will backup the \
            the existing minion config file and minion.d directories. The \
            values above will be used in the custom config.$\r$\n\
            $\r$\n\
            NOTE: If Master IP is set to `salt` and Minion Name is set to \
            `hostname` no changes will be made."
    ${Endif}
    Pop $WarningCustomConfig
    CreateFont $0 "Arial" 10 500 /ITALIC
    SendMessage $WarningCustomConfig ${WM_SETFONT} $0 1
    SetCtlColors $WarningCustomConfig 0xBB0000 transparent

    # If existing config found, add the Existing Config option to the Drop List
    # If not, hide the Default Warning
    ${If} $ExistingConfigFound == 1
        ${NSD_CB_AddString} $ConfigType "Existing Config"
    ${Else}
        ShowWindow $WarningDefaultConfig ${SW_HIDE}
    ${Endif}

    ${NSD_CB_SelectString} $ConfigType $ConfigType_State
    ${NSD_SetText} $CustomConfig $CustomConfig_State

    Call pageMinionConfig_OnChange

    nsDialogs::Show

FunctionEnd


Function pageMinionConfig_OnChange

    # You have to pop the top handle to keep the stack clean
    Pop $R0

    # Assign the current checkbox state to the variable
    ${NSD_GetText} $ConfigType $ConfigType_State

    # Update Dialog
    ${Switch} $ConfigType_State
        ${Case} "Existing Config"
            # Enable Master/Minion and set values
            EnableWindow $MasterHost 0
            EnableWindow $MinionName 0
            ${NSD_SetText} $MasterHost $ConfigMasterHost
            ${NSD_SetText} $MinionName $ConfigMinionName
            # Hide Custom File Picker
            ShowWindow $CustomConfig ${SW_HIDE}
            ShowWindow $CustomConfig_btn ${SW_HIDE}
            # Hide Warnings
            ShowWindow $WarningDefaultConfig ${SW_HIDE}
            ShowWindow $WarningCustomConfig ${SW_HIDE}
            # Show Existing Warning
            ShowWindow $WarningExistingConfig ${SW_SHOW}
            ${Break}
        ${Case} "Custom Config"
            # Enable Master/Minion and set values
            EnableWindow $MasterHost 1
            EnableWindow $MinionName 1
            ${NSD_SetText} $MasterHost $MasterHost_State
            ${NSD_SetText} $MinionName $MinionName_State
            # Show Custom File Picker
            ShowWindow $CustomConfig ${SW_SHOW}
            ShowWindow $CustomConfig_btn ${SW_SHOW}
            # Hide Warnings
            ShowWindow $WarningDefaultConfig ${SW_HIDE}
            ShowWindow $WarningExistingConfig ${SW_HIDE}
            # Show Custom Warning
            ShowWindow $WarningCustomConfig ${SW_SHOW}
            ${Break}
        ${Case} "Default Config"
            # Enable Master/Minion and set values
            EnableWindow $MasterHost 1
            EnableWindow $MinionName 1
            ${NSD_SetText} $MasterHost $MasterHost_State
            ${NSD_SetText} $MinionName $MinionName_State
            # Hide Custom File Picker
            ShowWindow $CustomConfig ${SW_HIDE}
            ShowWindow $CustomConfig_btn ${SW_HIDE}
            # Hide Warnings
            ShowWindow $WarningExistingConfig ${SW_HIDE}
            ShowWindow $WarningCustomConfig ${SW_HIDE}
            # Show Default Warning, if there is an existing config
            ${If} $ExistingConfigFound == 1
                ShowWindow $WarningDefaultConfig ${SW_SHOW}
            ${Endif}
            ${Break}
    ${EndSwitch}

FunctionEnd

# File Picker Definitions
!define OFN_FILEMUSTEXIST 0x00001000
!define OFN_DONTADDTOREC 0x02000000
!define OPENFILENAME_SIZE_VERSION_400 76
!define OPENFILENAME 'i,i,i,i,i,i,i,i,i,i,i,i,i,i,&i2,&i2,i,i,i,i'
Function pageCustomConfigBtn_OnClick

    Pop $0
    System::Call '*(&t${NSIS_MAX_STRLEN})i.s'  # Allocate OPENFILENAME.lpstrFile buffer
    System::Call '*(${OPENFILENAME})i.r0'      # Allocate OPENFILENAME struct
    System::Call '*$0(${OPENFILENAME})(${OPENFILENAME_SIZE_VERSION_400}, \
                      $hwndparent, , , , , , sr1, ${NSIS_MAX_STRLEN} , , , , \
                      t"Select Custom Config File", \
                      ${OFN_FILEMUSTEXIST} | ${OFN_DONTADDTOREC})'

    # Populate file name field
    ${NSD_GetText} $CustomConfig $2
    System::Call "*$1(&t${NSIS_MAX_STRLEN}r2)" ; Set lpstrFile to the old path (if any)

    # Open the dialog
    System::Call 'COMDLG32::GetOpenFileName(ir0)i.r2'

    # Get file name field
    ${If} $2 <> 0
        System::Call "*$1(&t${NSIS_MAX_STRLEN}.r2)"
        ${NSD_SetText} $CustomConfig $2
    ${EndIf}

    # Free resources
    System::Free $1
    System::Free $0

FunctionEnd


Function pageMinionConfig_Leave

    # Save the State
    ${NSD_GetText} $MasterHost $MasterHost_State
    ${NSD_GetText} $MinionName $MinionName_State
    ${NSD_GetText} $ConfigType $ConfigType_State
    ${NSD_GetText} $CustomConfig $CustomConfig_State

    # Abort if config file not found
    ${If} $ConfigType_State == "Custom Config"
        IfFileExists "$CustomConfig_State" continue 0
            MessageBox MB_OK "File not found: $CustomConfig_State" /SD IDOK
            Abort
    ${EndIf}

    continue:
    Call BackupExistingConfig

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
Name "${PRODUCT_NAME} ${PRODUCT_VERSION} (Python ${PYTHON_VERSION})"
OutFile "${OutFile}"
InstallDir "c:\salt"
InstallDirRegKey HKLM "${PRODUCT_DIR_REGKEY}" ""
ShowInstDetails show
ShowUnInstDetails show


Section -copy_prereqs
    # Copy prereqs to the Plugins Directory
    # These files are downloaded by build_pkg.bat
    # This directory gets removed upon completion
    SetOutPath "$PLUGINSDIR\"
    File /r "..\prereqs\"
SectionEnd

# Check if the  Windows 10 Universal C Runtime (KB2999226) is installed
# Python 3 needs the updated ucrt on Windows 8.1 / 2012R2 and lower
# They are installed via KB2999226, but we're not going to patch the system here
# Instead, we're going to copy the .dll files to the \salt\bin directory
Section -install_ucrt

    Var /GLOBAL UcrtFileName

    # Get the Major.Minor version Number
    # Windows 10 introduced CurrentMajorVersionNumber
    ReadRegStr $R0 HKLM "SOFTWARE\Microsoft\Windows NT\CurrentVersion" \
        CurrentMajorVersionNumber

    # Windows 10/2016 will return a value here, skip to the end if returned
    StrCmp $R0 '' lbl_needs_ucrt 0

    # Found Windows 10
    detailPrint "KB2999226 does not apply to this machine"
    goto lbl_done

    lbl_needs_ucrt:
    # UCRT only needed on Windows Server 2012R2/Windows 8.1 and below
    # The first ReadRegStr command above should have skipped to lbl_done if on
    # Windows 10 box

    # Is the update already installed
    ClearErrors

    # Use WMI to check if it's installed
    detailPrint "Checking for existing UCRT (KB2999226) installation"
    nsExec::ExecToStack 'cmd /q /c wmic qfe get hotfixid | findstr "^KB2999226"'
    # Clean up the stack
    Pop $R0 # Gets the ErrorCode
    Pop $R1 # Gets the stdout, which should be KB2999226 if it's installed

    # If it returned KB2999226 it's already installed
    StrCmp $R1 'KB2999226' lbl_done

    detailPrint "UCRT (KB2999226) not found"

    # Use RunningX64 here to get the Architecture for the system running the installer
    # CPUARCH is defined when the installer is built and is based on the machine that
    # built the installer, not the target system as we need here.
    ${If} ${RunningX64}
        StrCpy $UcrtFileName "ucrt_x64.zip"
    ${Else}
        StrCpy $UcrtFileName "ucrt_x86.zip"
    ${EndIf}

    ClearErrors

    detailPrint "Unzipping UCRT dll files to $INSTDIR\bin"
    CreateDirectory $INSTDIR\bin
    nsisunz::UnzipToLog "$PLUGINSDIR\$UcrtFileName" "$INSTDIR\bin"

    # Clean up the stack
    Pop $R0  # Get Error

    ${IfNot} $R0 == "success"
        detailPrint "error: $R0"
        Sleep 3000
    ${Else}
        detailPrint "UCRT dll files copied successfully"
    ${EndIf}

    lbl_done:

SectionEnd


# Check and install Visual C++ redist 2013 packages
# Hidden section (-) to install VCRedist
Section -install_vcredist_2013

    Var /GLOBAL VcRedistName
    Var /GLOBAL VcRedistGuid
    Var /GLOBAL NeedVcRedist

    # GUIDs can be found by installing them and then running the following command:
    # wmic product where "Name like '%2013%minimum runtime%'" get Name, Version, IdentifyingNumber
    !define VCREDIST_X86_NAME "vcredist_x86_2013"
    !define VCREDIST_X86_GUID "{8122DAB1-ED4D-3676-BB0A-CA368196543E}"
    !define VCREDIST_X64_NAME "vcredist_x64_2013"
    !define VCREDIST_X64_GUID "{53CF6934-A98D-3D84-9146-FC4EDF3D5641}"

    # Only install 64bit VCRedist on 64bit machines
    ${If} ${CPUARCH} == "AMD64"
        StrCpy $VcRedistName ${VCREDIST_X64_NAME}
        StrCpy $VcRedistGuid ${VCREDIST_X64_GUID}
        Call InstallVCRedist
    ${Else}
        # Install 32bit VCRedist on all machines
        StrCpy $VcRedistName ${VCREDIST_X86_NAME}
        StrCpy $VcRedistGuid ${VCREDIST_X86_GUID}
        Call InstallVCRedist
    ${EndIf}

SectionEnd


Function InstallVCRedist
    # Check to see if it's already installed
    Call MsiQueryProductState
    ${If} $NeedVcRedist == "True"
        detailPrint "System requires $VcRedistName"
        MessageBox MB_ICONQUESTION|MB_YESNO|MB_DEFBUTTON2 \
            "$VcRedistName is currently not installed. Would you like to install?" \
            /SD IDYES IDNO endVCRedist

        # If an output variable is specified ($0 in the case below),
        # ExecWait sets the variable with the exit code (and only sets the
        # error flag if an error occurs; if an error occurs, the contents
        # of the user variable are undefined).
        # http://nsis.sourceforge.net/Reference/ExecWait
        ClearErrors
        detailPrint "Installing $VcRedistName..."
        ExecWait '"$PLUGINSDIR\$VcRedistName.exe" /install /quiet /norestart' $0
        IfErrors 0 CheckVcRedistErrorCode
            MessageBox MB_OK \
                "$VcRedistName failed to install. Try installing the package manually." \
                /SD IDOK
            detailPrint "An error occurred during installation of $VcRedistName"

        CheckVcRedistErrorCode:
        # Check for Reboot Error Code (3010)
        ${If} $0 == 3010
            MessageBox MB_OK \
                "$VcRedistName installed but requires a restart to complete." \
                /SD IDOK
            detailPrint "Reboot and run Salt install again"

        # Check for any other errors
        ${ElseIfNot} $0 == 0
            MessageBox MB_OK \
                "$VcRedistName failed with ErrorCode: $0. Try installing the package manually." \
                /SD IDOK
            detailPrint "An error occurred during installation of $VcRedistName"
            detailPrint "Error: $0"
        ${EndIf}

        endVCRedist:

    ${EndIf}

FunctionEnd


Section "MainSection" SEC01

    SetOutPath "$INSTDIR\"
    SetOverwrite off
    CreateDirectory $INSTDIR\conf\pki\minion
    CreateDirectory $INSTDIR\conf\minion.d
    File /r "..\buildenv\"
    nsExec::Exec 'icacls c:\salt /inheritance:r /grant:r "*S-1-5-32-544":(OI)(CI)F /grant:r "*S-1-5-18":(OI)(CI)F'

SectionEnd


Function .onInit

    InitPluginsDir
    Call parseCommandLineSwitches

    # Uninstall msi-installed salt
    # Source    https://nsis-dev.github.io/NSIS-Forums/html/t-303468.html
    !define upgradecode {FC6FB3A2-65DE-41A9-AD91-D10A402BD641}    ;Salt upgrade code
    StrCpy $0 0
    loop:
    System::Call 'MSI::MsiEnumRelatedProducts(t "${upgradecode}",i0,i r0,t.r1)i.r2'
    ${If} $2 = 0
	# Now $1 contains the product code
        DetailPrint product:$1
        push $R0
          StrCpy $R0 $1
          Call UninstallMSI
        pop $R0
        IntOp $0 $0 + 1
        goto loop
    ${Endif}

    # If custom config passed, verify its existence before continuing so we
    # don't uninstall an existing installation and then fail
    ${If} $ConfigType_State == "Custom Config"
        IfFileExists "$CustomConfig_State" customConfigExists 0
        Abort
    ${EndIf}

    customConfigExists:
        # Check for existing installation
        ReadRegStr $R0 HKLM \
            "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
            "UninstallString"
        StrCmp $R0 "" checkOther
        # Found existing installation, prompt to uninstall
        MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION \
            "${PRODUCT_NAME} is already installed.$\n$\n\
            Click `OK` to remove the existing installation." \
            /SD IDOK IDOK uninst
        Abort

    checkOther:
        # Check for existing installation of full salt
        ReadRegStr $R0 HKLM \
            "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME_OTHER}" \
            "UninstallString"
        StrCmp $R0 "" skipUninstall
        # Found existing installation, prompt to uninstall
        MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION \
            "${PRODUCT_NAME_OTHER} is already installed.$\n$\n\
            Click `OK` to remove the existing installation." \
            /SD IDOK IDOK uninst
        Abort

    uninst:

        # Get current Silent status
        StrCpy $R0 0
        ${If} ${Silent}
            StrCpy $R0 1
        ${EndIf}

        # Turn on Silent mode
        SetSilent silent

        # Don't remove all directories
        StrCpy $DeleteInstallDir 0

        # Uninstall silently
        Call uninstallSalt

        # Set it back to Normal mode, if that's what it was before
        ${If} $R0 == 0
            SetSilent normal
        ${EndIf}

    skipUninstall:

    Call getExistingMinionConfig

    ${If} $ExistingConfigFound == 0
    ${AndIf} $ConfigType_State == "Existing Config"
        StrCpy $ConfigType_State "Default Config"
    ${EndIf}

    IfSilent 0 +2
        Call BackupExistingConfig

FunctionEnd


# Time Stamp Definition
!define /date TIME_STAMP "%Y-%m-%d-%H-%M-%S"
Function BackupExistingConfig

    ${If} $ExistingConfigFound == 1                     # If existing config found
    ${AndIfNot} $ConfigType_State == "Existing Config"  # If not using Existing Config

        # Backup the minion config
        Rename "$INSTDIR\conf\minion" "$INSTDIR\conf\minion-${TIME_STAMP}.bak"
        IfFileExists "$INSTDIR\conf\minion.d" 0 +2
            Rename "$INSTDIR\conf\minion.d" "$INSTDIR\conf\minion.d-${TIME_STAMP}.bak"

    ${EndIf}

    # By this point there should be no existing config
    # It was either backed up or wasn't there to begin with
    ${If} $ConfigType_State == "Custom Config"  # If we're using Custom Config
    ${AndIfNot} $CustomConfig_State == ""       # If a custom config is passed

        # Check for a file name
        # Named file should be in the same directory as the installer
        CreateDirectory "$INSTDIR\conf"
        IfFileExists "$EXEDIR\$CustomConfig_State" 0 checkFullPath
            CopyFiles /SILENT /FILESONLY "$EXEDIR\$CustomConfig_State" "$INSTDIR\conf\minion"
            goto finished

        # Maybe it was a full path to a file
        checkFullPath:
        IfFileExists "$CustomConfig_State" 0 finished
            CopyFiles /SILENT /FILESONLY "$CustomConfig_State" "$INSTDIR\conf\minion"

        finished:

    ${EndIf}

FunctionEnd


Section -Post

    WriteUninstaller "$INSTDIR\uninst.exe"

    # Uninstall Registry Entries
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

    # Set the estimated size
    ${GetSize} "$INSTDIR\bin" "/S=OK" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" \
        "EstimatedSize" "$0"

    # Commandline Registry Entries
    WriteRegStr HKLM "${PRODUCT_CALL_REGKEY}" "" "$INSTDIR\salt-call.bat"
    WriteRegStr HKLM "${PRODUCT_CALL_REGKEY}" "Path" "$INSTDIR\bin\"
    WriteRegStr HKLM "${PRODUCT_MINION_REGKEY}" "" "$INSTDIR\salt-minion.bat"
    WriteRegStr HKLM "${PRODUCT_MINION_REGKEY}" "Path" "$INSTDIR\bin\"

    # Register the Salt-Minion Service
    nsExec::Exec "$INSTDIR\bin\ssm.exe install salt-minion $INSTDIR\bin\python.exe -E -s $INSTDIR\bin\Scripts\salt-minion -c $INSTDIR\conf -l quiet"
    nsExec::Exec "$INSTDIR\bin\ssm.exe set salt-minion Description Salt Minion from saltstack.com"
    nsExec::Exec "$INSTDIR\bin\ssm.exe set salt-minion Start SERVICE_AUTO_START"
    nsExec::Exec "$INSTDIR\bin\ssm.exe set salt-minion AppStopMethodConsole 24000"
    nsExec::Exec "$INSTDIR\bin\ssm.exe set salt-minion AppStopMethodWindow 2000"
    nsExec::Exec "$INSTDIR\bin\ssm.exe set salt-minion AppRestartDelay 60000"

    ${IfNot} $ConfigType_State == "Existing Config"  # If not using Existing Config
        Call updateMinionConfig
    ${EndIf}

    # Add $INSTDIR in the Path
    EnVar::SetHKLM
    EnVar::AddValue Path "$INSTDIR"

SectionEnd


Function .onInstSuccess

    # If StartMinionDelayed is 1, then set the service to start delayed
    ${If} $StartMinionDelayed == 1
        nsExec::Exec "$INSTDIR\bin\ssm.exe set salt-minion Start SERVICE_DELAYED_AUTO_START"
    ${EndIf}

    # If start-minion is 1, then start the service
    ${If} $StartMinion == 1
        nsExec::Exec 'net start salt-minion'
    ${EndIf}

FunctionEnd


Function un.onInit

    # Load the parameters
    ${GetParameters} $R0

    # Uninstaller: Remove Installation Directory
    ClearErrors
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

    # Remove $INSTDIR from the Path
    EnVar::SetHKLM
    EnVar::DeleteValue Path "$INSTDIR"

SectionEnd


!macro uninstallSalt un
Function ${un}uninstallSalt

    # Make sure we're in the right directory
    ${If} $INSTDIR == "c:\salt\bin\Scripts"
      StrCpy $INSTDIR "C:\salt"
    ${EndIf}

    # Stop and Remove salt-minion service
    nsExec::Exec 'net stop salt-minion'
    nsExec::Exec 'sc delete salt-minion'

    # Stop and remove the salt-master service
    nsExec::Exec 'net stop salt-master'
    nsExec::Exec 'sc delete salt-master'

    # Remove files
    Delete "$INSTDIR\uninst.exe"
    Delete "$INSTDIR\ssm.exe"
    Delete "$INSTDIR\salt*"
    Delete "$INSTDIR\vcredist.exe"
    RMDir /r "$INSTDIR\bin"

    # Remove Registry entries
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}"
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY_OTHER}"
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_CALL_REGKEY}"
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_CP_REGKEY}"
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_KEY_REGKEY}"
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_MASTER_REGKEY}"
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_MINION_REGKEY}"
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_RUN_REGKEY}"

    # Automatically close when finished
    SetAutoClose true

    # Prompt to remove the Installation directory
    ${IfNot} $DeleteInstallDir == 1
        MessageBox MB_ICONQUESTION|MB_YESNO|MB_DEFBUTTON2 \
            "Would you like to completely remove $INSTDIR and all of its contents?" \
            /SD IDNO IDNO finished
    ${EndIf}

    # Make sure you're not removing Program Files
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
    # Used for detecting VCRedist Installation
    !define INSTALLSTATE_DEFAULT "5"

    StrCpy $NeedVcRedist "False"
    System::Call "msi::MsiQueryProductStateA(t '$VcRedistGuid') i.r0"
    StrCmp $0 ${INSTALLSTATE_DEFAULT} +2 0
    StrCpy $NeedVcRedist "True"

FunctionEnd

#------------------------------------------------------------------------------
# Trim Function
# - Trim whitespace from the beginning and end of a string
# - Trims spaces, \r, \n, \t
#
# Usage:
#   Push " some string "  ; String to Trim
#   Call Trim
#   Pop $0                ; Trimmed String: "some string"
#
#   or
#
#   ${Trim} $0 $1   ; Trimmed String, String to Trim
#------------------------------------------------------------------------------
Function Trim

    Exch $R1 # Original string
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


#------------------------------------------------------------------------------
# Explode Function
# - Splits a string based off the passed separator
# - Each item in the string is pushed to the stack
# - The last item pushed to the stack is the length of the array
#
# Usage:
#   Push ","                    ; Separator
#   Push "string,to,separate"   ; String to explode
#   Call Explode
#   Pop $0                      ; Number of items in the array
#
#   or
#
#   ${Explode} $0 $1 $2         ; Length, Separator, String
#------------------------------------------------------------------------------
Function Explode
    # Initialize variables
    Var /GLOBAL explString
    Var /GLOBAL explSeparator
    Var /GLOBAL explStrLen
    Var /GLOBAL explSepLen
    Var /GLOBAL explOffset
    Var /GLOBAL explTmp
    Var /GLOBAL explTmp2
    Var /GLOBAL explTmp3
    Var /GLOBAL explArrCount

    # Get input from user
    Pop $explString
    Pop $explSeparator

    # Calculates initial values
    StrLen $explStrLen $explString
    StrLen $explSepLen $explSeparator
    StrCpy $explArrCount 1

    ${If} $explStrLen <= 1             #   If we got a single character
    ${OrIf} $explSepLen > $explStrLen  #   or separator is larger than the string,
        Push    $explString            #   then we return initial string with no change
        Push    1                      #   and set array's length to 1
        Return
    ${EndIf}

    # Set offset to the last symbol of the string
    StrCpy $explOffset $explStrLen
    IntOp  $explOffset $explOffset - 1

    # Clear temp string to exclude the possibility of appearance of occasional data
    StrCpy $explTmp   ""
    StrCpy $explTmp2  ""
    StrCpy $explTmp3  ""

    # Loop until the offset becomes negative
    ${Do}
        # If offset becomes negative, it is time to leave the function
        ${IfThen} $explOffset == -1 ${|} ${ExitDo} ${|}

        # Remove everything before and after the searched part ("TempStr")
        StrCpy $explTmp $explString $explSepLen $explOffset

        ${If} $explTmp == $explSeparator
            # Calculating offset to start copy from
            IntOp   $explTmp2 $explOffset + $explSepLen    # Offset equals to the current offset plus length of separator
            StrCpy  $explTmp3 $explString "" $explTmp2

            Push    $explTmp3                              # Throwing array item to the stack
            IntOp   $explArrCount $explArrCount + 1        # Increasing array's counter

            StrCpy  $explString $explString $explOffset 0  # Cutting all characters beginning with the separator entry
            StrLen  $explStrLen $explString
        ${EndIf}

        ${If} $explOffset = 0           # If the beginning of the line met and there is no separator,
                                        # copying the rest of the string
            ${If} $explSeparator == ""  # Fix for the empty separator
                IntOp   $explArrCount   $explArrCount - 1
            ${Else}
                Push    $explString
            ${EndIf}
        ${EndIf}

        IntOp   $explOffset $explOffset - 1
    ${Loop}

    Push $explArrCount
FunctionEnd


#------------------------------------------------------------------------------
# UninstallMSI Function
# - Uninstalls MSI by product code
#
# Usage:
#   Push product code
#   Call UninstallMSI
#
# Source:
#   https://nsis.sourceforge.io/Uninstalling_a_previous_MSI_(Windows_installer_package)
#------------------------------------------------------------------------------
Function UninstallMSI
    ; $R0 === product code
    MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION \
        "${PRODUCT_NAME} is already installed via MSI.$\n$\n\
        Click `OK` to remove the existing installation." \
        /SD IDOK IDOK UninstallMSI
    Abort

    UninstallMSI:
        ExecWait '"msiexec.exe" /x $R0 /qb /quiet /norestart'

FunctionEnd


###############################################################################
# Specialty Functions
###############################################################################
Function getExistingMinionConfig

    # Set Config Found Default Value
    StrCpy $ExistingConfigFound 0

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
    StrCpy $ExistingConfigFound 1
    FileOpen $0 "$INSTDIR\conf\minion" r

    confLoop:
        ClearErrors                                             # clear Errors
        FileRead $0 $1                                          # read the next line
        IfErrors EndOfFile                                      # error is probably EOF
        ${StrLoc} $2 $1 "master:" ">"                           # find `master:` starting at the beginning
        ${If} $2 == 0                                           # if it found it in the first position, then it is defined
            ${StrStrAdv} $2 $1 "master: " ">" ">" "0" "0" "0"   # read everything after `master: `
            ${Trim} $2 $2                                       # trim white space
            ${If} $2 == ""                                      # if it's empty, it's probably a list of masters
                masterLoop:
                ClearErrors                                     # clear Errors
                FileRead $0 $1                                  # read the next line
                IfErrors EndOfFile                              # error is probably EOF
                ${StrStrAdv} $2 $1 "- " ">" ">" "0" "0" "0"     # read everything after `- `
                ${Trim} $2 $2                                   # trim white space
                ${IfNot} $2 == ""                               # if the line is not empty, we found something
                    ${If} $ConfigMasterHost == ""               # if the config setting is empty
                        StrCpy $ConfigMasterHost $2             # make the first item the new entry
                    ${Else}
                        StrCpy $ConfigMasterHost "$ConfigMasterHost,$2"  # Append the new master, comma separated
                    ${EndIf}
                    Goto masterLoop                             # check the next one
                ${EndIf}
            ${Else}
                StrCpy $ConfigMasterHost $2                     # a single master entry
            ${EndIf}
        ${EndIf}

        ${StrLoc} $2 $1 "id:" ">"
        ${If} $2 == 0
            ${StrStrAdv} $2 $1 "id: " ">" ">" "0" "0" "0"
            ${Trim} $2 $2
            StrCpy $ConfigMinionName $2
        ${EndIf}

    Goto confLoop

    EndOfFile:
    FileClose $0

    confReallyNotFound:

    # Set Default Config Values if not found
    ${If} $ConfigMasterHost == ""
        StrCpy $ConfigMasterHost "salt"
    ${EndIf}
    ${If} $ConfigMinionName == ""
        StrCpy $ConfigMinionName "hostname"
    ${EndIf}

FunctionEnd


Var cfg_line
Var chk_line
Var lst_check
Function updateMinionConfig

    ClearErrors
    FileOpen $0 "$INSTDIR\conf\minion" "r"              # open target file for reading
    GetTempFileName $R0                                 # get new temp file name
    FileOpen $1 $R0 "w"                                 # open temp file for writing

    StrCpy $ConfigWriteMaster 1                         # write the master config value
    StrCpy $ConfigWriteMinion 1                         # write the minion config value

    loop:                                               # loop through each line
        FileRead $0 $cfg_line                           # read line from target file
        IfErrors done                                   # end if errors are encountered (end of line)

        loop_after_read:
        StrCpy $lst_check 0                             # list check not performed

        ${If} $MasterHost_State == ""                   # if master is empty
        ${OrIf} $MasterHost_State == "salt"             # or if master is 'salt'
            StrCpy $ConfigWriteMaster 0                 # no need to write master config
        ${EndIf}                                        # close if statement
        ${If} $MinionName_State == ""                   # if minion is empty
        ${OrIf} $MinionName_State == "hostname"         # and if minion is not 'hostname'
            StrCpy $ConfigWriteMinion 0                 # no need to write minion config
        ${EndIf}                                        # close if statement

        ${If} $ConfigWriteMaster == 1                   # if we need to write master config

            ${StrLoc} $3 $cfg_line "master:" ">"        # where is 'master:' in this line
            ${If} $3 == 0                               # is it in the first...
            ${OrIf} $3 == 1                             # or second position (account for comments)

                ${Explode} $9 "," $MasterHost_state     # Split the hostname on commas, $9 is the number of items found
                ${If} $9 == 1                           # 1 means only a single master was passed
                    StrCpy $cfg_line "master: $MasterHost_State$\r$\n"  # write the master
                ${Else}                                 # make a multi-master entry
                    StrCpy $cfg_line "master:"          # make the first line "master:"

                    loop_explode:                       # start a loop to go through the list in the config
                    pop $8                              # pop the next item off the stack
                    ${Trim} $8 $8                       # trim any whitespace
                    StrCpy $cfg_line "$cfg_line$\r$\n  - $8"  # add it to the master variable ($2)
                    IntOp $9 $9 - 1                     # decrement the list count
                    ${If} $9 >= 1                       # if it's not 0
                        Goto loop_explode               # do it again
                    ${EndIf}                            # close if statement
                    StrCpy $cfg_line "$cfg_line$\r$\n"  # Make sure there's a new line at the end

                    # Remove remaining items in list
                    ${While} $lst_check == 0            # while list item found
                        FileRead $0 $chk_line           # read line from target file
                        IfErrors done                   # end if errors are encountered (end of line)
                        ${StrLoc} $3 $chk_line "  - " ">"  # where is 'master:' in this line
                        ${If} $3 == ""                  # is it in the first...
                            StrCpy $lst_check 1         # list check performed and finished
                        ${EndIf}
                    ${EndWhile}

                ${EndIf}                                # close if statement

                StrCpy $ConfigWriteMaster 0             # master value written to config

            ${EndIf}                                    # close if statement
        ${EndIf}                                        # close if statement

        ${If} $ConfigWriteMinion == 1                   # if we need to write minion config
            ${StrLoc} $3 $cfg_line "id:" ">"            # where is 'id:' in this line
            ${If} $3 == 0                               # is it in the first...
            ${OrIf} $3 == 1                             # or the second position (account for comments)
                StrCpy $cfg_line "id: $MinionName_State$\r$\n"  # write the minion config setting
                StrCpy $ConfigWriteMinion 0             # minion value written to config
            ${EndIf}                                    # close if statement
        ${EndIf}                                        # close if statement

        FileWrite $1 $cfg_line                          # write changed or unchanged line to temp file

    ${If} $lst_check == 1                               # master not written to the config
        StrCpy $cfg_line $chk_line
        Goto loop_after_read                            # A loop was performed, skip the next read
    ${EndIf}                                            # close if statement

    Goto loop                                           # check the next line in the config file

    done:
    ClearErrors
    # Does master config still need to be written
    ${If} $ConfigWriteMaster == 1                       # master not written to the config

        ${Explode} $9 "," $MasterHost_state             # split the hostname on commas, $9 is the number of items found
        ${If} $9 == 1                                   # 1 means only a single master was passed
            StrCpy $cfg_line "master: $MasterHost_State"  # write the master
        ${Else}                                         # make a multi-master entry
            StrCpy $cfg_line "master:"                  # make the first line "master:"

            loop_explode_2:                             # start a loop to go through the list in the config
            pop $8                                      # pop the next item off the stack
            ${Trim} $8 $8                               # trim any whitespace
            StrCpy $cfg_line "$cfg_line$\r$\n  - $8"    # add it to the master variable ($2)
            IntOp $9 $9 - 1                             # decrement the list count
            ${If} $9 >= 1                               # if it's not 0
                Goto loop_explode_2                     # do it again
            ${EndIf}                                    # close if statement
        ${EndIf}                                        # close if statement
        FileWrite $1 $cfg_line                          # write changed or unchanged line to temp file

    ${EndIf}                                            # close if statement

    ${If} $ConfigWriteMinion == 1                       # minion ID not written to the config
        StrCpy $cfg_line "$\r$\nid: $MinionName_State"  # write the minion config setting
        FileWrite $1 $cfg_line                          # write changed or unchanged line to temp file
    ${EndIf}                                            # close if statement

    FileClose $0                                        # close target file
    FileClose $1                                        # close temp file
    Delete "$INSTDIR\conf\minion"                       # delete target file
    CopyFiles /SILENT $R0 "$INSTDIR\conf\minion"        # copy temp file to target file
    Delete $R0                                          # delete temp file

FunctionEnd


Function parseCommandLineSwitches

    # Load the parameters
    ${GetParameters} $R0

    # Display Help
    ClearErrors
    ${GetOptions} $R0 "/?" $R1
    IfErrors display_help_not_found

        System::Call 'kernel32::GetStdHandle(i -11)i.r0'
        System::Call 'kernel32::AttachConsole(i -1)i.r1'
        ${If} $0 = 0
        ${OrIf} $1 = 0
            System::Call 'kernel32::AllocConsole()'
            System::Call 'kernel32::GetStdHandle(i -11)i.r0'
        ${EndIf}
        FileWrite $0 "$\n"
        FileWrite $0 "$\n"
        FileWrite $0 "Help for Salt Minion installation$\n"
        FileWrite $0 "===============================================================================$\n"
        FileWrite $0 "$\n"
        FileWrite $0 "/minion-name=$\t$\tA string value to set the minion name. Default value is$\n"
        FileWrite $0 "$\t$\t$\t'hostname'. Setting the minion name causes the installer$\n"
        FileWrite $0 "$\t$\t$\tto use the default config or a custom config if defined$\n"
        FileWrite $0 "$\n"
        FileWrite $0 "/master=$\t$\tA string value to set the IP address or hostname of the$\n"
        FileWrite $0 "$\t$\t$\tmaster. Default value is 'salt'. You may pass a single$\n"
        FileWrite $0 "$\t$\t$\tmaster or a comma-separated list of masters. Setting$\n"
        FileWrite $0 "$\t$\t$\tthe master will cause the installer to use the default$\n"
        FileWrite $0 "$\t$\t$\tconfig or a custom config if defined$\n"
        FileWrite $0 "$\n"
        FileWrite $0 "/start-minion=$\t$\t1 will start the minion service, 0 will not.$\n"
        FileWrite $0 "$\t$\t$\tDefault is 1$\n"
        FileWrite $0 "$\n"
        FileWrite $0 "/start-minion-delayed$\tSet the minion start type to 'Automatic (Delayed Start)'$\n"
        FileWrite $0 "$\n"
        FileWrite $0 "/default-config$\t$\tOverwrite the existing config if present with the$\n"
        FileWrite $0 "$\t$\t$\tdefault config for salt. Default is to use the existing$\n"
        FileWrite $0 "$\t$\t$\tconfig if present. If /master and/or /minion-name is$\n"
        FileWrite $0 "$\t$\t$\tpassed, those values will be used to update the new$\n"
        FileWrite $0 "$\t$\t$\tdefault config$\n"
        FileWrite $0 "$\n"
        FileWrite $0 "$\t$\t$\tAny existing config will be backed up by appending$\n"
        FileWrite $0 "$\t$\t$\ta timestamp and a .bak extension. That includes\n"
        FileWrite $0 "$\t$\t$\tthe minion file and the minion.d directory$\n"
        FileWrite $0 "$\n"
        FileWrite $0 "/custom-config=$\t$\tA string value specifying the name of a custom config$\n"
        FileWrite $0 "$\t$\t$\tfile in the same path as the installer or the full path$\n"
        FileWrite $0 "$\t$\t$\tto a custom config file. If /master and/or /minion-name$\n"
        FileWrite $0 "$\t$\t$\tis passed, those values will be used to update the new$\n"
        FileWrite $0 "$\t$\t$\tcustom config$\n"
        FileWrite $0 "$\n"
        FileWrite $0 "$\t$\t$\tAny existing config will be backed up by appending$\n"
        FileWrite $0 "$\t$\t$\ta timestamp and a .bak extension. That includes\n"
        FileWrite $0 "$\t$\t$\tthe minion file and the minion.d directory$\n"
        FileWrite $0 "$\n"
        FileWrite $0 "/S$\t$\t$\tInstall Salt silently$\n"
        FileWrite $0 "$\n"
        FileWrite $0 "/?$\t$\t$\tDisplay this help screen$\n"
        FileWrite $0 "$\n"
        FileWrite $0 "-------------------------------------------------------------------------------$\n"
        FileWrite $0 "$\n"
        FileWrite $0 "Examples:$\n"
        FileWrite $0 "$\n"
        FileWrite $0 "${OutFile} /S$\n"
        FileWrite $0 "$\n"
        FileWrite $0 "${OutFile} /S /minion-name=myminion /master=master.mydomain.com /start-minion-delayed$\n"
        FileWrite $0 "$\n"
        FileWrite $0 "===============================================================================$\n"
        FileWrite $0 "$\n"
        System::Free $0
        System::Free $1
        System::Call 'kernel32::FreeConsole()'

        # Give the user back the prompt
        !define VK_RETURN 0x0D ; Enter Key
        !define KEYEVENTF_EXTENDEDKEY 0x0001
        !define KEYEVENTF_KEYUP 0x0002
        System::Call "user32::keybd_event(i${VK_RETURN}, i0x45, i${KEYEVENTF_EXTENDEDKEY}|0, i0)"
        System::Call "user32::keybd_event(i${VK_RETURN}, i0x45, i${KEYEVENTF_EXTENDEDKEY}|${KEYEVENTF_KEYUP}, i0)"
        Abort

    display_help_not_found:

    # Set default value for Use Existing Config
    StrCpy $ConfigType_State "Existing Config"

    # Check for start-minion switches
    # /start-service is to be deprecated, so we must check for both
    ${GetOptions} $R0 "/start-service=" $R1
    ${GetOptions} $R0 "/start-minion=" $R2

    # Service: Start Salt Minion
    ${IfNot} $R2 == ""
        # If start-minion was passed something, then set it
        StrCpy $StartMinion $R2
    ${ElseIfNot} $R1 == ""
        # If start-service was passed something, then set StartMinion to that
        StrCpy $StartMinion $R1
    ${Else}
        # Otherwise default to 1
        StrCpy $StartMinion 1
    ${EndIf}

    # Service: Minion Startup Type Delayed
    ClearErrors
    ${GetOptions} $R0 "/start-minion-delayed" $R1
    IfErrors start_minion_delayed_not_found
        StrCpy $StartMinionDelayed 1
    start_minion_delayed_not_found:

    # Minion Config: Master IP/Name
    # If setting master, we don't want to use existing config
    ${GetOptions} $R0 "/master=" $R1
    ${IfNot} $R1 == ""
        StrCpy $MasterHost_State $R1
        StrCpy $ConfigType_State "Default Config"
    ${ElseIf} $MasterHost_State == ""
        StrCpy $MasterHost_State "salt"
    ${EndIf}

    # Minion Config: Minion ID
    # If setting minion id, we don't want to use existing config
    ${GetOptions} $R0 "/minion-name=" $R1
    ${IfNot} $R1 == ""
        StrCpy $MinionName_State $R1
        StrCpy $ConfigType_State "Default Config"
    ${ElseIf} $MinionName_State == ""
        StrCpy $MinionName_State "hostname"
    ${EndIf}

    # Use Default Config
    ${GetOptions} $R0 "/default-config" $R1
    IfErrors default_config_not_found
        StrCpy $ConfigType_State "Default Config"
    default_config_not_found:

    # Use Custom Config
    # Set default value for Use Custom Config
    StrCpy $CustomConfig_State ""
    # Existing config will get a `.bak` extension
    ${GetOptions} $R0 "/custom-config=" $R1
    ${IfNot} $R1 == ""
        # Custom Config was passed something, set it
        StrCpy $CustomConfig_State $R1
        StrCpy $ConfigType_State "Custom Config"
    ${EndIf}

FunctionEnd
