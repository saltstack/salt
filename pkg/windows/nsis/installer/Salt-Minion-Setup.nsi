!define PRODUCT_NAME "Salt Minion"
!define PRODUCT_PUBLISHER "SaltStack, Inc"
!define PRODUCT_WEB_SITE "http://saltproject.io"
!define PRODUCT_CALL_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\salt-call.exe"
!define PRODUCT_CP_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\salt-cp.exe"
!define PRODUCT_KEY_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\salt-key.exe"
!define PRODUCT_MASTER_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\salt-master.exe"
!define PRODUCT_MINION_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\salt-minion.exe"
!define PRODUCT_RUN_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\salt-run.exe"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define PRODUCT_UNINST_ROOT_KEY "HKLM"
!define /date TIME_STAMP "%Y-%m-%d-%H-%M-%S"

# Request admin rights
RequestExecutionLevel admin

# Import Libraries
!include "FileFunc.nsh"
!include "LogicLib.nsh"
!include "MoveFileFolder.nsh"
!include "MUI2.nsh"
!include "nsDialogs.nsh"
!include "StrFunc.nsh"
!include "WinMessages.nsh"
!include "WinVer.nsh"
!include "x64.nsh"
${StrLoc}
${StrStrAdv}

# Required by MoveFileFolder.nsh
!insertmacro Locate

# Get salt version from CLI argument /DSaltVersion
!ifdef SaltVersion
    !define PRODUCT_VERSION "${SaltVersion}"
!else
    !define PRODUCT_VERSION "Undefined Version"
!endif

# Get architecture from CLI argument /DPythonArchitecture
# Should be x64, AMD64, or x86
!ifdef PythonArchitecture
    !define PYTHON_ARCHITECTURE "${PythonArchitecture}"
!else
    # Default
    !define PYTHON_ARCHITECTURE "x64"
!endif

# Get Estimated Size from CLI argument /DEstimatedSize
!ifdef PythonArchitecture
    !define ESTIMATED_SIZE "${EstimatedSize}"
!else
    # Default
    !define ESTIMATED_SIZE 0
!endif

# x64 and AMD64 are AMD64, all others are x86
!if "${PYTHON_ARCHITECTURE}" == "x64"
    !define CPUARCH "AMD64"
!else if "${PYTHON_ARCHITECTURE}" == "AMD64"
    !define CPUARCH "AMD64"
!else
    !define CPUARCH "x86"
!endif

!define BUILD_TYPE "Python 3"
!define OUTFILE "Salt-Minion-${PRODUCT_VERSION}-Py3-${CPUARCH}-Setup.exe"

# Part of the Trim function for Strings
!define Trim "!insertmacro Trim"
!macro Trim ResultVar String
    Push "${String}"
    Call Trim
    Pop  "${ResultVar}"
!macroend

# Part of the Explode function for Strings
!define Explode "!insertmacro Explode"
!macro Explode Length Separator String
    Push "${Separator}"
    Push "${String}"
    Call Explode
    Pop  "${Length}"
!macroend

# Part of the StrContains function for Strings
!define StrContains "!insertmacro StrContains"
!macro StrContains OUT NEEDLE HAYSTACK
    Push "${HAYSTACK}"
    Push "${NEEDLE}"
    Call StrContains
    Pop  "${OUT}"
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

# Install location page
!define MUI_PAGE_CUSTOMFUNCTION_SHOW pageCheckExistingInstall
!insertmacro MUI_PAGE_DIRECTORY

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
Var MinionStart_ChkBox
Var MinionStartDelayed_ChkBox
Var MasterHost_Cfg
Var MasterHost_TxtBox
Var MasterHost
Var MinionName_Cfg
Var MinionName_TxtBox
Var MinionName
Var ExistingConfigFound
Var ConfigType_DropList
Var ConfigType
Var CustomConfig_TxtBox
Var CustomConfig_Btn
Var CustomConfig
Var CustomConfigWarning_Lbl
Var ExistingConfigWarning_Lbl
Var DefaultConfigWarning_Lbl
Var MoveExistingConfig_ChkBox
Var MoveExistingConfig
Var StartMinion
Var StartMinionDelayed
Var DeleteInstallDir
Var DeleteRootDir
Var ConfigWriteMinion
Var ConfigWriteMaster
# For new method installation
Var RegInstDir
Var RegRootDir
Var RootDir
Var SysDrive
Var ExistingInstallation
Var CustomLocation


###############################################################################
# Directory Picker Dialog Box
###############################################################################
Function pageCheckExistingInstall
    # If this is an Existing Installation we want to disable the directory
    # picker functionality
    # https://nsis-dev.github.io/NSIS-Forums/html/t-166727.html
    # Use the winspy tool (https://sourceforge.net/projects/winspyex/) to get
    # the Control ID for the items you want to disable
    # The Control ID is in the Details tab
    # It is a Hex value that needs to be converted to an integer
    ${If} $ExistingInstallation == 1
        # 32770 is Class name used by all NSIS dialog boxes
        FindWindow $R0 "#32770" "" $HWNDPARENT
        # 1019 is the Destination Folder text field (0x3FB)
        GetDlgItem $R1 $R0 1019
        EnableWindow $R1 0
        # 1001 is the Browse button (0x3E9)
        GetDlgItem $R1 $R0 1001
        EnableWindow $R1 0
        # Disabling the Location Picker causes the buttons to behave incorrectly
        # Esc and Enter don't work. Nor can you use Alt+N and Alt+B. Setting
        # the focus to the Next button seems to fix this
        # Set focus on Next button (0x1)
        # Next=1, cancel=2, back=3
        GetDlgItem $R1 $HWNDPARENT 1
        SendMessage $HWNDPARENT ${WM_NEXTDLGCTL} $R1 1
    ${EndIf}
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

    # Master IP or Hostname Dialog Control
    ${NSD_CreateLabel} 0 0 100% 9u "&Master IP or Hostname:"
    Pop $Label

    ${NSD_CreateText} 0 10u 100% 12u $MasterHost
    Pop $MasterHost_TxtBox

    # Minion ID Dialog Control
    ${NSD_CreateLabel} 0 30u 100% 9u "Minion &Name:"
    Pop $Label

    ${NSD_CreateText} 0 40u 100% 12u $MinionName
    Pop $MinionName_TxtBox

    # Config Drop List
    ${NSD_CreateDropList} 0 60u 25% 36u ""
    Pop $ConfigType_DropList
    ${NSD_CB_AddString} $ConfigType_DropList "Default Config"
    ${NSD_CB_AddString} $ConfigType_DropList "Custom Config"
    ${NSD_OnChange} $ConfigType_DropList pageMinionConfig_OnChange

    # Add Existing Config Warning Label
    ${NSD_CreateLabel} 0 75u 100% 50u \
        "The values above are taken from an existing configuration found in \
        `$RootDir\conf\minion`.$\n\
        $\n\
        Clicking `Install` will leave the existing config unchanged."
    Pop $ExistingConfigWarning_Lbl
    CreateFont $0 "Arial" 10 500 /ITALIC
    SendMessage $ExistingConfigWarning_Lbl ${WM_SETFONT} $0 1
    SetCtlColors $ExistingConfigWarning_Lbl 0xBB0000 transparent

    # Add Checkbox to move root_dir
    ${NSD_CreateCheckBox} 0 125u 100% 10u \
        "Move &existing root directory (C:\salt) to %ProgramData%\Salt."
    Pop $MoveExistingConfig_ChkBox
    CreateFont $0 "Arial" 10 500
    SendMessage $MoveExistingConfig_ChkBox ${WM_SETFONT} $0 1
    ${If} $MoveExistingConfig == 1
        ${NSD_Check} $MoveExistingConfig_ChkBox
    ${EndIf}

    # Add Default Config Warning Label
    ${NSD_CreateLabel} 0 75u 100% 60u "Clicking `Install` will backup the \
        existing minion config file and minion.d directories. The values \
        above will be used in the new default config.$\n\
        $\n\
        NOTE: If Master IP is set to `salt` and Minion Name is set to \
        `hostname` no changes will be made."
    Pop $DefaultConfigWarning_Lbl
    CreateFont $0 "Arial" 10 500 /ITALIC
    SendMessage $DefaultConfigWarning_Lbl ${WM_SETFONT} $0 1
    SetCtlColors $DefaultConfigWarning_Lbl 0xBB0000 transparent

    # Add Custom Config File Selector and Warning Label
    ${NSD_CreateText} 26% 60u 64% 12u $CustomConfig
    Pop $CustomConfig_TxtBox
    ${NSD_CreateButton} 91% 60u 9% 12u "..."
    Pop $CustomConfig_Btn
    ${NSD_OnClick} $CustomConfig_Btn pageCustomConfigBtn_OnClick

    ${If} $ExistingConfigFound == 0
        ${NSD_CreateLabel} 0 75u 100% 60u \
            "Values entered above will be used in the custom config.$\n\
            $\n\
            NOTE: If Master IP is set to `salt` and Minion Name is set to \
            `hostname` no changes will be made."
    ${Else}
        ${NSD_CreateLabel} 0 75u 100% 60u \
            "Clicking `Install` will backup the the existing minion config \
            file and minion.d directories. The values above will be used in \
            the custom config.$\n\
            $\n\
            NOTE: If Master IP is set to `salt` and Minion Name is set to \
            `hostname` no changes will be made."
    ${Endif}
    Pop $CustomConfigWarning_Lbl
    CreateFont $0 "Arial" 10 500 /ITALIC
    SendMessage $CustomConfigWarning_Lbl ${WM_SETFONT} $0 1
    SetCtlColors $CustomConfigWarning_Lbl 0xBB0000 transparent

    # If existing config found, add the Existing Config option to the Drop List
    # If not, hide the Default Warning
    ${If} $ExistingConfigFound == 1
        ${NSD_CB_AddString} $ConfigType_DropList "Existing Config"
    ${Else}
        ShowWindow $DefaultConfigWarning_Lbl ${SW_HIDE}
    ${Endif}

    ${NSD_CB_SelectString} $ConfigType_DropList $ConfigType
    ${NSD_SetText} $CustomConfig_TxtBox $CustomConfig

    Call pageMinionConfig_OnChange

    nsDialogs::Show

FunctionEnd


Function pageMinionConfig_OnChange

    # You have to pop the top handle to keep the stack clean
    Pop $R0

    # Assign the current checkbox state to the variable
    ${NSD_GetText} $ConfigType_DropList $ConfigType

    # Update Dialog
    ${Switch} $ConfigType
        ${Case} "Existing Config"
            # Enable Master/Minion and set values
            EnableWindow $MasterHost_TxtBox 0
            EnableWindow $MinionName_TxtBox 0
            ${NSD_SetText} $MasterHost_TxtBox $MasterHost_Cfg
            ${NSD_SetText} $MinionName_TxtBox $MinionName_Cfg
            # Hide Custom File Picker
            ShowWindow $CustomConfig_TxtBox ${SW_HIDE}
            ShowWindow $CustomConfig_Btn ${SW_HIDE}
            # Hide Warnings
            ShowWindow $DefaultConfigWarning_Lbl ${SW_HIDE}
            ShowWindow $CustomConfigWarning_Lbl ${SW_HIDE}
            # Show Existing Warning
            ShowWindow $ExistingConfigWarning_Lbl ${SW_SHOW}
            ${If} $RootDir == "C:\salt"
                ShowWindow $MoveExistingConfig_ChkBox ${SW_SHOW}
            ${Else}
                ShowWindow $MoveExistingConfig_ChkBox ${SW_HIDE}
            ${EndIf}
            ${Break}
        ${Case} "Custom Config"
            # Enable Master/Minion and set values
            EnableWindow $MasterHost_TxtBox 1
            EnableWindow $MinionName_TxtBox 1
            ${NSD_SetText} $MasterHost_TxtBox $MasterHost
            ${NSD_SetText} $MinionName_TxtBox $MinionName
            # Show Custom File Picker
            ShowWindow $CustomConfig_TxtBox ${SW_SHOW}
            ShowWindow $CustomConfig_Btn ${SW_SHOW}
            # Hide Warnings
            ShowWindow $DefaultConfigWarning_Lbl ${SW_HIDE}
            ShowWindow $ExistingConfigWarning_Lbl ${SW_HIDE}
            ShowWindow $MoveExistingConfig_ChkBox ${SW_HIDE}
            # Show Custom Warning
            ShowWindow $CustomConfigWarning_Lbl ${SW_SHOW}
            ${Break}
        ${Case} "Default Config"
            # Enable Master/Minion and set values
            EnableWindow $MasterHost_TxtBox 1
            EnableWindow $MinionName_TxtBox 1
            ${NSD_SetText} $MasterHost_TxtBox $MasterHost
            ${NSD_SetText} $MinionName_TxtBox $MinionName
            # Hide Custom File Picker
            ShowWindow $CustomConfig_TxtBox ${SW_HIDE}
            ShowWindow $CustomConfig_Btn ${SW_HIDE}
            # Hide Warnings
            ShowWindow $ExistingConfigWarning_Lbl ${SW_HIDE}
            ShowWindow $MoveExistingConfig_ChkBox ${SW_HIDE}
            ShowWindow $CustomConfigWarning_Lbl ${SW_HIDE}
            # Show Default Warning, if there is an existing config
            ${If} $ExistingConfigFound == 1
                ShowWindow $DefaultConfigWarning_Lbl ${SW_SHOW}
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
    ${NSD_GetText} $CustomConfig_TxtBox $2
    System::Call "*$1(&t${NSIS_MAX_STRLEN}r2)" ; Set lpstrFile to the old path (if any)

    # Open the dialog
    System::Call 'COMDLG32::GetOpenFileName(ir0)i.r2'

    # Get file name field
    ${If} $2 <> 0
        System::Call "*$1(&t${NSIS_MAX_STRLEN}.r2)"
        ${NSD_SetText} $CustomConfig_TxtBox $2
    ${EndIf}

    # Free resources
    System::Free $1
    System::Free $0

FunctionEnd


Function pageMinionConfig_Leave

    # Save the State
    ${NSD_GetText} $MasterHost_TxtBox $MasterHost
    ${NSD_GetText} $MinionName_TxtBox $MinionName
    ${NSD_GetText} $ConfigType_DropList $ConfigType
    ${NSD_GetText} $CustomConfig_TxtBox $CustomConfig
    ${NSD_GetState} $MoveExistingConfig_ChkBox $MoveExistingConfig

    # Abort if config file not found
    ${If} $ConfigType == "Custom Config"
        IfFileExists "$CustomConfig" done 0
            MessageBox MB_OK|MB_ICONEXCLAMATION \
                "File not found: $CustomConfig" \
                /SD IDOK
            Abort
    ${EndIf}

    ${If} $MoveExistingConfig == 1

        # This makes the $APPDATA variable point to the ProgramData folder
        # instead of the current user's roaming AppData folder
        SetShellVarContext all

        # Get directory status
        # We don't want to overwrite data in the new location, so it needs to
        # either be empty or not found. Otherwise, warn and abort
        ${DirState} "$APPDATA\Salt Project\Salt" $R0  # 0=Empty, 1=full, -1=Not Found
        StrCmp $R0 "1" 0 done # Move files if directory empty or missing
        MessageBox MB_OKCANCEL \
            "The $APPDATA\Salt Project\Salt directory is not empty.$\n\
            These files will need to be moved manually." \
            /SD IDOK IDCANCEL cancel
        # OK: We're continuing without moving existing config
        StrCpy $MoveExistingConfig 0
        Goto done

        cancel:
            # Cancel: We're unchecking the checkbox and returning the user to
            # the dialog box
            # Abort just returns the user back to the dialog box
            ${NSD_UNCHECK} $MoveExistingConfig_ChkBox
            Abort

    ${EndIf}

    done:

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
    Pop $MinionStart_ChkBox
    SetCtlColors $MinionStart_ChkBox "" "ffffff"
    # This command required to bring the checkbox to the front
    System::Call "User32::SetWindowPos(i, i, i, i, i, i, i) b ($MinionStart_ChkBox, ${HWND_TOP}, 0, 0, 0, 0, ${SWP_NOSIZE}|${SWP_NOMOVE})"

    # Create Start Minion Delayed ComboBox
    ${NSD_CreateCheckbox} 130u 102u 100% 12u "&Delayed Start"
    Pop $MinionStartDelayed_ChkBox
    SetCtlColors $MinionStartDelayed_ChkBox "" "ffffff"
    # This command required to bring the checkbox to the front
    System::Call "User32::SetWindowPos(i, i, i, i, i, i, i) b ($MinionStartDelayed_ChkBox, ${HWND_TOP}, 0, 0, 0, 0, ${SWP_NOSIZE}|${SWP_NOMOVE})"

    # Load current settings for Minion
    ${If} $StartMinion == 1
        ${NSD_Check} $MinionStart_ChkBox
    ${EndIf}

    # Load current settings for Minion Delayed
    ${If} $StartMinionDelayed == 1
        ${NSD_Check} $MinionStartDelayed_ChkBox
    ${EndIf}

FunctionEnd


Function pageFinish_Leave

    # Assign the current checkbox states
    ${NSD_GetState} $MinionStart_ChkBox $StartMinion
    ${NSD_GetState} $MinionStartDelayed_ChkBox $StartMinionDelayed

FunctionEnd


###############################################################################
# Installation Settings
###############################################################################
Name "${PRODUCT_NAME} ${PRODUCT_VERSION} (${BUILD_TYPE})"
OutFile "${OutFile}"
InstallDir "C:\Program Files\Salt Project\Salt"
InstallDirRegKey HKLM "${PRODUCT_DIR_REGKEY}" ""
ShowInstDetails show
ShowUnInstDetails show


Section -copy_prereqs
    # Copy prereqs to the Plugins Directory
    # These files are downloaded by build_pkg.bat
    # This directory gets removed upon completion
    SetOutPath "$PLUGINSDIR\"
    File /r "..\..\prereqs\"
SectionEnd

# Check if the Windows 10 Universal C Runtime (KB2999226) is installed. Python
# 3 needs the updated ucrt on Windows 8.1/2012R2 and lower. They are installed
# via KB2999226, but we're not going to patch the system here. Instead, we're
# going to copy the .dll files to the \salt\bin directory
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
    # UCRT only needed on Windows Server 2012R2/Windows 8.1 and below. The
    # first ReadRegStr command above should have skipped to lbl_done if on
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

    # Use RunningX64 here to get the Architecture for the system running the
    # installer.
    ${If} ${RunningX64}
        StrCpy $UcrtFileName "ucrt_x64.zip"
    ${Else}
        StrCpy $UcrtFileName "ucrt_x86.zip"
    ${EndIf}

    ClearErrors

    detailPrint "Unzipping UCRT dll files to $INSTDIR\Scripts"
    CreateDirectory $INSTDIR\Scripts
    nsisunz::UnzipToLog "$PLUGINSDIR\$UcrtFileName" "$INSTDIR\Scripts"

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

    # GUIDs can be found by installing them and then running the following
    # command:
    # wmic product where "Name like '%2013%minimum runtime%'" get Name, Version, IdentifyingNumber
    !define VCREDIST_X86_NAME "vcredist_x86_2013"
    !define VCREDIST_X86_GUID "{8122DAB1-ED4D-3676-BB0A-CA368196543E}"
    !define VCREDIST_X64_NAME "vcredist_x64_2013"
    !define VCREDIST_X64_GUID "{53CF6934-A98D-3D84-9146-FC4EDF3D5641}"

    # Only install 64bit VCRedist on 64bit machines
    # Use RunningX64 here to get the Architecture for the system running the
    # installer.
    ${If} ${RunningX64}
        StrCpy $VcRedistName ${VCREDIST_X64_NAME}
        StrCpy $VcRedistGuid ${VCREDIST_X64_GUID}
    ${Else}
        StrCpy $VcRedistName ${VCREDIST_X86_NAME}
        StrCpy $VcRedistGuid ${VCREDIST_X86_GUID}
    ${EndIf}

    # Detecting VCRedist Installation
    !define INSTALLSTATE_DEFAULT "5"

    StrCpy $NeedVcRedist "False"
    detailPrint "Checking for $VcRedistName..."
    System::Call "msi::MsiQueryProductStateA(t '$VcRedistGuid') i.r0"
    StrCmp $0 ${INSTALLSTATE_DEFAULT} +2 0
    StrCpy $NeedVcRedist "True"

    Call InstallVCRedist

SectionEnd


Function InstallVCRedist
    # Check to see if it's already installed
    ${If} $NeedVcRedist == "True"
        detailPrint "System requires $VcRedistName"
        MessageBox MB_ICONQUESTION|MB_YESNO|MB_DEFBUTTON2 \
            "$VcRedistName is currently not installed. Would you like to \
            install?" \
            /SD IDYES IDNO endVCRedist

        # If an output variable is specified ($0 in the case below), ExecWait
        # sets the variable with the exit code (and only sets the error flag if
        # an error occurs; if an error occurs, the contents of the user
        # variable are undefined).
        # http://nsis.sourceforge.net/Reference/ExecWait
        ClearErrors
        detailPrint "Installing $VcRedistName..."
        ExecWait '"$PLUGINSDIR\$VcRedistName.exe" /install /quiet /norestart' $0

        IfErrors 0 CheckVcRedistErrorCode

        detailPrint "An error occurred during installation of $VcRedistName"
        MessageBox MB_OK|MB_ICONEXCLAMATION \
            "$VcRedistName failed to install. Try installing the package \
            manually." \
            /SD IDOK

        CheckVcRedistErrorCode:
        # Check for Reboot Error Code (3010)
        ${If} $0 == 3010
            detailPrint "Reboot and run Salt install again"
            MessageBox MB_OK|MB_ICONINFORMATION \
                "$VcRedistName installed but requires a restart to complete." \
                /SD IDOK

        # Check for any other errors
        ${ElseIfNot} $0 == 0
            detailPrint "An error occurred during installation of $VcRedistName"
            detailPrint "Error: $0"
            MessageBox MB_OK|MB_ICONEXCLAMATION \
                "$VcRedistName failed with ErrorCode: $0. Try installing the \
                package manually." \
                /SD IDOK
        ${EndIf}

        endVCRedist:

    ${EndIf}

FunctionEnd


Section "MainSection" SEC01

    ${If} $MoveExistingConfig == 1
        # This makes the $APPDATA variable point to the ProgramData folder
        # instead of the current user's roaming AppData folder
        SetShellVarContext all

        detailPrint "Moving existing config to $APPDATA\Salt Project\Salt"
        # Make sure the target directory exists
        nsExec::Exec "md $APPDATA\Salt Project\Salt"
        # Take ownership of the C:\salt directory
        detailPrint "Taking ownership: $RootDir"
        nsExec::Exec "takeown /F $RootDir /R"
        # Move the C:\salt directory to the new location
        StrCpy $switch_overwrite 0
        detailPrint "Moving $RootDir to $APPDATA"
        IfFileExists "$RootDir\conf" 0 +2
        !insertmacro MoveFolder "$RootDir\conf" "$APPDATA\Salt Project\Salt\conf" "*.*"
        IfFileExists "$RootDir\srv" 0 +2
        !insertmacro MoveFolder "$RootDir\srv" "$APPDATA\Salt Project\Salt\srv" "*.*"
        IfFileExists "$RootDir\var" 0 +2
        !insertmacro MoveFolder "$RootDir\var" "$APPDATA\Salt Project\Salt\var" "*.*"
        # Make RootDir the new location
        StrCpy $RootDir "$APPDATA\Salt Project\Salt"
    ${EndIf}

    ${If} $ConfigType != "Existing Config"
        Call BackupExistingConfig
    ${EndIf}


    # Install files to the Installation Directory
    SetOutPath "$INSTDIR\"
    SetOverwrite off
    File /r "..\..\buildenv\"

    # Set up Root Directory
    CreateDirectory "$RootDir\conf\pki\minion"
    CreateDirectory "$RootDir\conf\minion.d"
    CreateDirectory "$RootDir\var\cache\salt\minion\extmods\grains"
    CreateDirectory "$RootDir\var\cache\salt\minion\proc"
    CreateDirectory "$RootDir\var\log\salt"
    CreateDirectory "$RootDir\var\run"
    nsExec::Exec 'icacls $RootDir /inheritance:r /grant:r "*S-1-5-32-544":(OI)(CI)F /grant:r "*S-1-5-18":(OI)(CI)F'

SectionEnd


Function .onInit
    # This function gets executed before any other. This is where we will
    # detect existing installations and config to be used by the installer

    # Make sure we do not allow 32-bit Salt on 64-bit systems
    # This is the system the installer is running on
    ${If} ${RunningX64}
        # This is the Python architecture the installer was built with
        ${If} ${CPUARCH} == "x86"
            MessageBox MB_OK|MB_ICONEXCLAMATION  \
                "Detected 64-bit Operating system.$\n$\n\
                Please install the 64-bit version of Salt on this operating system." \
                /SD IDOK
            Abort
        ${EndIf}
    ${Else}
        # This is the Python architecture the installer was built with
        ${If} ${CPUARCH} == "AMD64"
            MessageBox MB_OK|MB_ICONEXCLAMATION  \
                "Detected 32-bit Operating system.$\n$\n\
                Please install the 32-bit version of Salt on this operating system." \
                /SD IDOK
            Abort
        ${EndIf}
    ${EndIf}

    InitPluginsDir
    Call parseInstallerCommandLineSwitches

    # Uninstall msi-installed salt
    # Source: https://nsis-dev.github.io/NSIS-Forums/html/t-303468.html
    # TODO: Add a message box here confirming the uninstall of the MSI
    !define upgradecode {FC6FB3A2-65DE-41A9-AD91-D10A402BD641}  # Salt upgrade code
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

    # If a custom config is passed on the CLI, verify its existence before
    # continuing so we don't uninstall an existing installation and then fail
    # NOTE: This handles custom config for silent installations where the
    # NOTE: custom config is passed on the CLI. The GUI has its own checking
    # NOTE: when the user selects a custom config.
    ${If} $ConfigType == "Custom Config"
        IfFileExists "$CustomConfig" checkExistingInstallation 0
        Abort
    ${EndIf}

    checkExistingInstallation:
        # Check for existing installation

        # The NSIS installer is a 32bit application and will use the WOW6432Node
        # in the registry by default. We need to look in the 64 bit location on
        # 64 bit systems
        ${If} ${RunningX64}
            # https://nsis.sourceforge.io/Docs/Chapter4.html#setregview
            SetRegView 64  # View the 64 bit portion of the registry
        ${EndIf}

        ReadRegStr $R0 HKLM \
            "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
            "UninstallString"

        # Puts the nullsoft installer back to its default
        SetRegView 32  # Set it back to the 32 bit portion of the registry

        # If not found, look in 32 bit
        ${If} $R0 == ""
            ReadRegStr $R0 HKLM \
                "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                "UninstallString"
        ${EndIf}

        # If it's empty it's not installed
        StrCmp $R0 "" skipUninstall

        # Set InstDir to the parent directory so that we can uninstall it
        ${GetParent} $R0 $INSTDIR

        # Found existing installation, prompt to uninstall
        MessageBox MB_OKCANCEL|MB_USERICON \
            "${PRODUCT_NAME} is already installed.$\n$\n\
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

        # Don't remove all directories when upgrading (old method)
        StrCpy $DeleteInstallDir 0

        # Don't remove RootDir when upgrading (new method)
        StrCpy $DeleteRootDir 0

        # Uninstall silently
        Call uninstallSalt

        # Set it back to Normal mode, if that's what it was before
        ${If} $R0 == 0
            SetSilent normal
        ${EndIf}

    skipUninstall:

    Call getExistingInstallation

    Call getExistingMinionConfig

    ${If} $ExistingConfigFound == 0
    ${AndIf} $ConfigType == "Existing Config"
        StrCpy $ConfigType "Default Config"
    ${EndIf}

FunctionEnd


Function BackupExistingConfig

    ${If} $ExistingConfigFound == 1                     # If existing config found
    ${AndIfNot} $ConfigType == "Existing Config"  # If not using Existing Config

        # Backup the minion config
        Rename "$RootDir\conf\minion" "$RootDir\conf\minion-${TIME_STAMP}.bak"
        IfFileExists "$RootDir\conf\minion.d" 0 +2
            Rename "$RootDir\conf\minion.d" "$RootDir\conf\minion.d-${TIME_STAMP}.bak"

    ${EndIf}

    # By this point there should be no existing config. It was either backed up
    # or wasn't there to begin with
    ${If} $ConfigType == "Custom Config"  # If we're using Custom Config
    ${AndIfNot} $CustomConfig == ""       # If a custom config is passed

        # Check for a file name
        # Named file should be in the same directory as the installer
        CreateDirectory "$RootDir\conf"
        IfFileExists "$EXEDIR\$CustomConfig" 0 checkFullPath
            CopyFiles /SILENT /FILESONLY "$EXEDIR\$CustomConfig" "$RootDir\conf\minion"
            goto finished

        # Maybe it was a full path to a file
        checkFullPath:
        IfFileExists "$CustomConfig" 0 finished
            CopyFiles /SILENT /FILESONLY "$CustomConfig" "$RootDir\conf\minion"

        finished:

    ${EndIf}

FunctionEnd


Section -Post

    WriteUninstaller "$INSTDIR\uninst.exe"

    # The NSIS installer is a 32bit application and will use the WOW6432Node in
    # the registry by default. We need to look in the 64 bit location on 64 bit
    # systems
    ${If} ${RunningX64}
        # https://nsis.sourceforge.io/Docs/Chapter4.html#setregview
        SetRegView 64  # View 64 bit portion of the registry
    ${EndIf}

    # Write Uninstall Registry Entries
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

    # If ESTIMATED_SIZE is not set, calculated it
    ${If} ${ESTIMATED_SIZE} == 0
        ${GetSize} "$INSTDIR" "/S=OK" $0 $1 $2
    ${Else}
        StrCpy $0 ${ESTIMATED_SIZE}
    ${Endif}
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" \
        "EstimatedSize" "$0"

    # Write Commandline Registry Entries
    WriteRegStr HKLM "${PRODUCT_CALL_REGKEY}" "" "$INSTDIR\salt-call.exe"
    WriteRegStr HKLM "${PRODUCT_CALL_REGKEY}" "Path" "$INSTDIR\"
    WriteRegStr HKLM "${PRODUCT_MINION_REGKEY}" "" "$INSTDIR\salt-minion.exe"
    WriteRegStr HKLM "${PRODUCT_MINION_REGKEY}" "Path" "$INSTDIR\"

    # Write Salt Configuration Registry Entries
    # We want to write EXPAND_SZ string types to allow us to use environment
    # variables. It's OK to use EXPAND_SZ even if you don't use an environment
    # variable so we'll just do that whether it's new location or old.

    # Check for Program Files
    # Set the current setting for INSTDIR... we'll only change it if it contains
    # Program Files
    StrCpy $RegInstDir $INSTDIR

    # Program Files
    # We want to use the environment variables instead of the hardcoded path
    ${StrContains} $0 "Program Files" $INSTDIR
    StrCmp $0 "" +2  # If it's empty, skip the next line
        StrCpy $RegInstDir "%ProgramFiles%\Salt Project\Salt"

    # Check for ProgramData
    # Set the current setting for RootDir. we'll only change it if it contains
    # ProgramData
    StrCpy $RegRootDir $RootDir

    # We want to use the environment variables instead of the hardcoded path
    ${StrContains} $0 "ProgramData" $RootDir
    StrCmp $0 "" +2  # If it's empty, skip the next line
        StrCpy $RegRootDir "%ProgramData%\Salt Project\Salt"

    WriteRegExpandStr HKLM "SOFTWARE\Salt Project\Salt" "install_dir" "$RegInstDir"
    WriteRegExpandStr HKLM "SOFTWARE\Salt Project\Salt" "root_dir" "$RegRootDir"

    # Puts the nullsoft installer back to its default
    SetRegView 32  # Set it back to the 32 bit portion of the registry

    # Register the Salt-Minion Service
    nsExec::Exec `$INSTDIR\ssm.exe install salt-minion "$INSTDIR\salt-minion.exe" -c """$RootDir\conf""" -l quiet`
    nsExec::Exec "$INSTDIR\ssm.exe set salt-minion Description Salt Minion from saltstack.com"
    nsExec::Exec "$INSTDIR\ssm.exe set salt-minion Start SERVICE_AUTO_START"
    nsExec::Exec "$INSTDIR\ssm.exe set salt-minion AppStopMethodConsole 24000"
    nsExec::Exec "$INSTDIR\ssm.exe set salt-minion AppStopMethodWindow 2000"
    nsExec::Exec "$INSTDIR\ssm.exe set salt-minion AppRestartDelay 60000"

    # There is a default minion config laid down in the $INSTDIR directory
    ${Switch} $ConfigType
        ${Case} "Existing Config"
            # If this is an Existing Config, we don't do anything
            ${Break}
        ${Case} "Custom Config"
            # If this is a Custom Config, update the custom config
            Call updateMinionConfig
            ${Break}
        ${Case} "Default Config"
            # If this is the Default Config, we move it and update it
            StrCpy $switch_overwrite 1

            !insertmacro MoveFolder "$INSTDIR\configs" "$RootDir\conf" "*.*"
            Call updateMinionConfig
            ${Break}
    ${EndSwitch}

    # Delete the configs directory that came with the installer
    RMDir /r "$INSTDIR\configs"

    # Add $INSTDIR in the Path
    EnVar::SetHKLM
    EnVar::AddValue Path "$INSTDIR"

SectionEnd


Function .onInstSuccess

    # If StartMinionDelayed is 1, then set the service to start delayed
    ${If} $StartMinionDelayed == 1
        nsExec::Exec "$INSTDIR\ssm.exe set salt-minion Start SERVICE_DELAYED_AUTO_START"
    ${EndIf}

    # If start-minion is 1, then start the service
    ${If} $StartMinion == 1
        nsExec::Exec 'net start salt-minion'
    ${EndIf}

FunctionEnd


Function un.onInit

    Call un.parseUninstallerCommandLineSwitches

    MessageBox MB_USERICON|MB_YESNO|MB_DEFBUTTON1 \
        "Are you sure you want to completely remove $(^Name) and all of its \
        components?" \
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

    # WARNING: Any changes made here need to be reflected in the MSI uninstaller
    # Make sure we're in the right directory
    ${If} $INSTDIR == "c:\salt\Scripts"
      StrCpy $INSTDIR "C:\salt"
    ${EndIf}
    # $ProgramFiles is different depending on the CPU Architecture
    # https://nsis.sourceforge.io/Reference/$PROGRAMFILES
    # x86 : C:\Program Files
    # x64 : C:\Program Files (x86)
    ${If} $INSTDIR == "$ProgramFiles\Salt Project\Salt\Scripts"
      StrCpy $INSTDIR "$ProgramFiles\Salt Project\Salt"
    ${EndIf}
    # $ProgramFiles64 is the C:\Program Files directory
    ${If} $INSTDIR == "$ProgramFiles64\Salt Project\Salt\Scripts"
      StrCpy $INSTDIR "$ProgramFiles64\Salt Project\Salt"
    ${EndIf}

    # Stop and Remove salt-minion service
    nsExec::Exec "net stop salt-minion"
    nsExec::Exec "sc delete salt-minion"

    # Stop and remove the salt-master service
    nsExec::Exec "net stop salt-master"
    nsExec::Exec "sc delete salt-master"

    # We need to make sure the service is stopped and removed before deleting
    # any files
    StrCpy $0 1  # Tries
    StrCpy $1 1  # Service Present
    loop:
        detailPrint "Verifying salt-minion deletion: try $0"
        nsExec::ExecToStack 'net start | FIND /C /I "salt-minion"'
        pop $2  # First on the stack is the return code
        pop $1  # Next on the stack is standard out (service present)
        ${If} $1 == 1
            ${If} $0 < 5
                IntOp $0 $0 + 1
                Sleep 1000
                goto loop
            ${Else}
                MessageBox MB_OK|MB_ICONEXCLAMATION \
                    "Failed to remove salt-minion service" \
                    /SD IDOK
                Abort
            ${EndIf}
        ${EndIf}

    # Remove files
    Delete "$INSTDIR\uninst.exe"
    Delete "$INSTDIR\ssm.exe"
    Delete "$INSTDIR\salt*"
    Delete "$INSTDIR\vcredist.exe"
    RMDir /r "$INSTDIR\DLLs"
    RMDir /r "$INSTDIR\Include"
    RMDir /r "$INSTDIR\Lib"
    RMDir /r "$INSTDIR\libs"
    RMDir /r "$INSTDIR\Scripts"

    # Remove everything in the 64 bit registry

    # The NSIS installer is a 32bit application and will use the WOW6432Node in
    # the registry by default. We need to look in the 64 bit location on 64 bit
    # systems
    ${If} ${RunningX64}
        # https://nsis.sourceforge.io/Docs/Chapter4.html#setregview
        SetRegView 64  # View the 64 bit portion of the registry

        # Get Root Directory from the Registry (64 bit)
        ReadRegStr $RootDir HKLM "SOFTWARE\Salt Project\Salt" "root_dir"

        # Remove Registry entries
        DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}"

        # Remove Command Line Registry entries
        DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_CALL_REGKEY}"
        DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_CP_REGKEY}"
        DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_KEY_REGKEY}"
        DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_MASTER_REGKEY}"
        DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_MINION_REGKEY}"
        DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_RUN_REGKEY}"
        DeleteRegKey HKLM "SOFTWARE\Salt Project"
    ${EndIf}

    # Remove everything in the 32 bit registry
    SetRegView 32  # Set it to 32 bit

    ${If} $RootDir == ""
        # Get Root Directory from the Registry (32 bit)
        ReadRegStr $RootDir HKLM "SOFTWARE\Salt Project\Salt" "root_dir"
    ${EndIf}

    # Remove Registry entries
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}"

    # Remove Command Line Registry entries
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_CALL_REGKEY}"
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_CP_REGKEY}"
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_KEY_REGKEY}"
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_MASTER_REGKEY}"
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_MINION_REGKEY}"
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_RUN_REGKEY}"
    DeleteRegKey HKLM "SOFTWARE\Salt Project"

    # SystemDrive is not a built in NSIS constant, so we need to get it from
    # the environment variables
    ReadEnvStr $0 "SystemDrive"  # Get the SystemDrive env var
    StrCpy $SysDrive "$0\"

    # Automatically close when finished
    SetAutoClose true

    # Old Method Installation
    ${If} $INSTDIR == "C:\salt"

        # Prompt to remove the Installation Directory. This is because that
        # directory is also the root_dir which includes the config and pki
        # directories
        ${IfNot} $DeleteInstallDir == 1
            MessageBox MB_YESNO|MB_DEFBUTTON2|MB_USERICON \
                "Would you like to completely remove $INSTDIR and all of its contents?" \
                /SD IDNO IDNO finished
        ${EndIf}

        SetOutPath "$SysDrive"  # Can't remove CWD
        RMDir /r "$INSTDIR"

    ${Else}

        # New Method Installation
        # This makes the $APPDATA variable point to the ProgramData folder instead
        # of the current user's roaming AppData folder
        SetShellVarContext all

        # We can always remove the Installation Directory on New Method Installs
        # because it only contains binary data

        # Remove INSTDIR
        # Make sure you're not removing important system directory such as
        # Program Files, C:\Windows, or C:
        ${If} $INSTDIR != $ProgramFiles
        ${AndIf} $INSTDIR != $ProgramFiles64
        ${AndIf} $INSTDIR != $SysDrive
        ${AndIf} $INSTDIR != $WinDir
            SetOutPath "$SysDrive"  # Can't remove CWD
            RMDir /r $INSTDIR
        ${EndIf}

        # Remove INSTDIR (The parent)
        # For example, though salt is installed in ProgramFiles\Salt Project\Salt
        # We want to remove ProgramFiles\Salt Project
        # Only delete Salt Project directory if it's in Program Files
        # Otherwise, we can't guess where the user may have installed salt
        ${GetParent} $INSTDIR $0  # Get parent directory (Salt Project)
        ${If} $0 == "$ProgramFiles\Salt Project" # Make sure it's not ProgramFiles
        ${OrIf} $0 == "$ProgramFiles64\Salt Project" # Make sure it's not Program Files (x86)
            SetOutPath "$SysDrive"  # Can't remove CWD
            RMDir /r $0
        ${EndIf}

        # If RootDir is still empty, use C:\salt
        ${If} $RootDir == ""
            StrCpy $RootDir "C:\salt"
        ${EndIf}

        # Expand any environment variables
        ExpandEnvStrings $RootDir $RootDir

        # Prompt for the removal of the Root Directory which contains the config
        # and pki directories
        ${IfNot} $DeleteRootDir == 1
            MessageBox MB_YESNO|MB_DEFBUTTON2|MB_USERICON \
                "Would you like to completely remove the Root Directory \
                ($RootDir) and all of its contents?" \
                /SD IDNO IDNO finished
        ${EndIf}

        # Remove the Salt Project directory in ProgramData
        # The Salt Project directory will only ever be in ProgramData
        # It is not user selectable
        ${GetParent} $RootDir $0  # Get parent directory
        ${If} $0 == "$APPDATA\Salt Project"  # Make sure it's not ProgramData
            SetOutPath "$SysDrive"  # Can't remove CWD
            RMDir /r $0
        ${EndIf}

    ${EndIf}

    finished:

FunctionEnd
!macroend


!insertmacro uninstallSalt ""
!insertmacro uninstallSalt "un."


Function un.onUninstSuccess
    HideWindow
    MessageBox MB_OK|MB_USERICON \
        "$(^Name) was successfully removed from your computer." \
        /SD IDOK
FunctionEnd


###############################################################################
# Helper Functions
###############################################################################

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
# StrContains
#
# This function does a case sensitive searches for an occurrence of a substring in a string.
# It returns the substring if it is found.
# Otherwise it returns null("").
# Written by kenglish_hi
# Adapted from StrReplace written by dandaman32
#------------------------------------------------------------------------------
Function StrContains

    # Initialize variables
    Var /GLOBAL STR_HAYSTACK
    Var /GLOBAL STR_NEEDLE
    Var /GLOBAL STR_CONTAINS_VAR_1
    Var /GLOBAL STR_CONTAINS_VAR_2
    Var /GLOBAL STR_CONTAINS_VAR_3
    Var /GLOBAL STR_CONTAINS_VAR_4
    Var /GLOBAL STR_RETURN_VAR

    Exch $STR_NEEDLE
    Exch 1
    Exch $STR_HAYSTACK
    # Uncomment to debug
    #MessageBox MB_OK 'STR_NEEDLE = $STR_NEEDLE STR_HAYSTACK = $STR_HAYSTACK '
    StrCpy $STR_RETURN_VAR ""
    StrCpy $STR_CONTAINS_VAR_1 -1
    StrLen $STR_CONTAINS_VAR_2 $STR_NEEDLE
    StrLen $STR_CONTAINS_VAR_4 $STR_HAYSTACK

    loop:
        IntOp $STR_CONTAINS_VAR_1 $STR_CONTAINS_VAR_1 + 1
        StrCpy $STR_CONTAINS_VAR_3 $STR_HAYSTACK $STR_CONTAINS_VAR_2 $STR_CONTAINS_VAR_1
        StrCmp $STR_CONTAINS_VAR_3 $STR_NEEDLE found
        StrCmp $STR_CONTAINS_VAR_1 $STR_CONTAINS_VAR_4 done
        Goto loop

    found:
        StrCpy $STR_RETURN_VAR $STR_NEEDLE
        Goto done

    done:
        Pop $STR_NEEDLE  # Prevent "invalid opcode" errors and keep the stack clean
        Exch $STR_RETURN_VAR
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
    MessageBox MB_OKCANCEL|MB_ICONINFORMATION \
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

Function getExistingInstallation
    # Try to detect an existing installation. There are three possible scenarios
    # 1. Existing New Method Installation
    # 2. Existing Old Method Installation
    # 3. New Installation
    # The results of this function will determine if the user is allowed to set
    # the install location in the GUI. If there is an existing installation
    # present, the location picker will be grayed out
    # This function also sets the RootDir and INSTDIR variables used by the
    # installer.

    # Reset ExistingInstallation
    StrCpy $ExistingInstallation 0

    # Get ProgramFiles
    # Use RunningX64 here to get the Architecture for the system running the
    # installer.
    # There are 3 scenarios here:
    ${If} ${RunningX64}
        StrCpy $INSTDIR "$ProgramFiles64\Salt Project\Salt"
    ${Else}
        # 32 bit Salt on 32 bit system (C:\Program Files)
        StrCpy $INSTDIR "$ProgramFiles\Salt Project\Salt"
    ${EndIf}

    # This makes the $APPDATA variable point to the ProgramData folder instead
    # of the current user's roaming AppData folder
    SetShellVarContext all

    # Set default location of for salt config
    StrCpy $RootDir "$APPDATA\Salt Project\Salt"

    # The NSIS installer is a 32bit application and will use the WOW6432Node in
    # the registry by default. We need to look in the 64 bit location on 64 bit
    # systems
    ${If} ${RunningX64}
        # https://nsis.sourceforge.io/Docs/Chapter4.html#setregview
        SetRegView 64  # View the 64 bit portion of the registry
    ${EndIf}

    # Check for existing new method installation from registry
    # Look for `install_dir` in HKLM\SOFTWARE\Salt Project\Salt
    ReadRegStr $R0 HKLM "SOFTWARE\Salt Project\Salt" "install_dir"
    StrCmp $R0 "" checkOldInstallation
    StrCpy $ExistingInstallation 1

    # Set INSTDIR to the location in the registry
    StrCpy $INSTDIR $R0
    # Expand any environment variables it contains
    ExpandEnvStrings $INSTDIR $INSTDIR

    # Set RootDir, if defined
    ReadRegStr $R0 HKLM "SOFTWARE\Salt Project\Salt" "root_dir"
    StrCmp $R0 "" finished
    StrCpy $RootDir $R0
    # Expand any environment variables it contains
    ExpandEnvStrings $RootDir $RootDir
    Goto finished

    # Check for existing old method installation
    # Look for `python.exe` in C:\salt\bin
    checkOldInstallation:
        IfFileExists "C:\salt\bin\python.exe" 0 newInstallation
        StrCpy $ExistingInstallation 1
        StrCpy $INSTDIR "C:\salt"
        StrCpy $RootDir "C:\salt"
        Goto finished

    # This is a new installation
    # Check if custom location was passed via command line
    newInstallation:
        ${IfNot} $CustomLocation == ""
            StrCpy $INSTDIR $CustomLocation
        ${EndIf}

    finished:
        SetRegView 32  # View the 32 bit portion of the registry

FunctionEnd


Function getExistingMinionConfig

    # Set Config Found Default Value
    StrCpy $ExistingConfigFound 0

    # Find config, should be in $RootDir\conf\minion
    # Root dir is usually ProgramData\Salt Project\Salt\conf though it may be
    # C:\salt\conf if Salt was installed the old way

    IfFileExists "$RootDir\conf\minion" check_owner
    IfFileExists "C:\salt\conf\minion" old_location confNotFound

    old_location:
    StrCpy $RootDir "C:\salt"

    check_owner:
        # We need to verify the owner of the config directory (C:\salt\conf) to
        # ensure the config has not been modified by an unknown user. The
        # permissions and ownership of the directories is determined by the
        # installer used to install Salt. The NullSoft installer requests Admin
        # privileges so all directories are created with the Administrators
        # Group (S-1-5-32-544) as the owner. The MSI installer, however, runs in
        # the context of the Windows Installer service (msiserver), therefore
        # all directories are created with the Local System account (S-1-5-18)
        # as the owner.
        #
        # When Salt is launched it sets the root_dir (C:\salt) permissions as
        # follows:
        # - Owner: Administrators
        # - Allow Perms:
        #   - Owner: Full Control
        #   - System: Full Control
        #   - Administrators: Full Control
        #
        # The conf_dir (C:\salt\conf) inherits Allow/Deny permissions from the
        # parent, but NOT Ownership. The owner will be the Administrators Group
        # if it was installed via NullSoft or the Local System account if it was
        # installed via the MSI. Therefore valid owners for the conf_dir are
        # both the Administrators group and the Local System account.
        #
        # An unprivileged account cannot change the owner of a directory by
        # default. So, if the owner of the conf_dir is either the Administrators
        # group or the Local System account, then we will trust it. Otherwise,
        # we will display an option to abort the installation or to backup the
        # untrusted config directory and continue with the default config. If
        # running the install with the silent option (/S) it will backup the
        # untrusted config directory and continue with the default config.

        AccessControl::GetFileOwner /SID "$RootDir\conf"
        Pop $0

        # Check for valid SIDs
        StrCmp $0 "S-1-5-32-544" correct_owner  # Administrators Group (NullSoft)
        StrCmp $0 "S-1-5-18" correct_owner      # Local System (MSI)
        MessageBox MB_YESNO \
                "Insecure config found at $RootDir\conf. If you continue, the \
                config directory will be renamed to $RootDir\conf.insecure \
                and the default config will be used. Continue?" \
                /SD IDYES IDYES insecure_config
            Abort

    insecure_config:
        # Backing up insecure config
        Rename "$RootDir\conf" "$RootDir\conf.insecure-${TIME_STAMP}"
        Goto confNotFound

    correct_owner:
        StrCpy $ExistingConfigFound 1
        FileOpen $0 "$RootDir\conf\minion" r

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
                    ${If} $MasterHost_Cfg == ""                 # if the config setting is empty
                        StrCpy $MasterHost_Cfg $2               # make the first item the new entry
                    ${Else}
                        StrCpy $MasterHost_Cfg "$MasterHost_Cfg,$2"  # Append the new master, comma separated
                    ${EndIf}
                    Goto masterLoop                             # check the next one
                ${EndIf}
            ${Else}
                StrCpy $MasterHost_Cfg $2                       # a single master entry
            ${EndIf}
        ${EndIf}

        ${StrLoc} $2 $1 "id:" ">"
        ${If} $2 == 0
            ${StrStrAdv} $2 $1 "id: " ">" ">" "0" "0" "0"
            ${Trim} $2 $2
            StrCpy $MinionName_Cfg $2
        ${EndIf}

    Goto confLoop

    EndOfFile:
    FileClose $0

    confNotFound:

    # Set Default Config Values if not found
    ${If} $MasterHost_Cfg == ""
        StrCpy $MasterHost_Cfg "salt"
    ${EndIf}
    ${If} $MinionName_Cfg == ""
        StrCpy $MinionName_Cfg "hostname"
    ${EndIf}

FunctionEnd


Var cfg_line
Var chk_line
Var lst_check
Function updateMinionConfig

    ClearErrors
    FileOpen $0 "$RootDir\conf\minion" "r"              # open target file for reading
    GetTempFileName $R0                                 # get new temp file name
    FileOpen $1 $R0 "w"                                 # open temp file for writing

    StrCpy $ConfigWriteMaster 1                         # write the master config value
    StrCpy $ConfigWriteMinion 1                         # write the minion config value

    loop:                                               # loop through each line
        FileRead $0 $cfg_line                           # read line from target file
        IfErrors done                                   # end if errors are encountered (end of line)

        loop_after_read:
        StrCpy $lst_check 0                             # list check not performed

        ${If} $MasterHost == ""                         # if master is empty
        ${OrIf} $MasterHost == "salt"                   # or if master is 'salt'
            StrCpy $ConfigWriteMaster 0                 # no need to write master config
        ${EndIf}                                        # close if statement
        ${If} $MinionName == ""                         # if minion is empty
        ${OrIf} $MinionName == "hostname"               # and if minion is not 'hostname'
            StrCpy $ConfigWriteMinion 0                 # no need to write minion config
        ${EndIf}                                        # close if statement

        ${If} $ConfigWriteMaster == 1                   # if we need to write master config

            ${StrLoc} $3 $cfg_line "master:" ">"        # where is 'master:' in this line
            ${If} $3 == 0                               # is it in the first...
            ${OrIf} $3 == 1                             # or second position (account for comments)

                ${Explode} $9 "," $MasterHost           # Split the hostname on commas, $9 is the number of items found
                ${If} $9 == 1                           # 1 means only a single master was passed
                    StrCpy $cfg_line "master: $MasterHost$\r$\n"  # write the master
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
                StrCpy $cfg_line "id: $MinionName$\r$\n"  # write the minion config setting
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

        ${Explode} $9 "," $MasterHost                   # split the hostname on commas, $9 is the number of items found
        ${If} $9 == 1                                   # 1 means only a single master was passed
            StrCpy $cfg_line "master: $MasterHost"      # write the master
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
        StrCpy $cfg_line "$\r$\nid: $MinionName"        # write the minion config setting
        FileWrite $1 $cfg_line                          # write changed or unchanged line to temp file
    ${EndIf}                                            # close if statement

    FileClose $0                                        # close target file
    FileClose $1                                        # close temp file
    Delete "$RootDir\conf\minion"                       # delete target file
    CopyFiles /SILENT $R0 "$RootDir\conf\minion"        # copy temp file to target file
    Delete $R0                                          # delete temp file

FunctionEnd


Function un.parseUninstallerCommandLineSwitches

    # Load the parameters
    ${GetParameters} $R0

    # Display Help
    ClearErrors
    ${GetOptions} $R0 "/?" $R1
    IfErrors display_un_help_not_found

    # Using a message box here
    # I couldn't get the console output to work with the uninstaller
    MessageBox MB_OK \
        "Help for Salt Minion Uninstallation\
        $\n\
        $\n==============================================\
        $\n\
        $\n/delete-install-dir$\tDelete the installation directory that contains the\
        $\n$\t$\tconfig and pki directories. Default is to not delete\
        $\n$\t$\tthe installation directory\
        $\n\
        $\n$\t$\tThis applies to old method installations where\
        $\n$\t$\tthe root directory and the installation directory\
        $\n$\t$\tare the same (C:\salt)\
        $\n\
        $\n/delete-root-dir$\tDelete the root directory that contains the config\
        $\n$\t$\tand pki directories. Default is to not delete the root\
        $\n$\t$\tdirectory\
        $\n\
        $\n$\t$\tThis applies to new method installations where the\
        $\n$\t$\troot directory is in ProgramData and the installation\
        $\n$\t$\tdirectory is user defined, usually Program Files\
        $\n\
        $\n/S$\t$\tUninstall Salt silently\
        $\n\
        $\n/?$\t$\tDisplay this help screen\
        $\n\
        $\n--------------------------------------------------------------------------------------------\
        $\n\
        $\nExamples:\
        $\n\
        $\n$\tuninst.exe /S\
        $\n\
        $\n$\tuninst.exe /S /delete-root-dir\
        $\n\
        $\n=============================================="

        Abort

    display_un_help_not_found:

    # Load the parameters
    ${GetParameters} $R0

    # Uninstaller: Remove Installation Directory
    ClearErrors
    ${GetOptions} $R0 "/delete-install-dir" $R1
    IfErrors delete_install_dir_not_found
    StrCpy $DeleteInstallDir 1
    delete_install_dir_not_found:

    # Uninstaller: Remove Root Directory
    ClearErrors
    ${GetOptions} $R0 "/delete-root-dir" $R1
    IfErrors delete_root_dir_not_found
    StrCpy $DeleteRootDir 1
    delete_root_dir_not_found:

FunctionEnd


Function parseInstallerCommandLineSwitches

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
    FileWrite $0 "$\t$\t$\ta timestamp and a .bak extension. That includes$\n"
    FileWrite $0 "$\t$\t$\tthe minion file and the minion.d directory$\n"
    FileWrite $0 "$\n"
    FileWrite $0 "/custom-config=$\t$\tA string value specifying the name of a custom config$\n"
    FileWrite $0 "$\t$\t$\tfile in the same path as the installer or the full path$\n"
    FileWrite $0 "$\t$\t$\tto a custom config file. If /master and/or /minion-name$\n"
    FileWrite $0 "$\t$\t$\tis passed, those values will be used to update the new$\n"
    FileWrite $0 "$\t$\t$\tcustom config$\n"
    FileWrite $0 "$\n"
    FileWrite $0 "$\t$\t$\tAny existing config will be backed up by appending$\n"
    FileWrite $0 "$\t$\t$\ta timestamp and a .bak extension. That includes$\n"
    FileWrite $0 "$\t$\t$\tthe minion file and the minion.d directory$\n"
    FileWrite $0 "$\n"
    FileWrite $0 "/install-dir=$\t$\tSpecify the installation location for the Salt binaries.$\n"
    FileWrite $0 "$\t$\t$\tThis will be ignored for existing installations.$\n"
    FileWrite $0 "$\n"
    FileWrite $0 "/move-config$\t$\tIf config is found at C:\salt it will be moved to %ProgramData%$\n"
    FileWrite $0 "$\n"
    FileWrite $0 "/S$\t$\t$\tInstall Salt silently$\n"
    FileWrite $0 "$\n"
    FileWrite $0 "/?$\t$\t$\tDisplay this help screen$\n"
    FileWrite $0 "$\n"
    FileWrite $0 "-------------------------------------------------------------------------------$\n"
    FileWrite $0 "$\n"
    FileWrite $0 "Examples:$\n"
    FileWrite $0 "$\n"
    FileWrite $0 "    $EXEFILE /S$\n"
    FileWrite $0 "$\n"
    FileWrite $0 "    $EXEFILE /S /minion-name=myminion /master=master.mydomain.com /start-minion-delayed$\n"
    FileWrite $0 "$\n"
    FileWrite $0 "    $EXEFILE /S /minion-name=myminion /master=master.mydomain.com /install-dir=$\"C:\Software\salt$\"$\n"
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
    StrCpy $ConfigType "Existing Config"

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
        MessageBox MB_OK|MB_ICONINFORMATION \
            "`/start-service` is being deprecated. Please use `/start-minion` \
            instead." /SD IDOK
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
        StrCpy $MasterHost $R1
        StrCpy $ConfigType "Default Config"
    ${ElseIf} $MasterHost == ""
        StrCpy $MasterHost "salt"
    ${EndIf}

    # Minion Config: Minion ID
    # If setting minion id, we don't want to use existing config
    ${GetOptions} $R0 "/minion-name=" $R1
    ${IfNot} $R1 == ""
        StrCpy $MinionName $R1
        StrCpy $ConfigType "Default Config"
    ${ElseIf} $MinionName == ""
        StrCpy $MinionName "hostname"
    ${EndIf}

    # Use Default Config
    ClearErrors
    ${GetOptions} $R0 "/default-config" $R1
    IfErrors default_config_not_found
    StrCpy $ConfigType "Default Config"
    default_config_not_found:

    # Use Custom Config
    # Set default value for Use Custom Config
    StrCpy $CustomConfig ""
    # Existing config will get a `.bak` extension
    ${GetOptions} $R0 "/custom-config=" $R1
    ${IfNot} $R1 == ""
        # A Custom Config was passed, set it
        StrCpy $CustomConfig $R1
        StrCpy $ConfigType "Custom Config"
    ${EndIf}

    # Set Install Location
    ClearErrors
    ${GetOptions} $R0 "/install-dir=" $R1
    ${IfNot} $R1 == ""
        # A Custom Location was passed, set it
        StrCpy $CustomLocation $R1
    ${EndIf}

    # Set Move Config Option
    ClearErrors
    ${GetOptions} $R0 "/move-config" $R1
    IfErrors move_config_not_found
    StrCpy $MoveExistingConfig 1
    move_config_not_found:

FunctionEnd
