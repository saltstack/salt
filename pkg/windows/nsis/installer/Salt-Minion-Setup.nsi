# This file must be UNICODE

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

# Request admin rights
RequestExecutionLevel admin

# Import Libraries
!include "FileFunc.nsh"
!include "helper_StrContains.nsh"
!include "LogicLib.nsh"
!include "MoveFileFolder.nsh"
!include "MUI2.nsh"
!include "nsDialogs.nsh"
!include "StrFunc.nsh"
!include "WinMessages.nsh"
!include "WinVer.nsh"
!include "x64.nsh"
${StrLoc}
${StrRep}
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
!ifdef EstimatedSize
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

VIProductVersion "1.0.0.0"  # This actually updates File Version
VIAddVersionKey FileVersion "1.0.0.0"  # This doesn't seem to do anything, but you'll get a warning without it
VIAddVersionKey "ProductName" "${PRODUCT_NAME}"
VIAddVersionKey "LegalTrademarks" "${PRODUCT_NAME} is a trademark of ${PRODUCT_PUBLISHER}"
VIAddVersionKey "LegalCopyright" "© ${PRODUCT_PUBLISHER}"
VIAddVersionKey "FileDescription" "${PRODUCT_NAME} Installer"
VIAddVersionKey "ProductVersion" "${PRODUCT_VERSION}"

################################################################################
# Early defines
################################################################################

!define Trim "!insertmacro Trim"
!macro Trim ResultVar String
    Push "${String}"
    !ifdef __UNINSTALL__
        Call un.Trim
    !else
        Call Trim
    !endif
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

# Variables for Logging
Var LogFile
Var TimeStamp
Var cmdLineParams
var logFileHandle
Var msg

# Followed this: https://nsis.sourceforge.io/StrRep
!define LogMsg '!insertmacro LogMsg'
!macro LogMsg _msg
    Push "${_msg}"
    !ifdef __UNINSTALL__
        Call un.LogMsg
    !else
        Call LogMsg
    !endif
!macroend
!macro Func_LogMsg un
    Function ${un}LogMsg
        Pop $msg
        ${If} $TimeStamp == ""
            ${GetTime} "" "L" $0 $1 $2 $3 $4 $5 $6
            StrCpy $TimeStamp "$2-$1-$0_$4-$5-$6"
        ${EndIf}
        ${If} $LogFile == ""
            !ifdef __UNINSTALL__
                StrCpy $LogFile "$TEMP\SaltInstaller\$TimeStamp-uninstall.log"
            !else
                StrCpy $LogFile "$TEMP\SaltInstaller\$TimeStamp-install.log"
            !endif
            ${IfNot} ${FileExists} "$TEMP\SaltInstaller\*.*"
                CreateDirectory "$TEMP\SaltInstaller"
            ${EndIf}
        ${EndIf}
        ${Trim} $msg $msg
        DetailPrint "$msg"
        FileOpen $logFileHandle "$LogFile" a
        FileSeek $logFileHandle 0 END
        FileWrite $logFileHandle "$msg$\r$\n"
        FileClose $logFileHandle
    FunctionEnd
!macroend
!insertmacro Func_LogMsg ""
!insertmacro Func_LogMsg "un."


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
Var SSMBin
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

Section "Install" Install01

    ${If} $MoveExistingConfig == 1
        ${LogMsg} "Moving existing config to $APPDATA\Salt Project\Salt"

        # This makes the $APPDATA variable point to the ProgramData folder
        # instead of the current user's roaming AppData folder
        ${LogMsg} "Set context to all users"
        SetShellVarContext all

        # Make sure the target directory exists
        ${LogMsg} "Creating rootdir in ProgramData"
        CreateDirectory "$APPDATA\Salt Project\Salt"

        # Take ownership of the C:\salt directory
        ${LogMsg} "Taking ownership: $RootDir"
        nsExec::ExecToStack "takeown /F $RootDir /R"
        pop $0  # ExitCode
        pop $1  # StdOut
        ${If} $0 == 0
            ${LogMsg} "Success"
        ${Else}
            ${LogMsg} "Failed"
            ${LogMsg} "ExitCode: $0"
            ${LogMsg} "StdOut: $1"
        ${EndIf}
        # Move the C:\salt directory to the new location
        StrCpy $switch_overwrite 0
        ${If} ${FileExists} "$RootDir\conf\*.*"
            ${LogMsg} "Moving $RootDir\conf to $APPDATA"
            !insertmacro MoveFolder "$RootDir\conf" "$APPDATA\Salt Project\Salt\conf" "*.*"
        ${EndIf}
        ${If} ${FileExists} "$RootDir\srv\*.*"
            ${LogMsg} "Moving $RootDir\srv to $APPDATA"
            !insertmacro MoveFolder "$RootDir\srv" "$APPDATA\Salt Project\Salt\srv" "*.*"
        ${EndIf}
        ${If} ${FileExists} "$RootDir\var\*.*"
            ${LogMsg} "Moving $RootDir\var to $APPDATA"
            !insertmacro MoveFolder "$RootDir\var" "$APPDATA\Salt Project\Salt\var" "*.*"
        ${EndIf}
        # Make RootDir the new location
        StrCpy $RootDir "$APPDATA\Salt Project\Salt"
    ${EndIf}

    ${If} $ConfigType != "Existing Config"
        Call BackupExistingConfig
    ${EndIf}

    # Install files to the Installation Directory
    ${LogMsg} "Setting outpath to $INSTDIR"
    SetOutPath "$INSTDIR\"
    ${LogMsg} "Setting Overwrite off"
    SetOverwrite off
    ${LogMsg} "Copying files"
    File /r "..\..\buildenv\"

    # Set up Root Directory
    ${LogMsg} "Creating directory structure"
    CreateDirectory "$RootDir\conf\pki\minion"
    CreateDirectory "$RootDir\conf\minion.d"
    CreateDirectory "$RootDir\var\cache\salt\minion\extmods\grains"
    CreateDirectory "$RootDir\var\cache\salt\minion\proc"
    CreateDirectory "$RootDir\var\log\salt"
    CreateDirectory "$RootDir\var\run"

    ${LogMsg} "Setting permissions on RootDir"
    nsExec::ExecToStack 'icacls "$RootDir" /inheritance:r /grant:r "*S-1-5-32-544":(OI)(CI)F /grant:r "*S-1-5-18":(OI)(CI)F'
    pop $0  # ExitCode
    pop $1  # StdOut
    ${If} $0 == 0
        ${LogMsg} "Success"
    ${Else}
        ${LogMsg} "Failed"
        ${LogMsg} "ExitCode: $0"
        ${LogMsg} "StdOut: $1"
    ${EndIf}

SectionEnd


Function .onInit
    # This function gets executed before any other. This is where we will
    # detect existing installations and config to be used by the installer

    ${LogMsg} "Running ${OUTFILE}"

    # Make sure we do not allow 32-bit Salt on 64-bit systems
    # This is the system the installer is running on
    ${If} ${RunningX64}
        # This is the Python architecture the installer was built with
        ${If} ${CPUARCH} == "x86"
            StrCpy $msg "Detected 64-bit Operating system.$\n\
                Please install the 64-bit version of Salt on this operating system."
            ${LogMsg} $msg
            MessageBox MB_OK|MB_ICONEXCLAMATION $msg /SD IDOK
            ${LogMsg} "Aborting"
            Abort
        ${EndIf}
    ${Else}
        # This is the Python architecture the installer was built with
        ${If} ${CPUARCH} == "AMD64"
            StrCpy $msg "Detected 32-bit Operating system.$\n\
                Please install the 32-bit version of Salt on this operating system."
            ${LogMsg} $msg
            MessageBox MB_OK|MB_ICONEXCLAMATION $msg /SD IDOK
            ${LogMsg} "Aborting"
            Abort
        ${EndIf}
    ${EndIf}

    Call parseInstallerCommandLineSwitches

    # Uninstall msi-installed salt
    # Source: https://nsis-dev.github.io/NSIS-Forums/html/t-303468.html
    !define upgradecode {FC6FB3A2-65DE-41A9-AD91-D10A402BD641}  # Salt upgrade code
    StrCpy $0 0
    ${LogMsg} "Looking for MSI installation"
    loop:
    System::Call 'MSI::MsiEnumRelatedProducts(t "${upgradecode}",i0,i r0,t.r1)i.r2'
    ${If} $2 = 0
        # Now $1 contains the product code
        ${LogMsg} product:$1
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
        ${LogMsg} "Verifying custom config"
        ${If} ${FileExists} "$CustomConfig"
            ${LogMsg} "Found full path to custom config: $CustomConfig"
            Goto checkExistingInstallation
        ${EndIf}
        ${If} ${FileExists} "$EXEDIR\$CustomConfig"
            ${LogMsg} "Found custom config with the install binary: $CustomConfig"
            Goto checkExistingInstallation
        ${EndIf}
        ${LogMsg} "Custom config not found. Aborting"
        Abort
    ${EndIf}

    checkExistingInstallation:
        # Check for existing installation
        ${LogMsg} "Checking for existing installation"

        # The NSIS installer is a 32bit application and will use the WOW6432Node
        # in the registry by default. We need to look in the 64 bit location on
        # 64 bit systems
        ${If} ${RunningX64}

            ${LogMsg} "Setting registry context to 64-bit"
            # https://nsis.sourceforge.io/Docs/Chapter4.html#setregview
            SetRegView 64  # View the 64 bit portion of the registry

            ${LogMsg} "Reading uninstall string"
            ReadRegStr $R0 HKLM \
                "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                "UninstallString"

            # Puts the nullsoft installer back to its default
            ${LogMsg} "Setting registry context to 32-bit"
            SetRegView 32  # Set it back to the 32 bit portion of the registry

        ${Else}

            ${LogMsg} "Reading uninstall string"
            ReadRegStr $R0 HKLM \
                "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" \
                "UninstallString"

        ${EndIf}

        # If it's empty it's not installed
        StrCmp $R0 "" skipUninstall

        # Set InstDir to the parent directory so that we can uninstall it
        ${GetParent} $R0 $INSTDIR

        ${LogMsg} "Found existing installation at $R0"

        # Found existing installation, prompt to uninstall
        StrCpy $msg "${PRODUCT_NAME} is already installed.$\n\
           Click `OK` to remove the existing installation."
        ${LogMsg} $msg
        MessageBox MB_OKCANCEL|MB_USERICON $msg /SD IDOK IDOK uninst
        ${LogMsg} "Aborting"
        Abort

    uninst:

        # Maybe try running the uninstaller first

        # Get current Silent status
       ${LogMsg} "Getting current silent setting"
        StrCpy $R0 0
        ${If} ${Silent}
            StrCpy $R0 1
        ${EndIf}

        # Turn on Silent mode
        ${LogMsg} "Setting to silent mode"
        SetSilent silent

        # Don't remove all directories when upgrading (old method)
        ${LogMsg} "Setting uninstaller to not delete the install dir"
        StrCpy $DeleteInstallDir 0

        # Don't remove RootDir when upgrading (new method)
        ${LogMsg} "Setting uninstaller to not delete the root dir"
        StrCpy $DeleteRootDir 0

        # Uninstall silently
        Call uninstallSalt

       ${LogMsg} "Resetting silent setting to original"
        # Set it back to Normal mode, if that's what it was before
        ${If} $R0 == 0
            SetSilent normal
        ${EndIf}

    skipUninstall:

    Call getExistingInstallation

    Call getExistingMinionConfig

    ${If} $ExistingConfigFound == 0
    ${AndIf} $ConfigType == "Existing Config"
        ${LogMsg} "Existing config not found, using Default config"
        StrCpy $ConfigType "Default Config"
    ${EndIf}

FunctionEnd


Function BackupExistingConfig

    ${If} $ExistingConfigFound == 1               # If existing config found
    ${AndIfNot} $ConfigType == "Existing Config"  # If not using Existing Config

        # Backup the minion config
        ${If} ${FileExists} "$RootDir\conf\minion"
            ${LogMsg} "Renaming existing config file"
            Rename "$RootDir\conf\minion" "$RootDir\conf\minion-$TimeStamp.bak"
        ${EndIf}

        ${If} ${FileExists} "$RootDir\conf\minion.d\*.*"
            ${LogMsg} "Renaming existing config directory"
            Rename "$RootDir\conf\minion.d" "$RootDir\conf\minion.d-$TimeStamp.bak"
        ${EndIf}

    ${EndIf}

    # By this point there should be no existing config. It was either backed up
    # or wasn't there to begin with
    ${If} $ConfigType == "Custom Config"  # If we're using Custom Config
    ${AndIfNot} $CustomConfig == ""       # If a custom config is passed

        # Check for a file name
        # Named file should be in the same directory as the installer
        ${LogMsg} "Make sure config directory is exists"
        ${LogMsg} "Path: $RootDir\conf"
        CreateDirectory "$RootDir\conf"

        ${If} ${FileExists} "$EXEDIR\$CustomConfig"
            ${LogMsg} "Copying custom config from path relative to installer"
            ${LogMsg} "Path: $EXEDIR\$CustomConfig"
            CopyFiles /SILENT /FILESONLY "$EXEDIR\$CustomConfig" "$RootDir\conf\minion"
        ${ElseIf} ${FileExists} "$CustomConfig"
            ${LogMsg} "Copying custom config from full path"
            ${LogMsg} "Path: $CustomConfig"
            CopyFiles /SILENT /FILESONLY "$CustomConfig" "$RootDir\conf\minion"
        ${Else}
            ${LogMsg} "Custom config not found, default values will be used"
        ${EndIf}

    ${EndIf}

FunctionEnd


Section -Post

    ${LogMsg} "Writing uninstaller"
    WriteUninstaller "$INSTDIR\uninst.exe"

    # The NSIS installer is a 32bit application and will use the WOW6432Node in
    # the registry by default. We need to look in the 64 bit location on 64 bit
    # systems
    ${If} ${RunningX64}
        # https://nsis.sourceforge.io/Docs/Chapter4.html#setregview
        ${LogMsg} "Setting registry context to 64-bit registry"
        SetRegView 64  # View 64 bit portion of the registry
    ${EndIf}

    ${LogMsg} "Updating installation information in the registry"
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

    ${LogMsg} "Getting estimated size"
    # If ESTIMATED_SIZE is not set, calculated it
    ${If} ${ESTIMATED_SIZE} == 0
        ${GetSize} "$INSTDIR" "/S=OK" $R0 $R1 $R2
    ${Else}
        StrCpy $R0 ${ESTIMATED_SIZE}
    ${Endif}
    IntFmt $R0 "0x%08X" $R0
    ${LogMsg} "Setting estimated size: $R0"
    WriteRegDWORD ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" \
        "EstimatedSize" "$R0"

    # Write Commandline Registry Entries
    ${LogMsg} "Registering salt commands for the cli"
    WriteRegStr HKLM "${PRODUCT_CALL_REGKEY}" "" "$INSTDIR\salt-call.exe"
    WriteRegStr HKLM "${PRODUCT_CALL_REGKEY}" "Path" "$INSTDIR\"
    WriteRegStr HKLM "${PRODUCT_MINION_REGKEY}" "" "$INSTDIR\salt-minion.exe"
    WriteRegStr HKLM "${PRODUCT_MINION_REGKEY}" "Path" "$INSTDIR\"

    # Write Salt Configuration Registry Entries
    # We want to write EXPAND_SZ string types to allow us to use environment
    # variables. It's OK to use EXPAND_SZ even if you don't use an environment
    # variable so we'll just do that whether it's new location or old.

    # Check for Program Files
    # We want to use the environment variables instead of the hardcoded path
    # when setting values in the registry
    ${LogMsg} "Getting registry values for install_dir and root_dir"
    ${If} ${RunningX64}
        ${StrRep} "$RegInstDir" "$INSTDIR" "$ProgramFiles64" "%PROGRAMFILES%"
    ${Else}
        ${StrRep} "$RegInstDir" "$INSTDIR" "$ProgramFiles" "%PROGRAMFILES%"
    ${EndIf}
    ${LogMsg} "install_dir: $RegInstDir"
    SetShellVarContext all
    ${StrRep} "$RegRootDir" "$RootDir" "$APPDATA" "%PROGRAMDATA%"
    ${LogMsg} "root_dir: $RegRootDir"

    ${LogMsg} "Writing install_dir and root_dir to the registry"
    WriteRegExpandStr HKLM "SOFTWARE\Salt Project\Salt" "install_dir" "$RegInstDir"
    WriteRegExpandStr HKLM "SOFTWARE\Salt Project\Salt" "root_dir" "$RegRootDir"

    # Puts the nullsoft installer back to its default
    ${LogMsg} "Setting registry context back to 32-bit"
    SetRegView 32  # Set it back to the 32 bit portion of the registry

    # Register the Salt-Minion Service
    ${LogMsg} "Registering the salt-minion service"
    nsExec::ExecToStack `"$INSTDIR\ssm.exe" install salt-minion "$INSTDIR\salt-minion.exe" -c """$RootDir\conf""" -l quiet`
    pop $0  # ExitCode
    pop $1  # StdOut
    ${IfNot} $0 == 0
        StrCpy $msg "Failed to register the salt minion service.$\n\
            ExitCode: $0$\n\
            StdOut: $1"
        ${LogMsg} $msg
        MessageBox MB_OK|MB_ICONEXCLAMATION $msg /SD IDOK IDOK
        ${LogMsg} "Aborting"
        Abort
    ${Else}
        ${LogMsg} "Setting service description"
        nsExec::ExecToStack "$INSTDIR\ssm.exe set salt-minion Description Salt Minion from saltstack.com"
        pop $0  # ExitCode
        pop $1  # StdOut
        ${If} $0 == 0
            ${LogMsg} "Success"
        ${Else}
            ${LogMsg} "Failed"
            ${LogMsg} "ExitCode: $0"
            ${LogMsg} "StdOut: $1"
        ${EndIf}
        ${LogMsg} "Setting service autostart"
        nsExec::ExecToStack "$INSTDIR\ssm.exe set salt-minion Start SERVICE_AUTO_START"
        pop $0  # ExitCode
        pop $1  # StdOut
        ${If} $0 == 0
            ${LogMsg} "Success"
        ${Else}
            ${LogMsg} "Failed"
            ${LogMsg} "ExitCode: $0"
            ${LogMsg} "StdOut: $1"
        ${EndIf}
        ${LogMsg} "Setting service console stop method"
        nsExec::ExecToStack "$INSTDIR\ssm.exe set salt-minion AppStopMethodConsole 24000"
        pop $0  # ExitCode
        pop $1  # StdOut
        ${If} $0 == 0
            ${LogMsg} "Success"
        ${Else}
            ${LogMsg} "Failed"
            ${LogMsg} "ExitCode: $0"
            ${LogMsg} "StdOut: $1"
        ${EndIf}
        ${LogMsg} "Setting service windows stop method"
        nsExec::ExecToStack "$INSTDIR\ssm.exe set salt-minion AppStopMethodWindow 2000"
        pop $0  # ExitCode
        pop $1  # StdOut
        ${If} $0 == 0
            ${LogMsg} "Success"
        ${Else}
            ${LogMsg} "Failed"
            ${LogMsg} "ExitCode: $0"
            ${LogMsg} "StdOut: $1"
        ${EndIf}
        ${LogMsg} "Setting service app restart delay"
        nsExec::ExecToStack "$INSTDIR\ssm.exe set salt-minion AppRestartDelay 60000"
        pop $0  # ExitCode
        pop $1  # StdOut
        ${If} $0 == 0
            ${LogMsg} "Success"
        ${Else}
            ${LogMsg} "Failed"
            ${LogMsg} "ExitCode: $0"
            ${LogMsg} "StdOut: $1"
        ${EndIf}
    ${EndIf}

    # There is a default minion config laid down in the $INSTDIR directory
    ${Switch} $ConfigType
        ${Case} "Existing Config"
            ${LogMsg} "Using existing config"
            # If this is an Existing Config, we don't do anything
            ${Break}
        ${Case} "Custom Config"
            ${LogMsg} "Using custom config"
            # If this is a Custom Config, update the custom config
            Call updateMinionConfig
            ${Break}
        ${Case} "Default Config"
            ${LogMsg} "Using default config"
            # If this is the Default Config, we move it and update it
            StrCpy $switch_overwrite 1
            !insertmacro MoveFolder "$INSTDIR\configs" "$RootDir\conf" "*.*"
            Call updateMinionConfig
            ${Break}
    ${EndSwitch}

    # Delete the configs directory that came with the installer
    ${LogMsg} "Removing configs directory"
    RMDir /r "$INSTDIR\configs"

    # Add $INSTDIR in the Path
    ${LogMsg} "Adding salt to the path"
    EnVar::SetHKLM
    EnVar::AddValue Path "$INSTDIR"
    Pop $0
    ${If} $0 == 0
        ${LogMsg} "Success"
    ${Else}
        # See this table for Error Codes:
        # https://github.com/GsNSIS/EnVar#error-codes
        ${LogMsg} "Failed"
        ${LogMsg} "Error Code: $0"
        ${LogMsg} "Lookup error codes here:"
        ${LogMsg} "https://github.com/GsNSIS/EnVar#error-codes"
    ${EndIf}

SectionEnd


Function .onInstSuccess

    # If StartMinionDelayed is 1, then set the service to start delayed
    ${If} $StartMinionDelayed == 1
        ${LogMsg} "Setting the salt-minion service to start delayed"
        nsExec::ExecToStack "$INSTDIR\ssm.exe set salt-minion Start SERVICE_DELAYED_AUTO_START"
        pop $0  # ExitCode
        pop $1  # StdOut
        ${If} $0 == 0
            ${LogMsg} "Success"
        ${Else}
            ${LogMsg} "Failed"
            ${LogMsg} "ExitCode: $0"
            ${LogMsg} "StdOut: $1"
        ${EndIf}
    ${EndIf}

    # If start-minion is 1, then start the service
    ${If} $StartMinion == 1
        ${LogMsg} "Starting the salt-minion service"
        nsExec::ExecToStack "$INSTDIR\ssm.exe start salt-minion"
        pop $0  # ExitCode
        pop $1  # StdOut
        ${If} $0 == 0
            ${LogMsg} "Success"
        ${Else}
            ${LogMsg} "Failed"
            ${LogMsg} "ExitCode: $0"
            ${LogMsg} "StdOut: $1"
        ${EndIf}
    ${EndIf}

    ${LogMsg} "Salt installation complete"

    # I don't know of another way to fix this. The installer hangs intermittently
    # This will force kill the installer process. This must be the last thing that
    # is run.
    StrCpy $1 "wmic Path win32_process where $\"name like '$EXEFILE'$\" Call Terminate"
    nsExec::Exec $1

FunctionEnd


Function un.onInit

    Call un.parseUninstallerCommandLineSwitches

    StrCpy $msg "Are you sure you want to completely remove $(^Name) and all \
        of its components?"
    ${LogMsg} $msg
    MessageBox MB_USERICON|MB_YESNO|MB_DEFBUTTON1 $msg /SD IDYES IDYES continue_remove
    ${LogMsg} "Aborting"
    Abort

    continue_remove:

FunctionEnd


Section Uninstall

    Call un.uninstallSalt

    # Remove $INSTDIR from the Path
    ${LogMsg} "Removing salt from the path"
    EnVar::SetHKLM
    EnVar::DeleteValue Path "$INSTDIR"
    Pop $0
    ${If} $0 == 0
        ${LogMsg} "Success"
    ${Else}
        # See this table for Error Codes:
        # https://github.com/GsNSIS/EnVar#error-codes
        ${LogMsg} "Failed"
        ${LogMsg} "Error Code: $0"
        ${LogMsg} "Lookup error codes here:"
        ${LogMsg} "https://github.com/GsNSIS/EnVar#error-codes"
    ${EndIf}

SectionEnd


!macro uninstallSalt un
Function ${un}uninstallSalt

    # WARNING: Any changes made here need to be reflected in the MSI uninstaller
    # Make sure we're in the right directory
    ${LogMsg} "Detecting INSTDIR"
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
    ${LogMsg} "INSTDIR: $INSTDIR"

    # Only attempt to remove the services if ssm.exe is present"

    # 3006(Relenv)/3007 Salt Installations
    ${LogMsg} "Looking for ssm.exe for 3006+: $INSTDIR\ssm.exe"
    IfFileExists "$INSTDIR\ssm.exe" 0 v3004
        StrCpy $SSMBin "$INSTDIR\ssm.exe"
        goto foundSSM

    v3004:
    # 3004/3005(Tiamat) Salt Installations
    ${LogMsg} "Looking for ssm.exe for 3004+: $INSTDIR\bin\ssm.exe"
    IfFileExists "$INSTDIR\bin\ssm.exe" 0 v2018
        StrCpy $SSMBin "$INSTDIR\bin\ssm.exe"
        goto foundSSM

    v2018:
    # 2018.3/2019.2/3000/3001/3002/3003 and below Salt Installations
    ${LogMsg} "Looking for ssm.exe for 2018.3+: C:\salt\bin\ssm.exe"
    IfFileExists "C:\salt\bin\ssm.exe" 0 v2016
        StrCpy $SSMBin "C:\salt\bin\ssm.exe"
        goto foundSSM

    v2016:
    # 2016.11/2017.7 Salt Installations used nssm.exe
    ${LogMsg} "Looking for ssm.exe for 2016.11+: C:\salt\nssm.exe"
    IfFileExists "C:\salt\nssm.exe" 0 v2016
        StrCpy $SSMBin "C:\salt\nssm.exe"
        goto foundSSM

    ${LogMsg} "ssm.exe/nssm.exe not found"
    goto doneSSM

    foundSSM:

    ${LogMsg} "ssm.exe found: $SSMBin"

    # Detect if the salt-minion service is installed
    ${LogMsg} "Detecting salt-minion service"
    nsExec::ExecToStack "$SSMBin Status salt-minion"
    pop $0  # ExitCode
    pop $1  # StdOut
    ${If} $0 == 0
        ${LogMsg} "Service found"
    ${Else}
        # If the service is already gone, skip the SSM commands
        ${StrContains} $2 $1 "service does not exist"
        StrCmp $2 "" doneSSM
        ${LogMsg} "Failed"
        ${LogMsg} "ExitCode: $0"
        ${LogMsg} "StdOut: $1"
    ${EndIf}

    # Stop and Remove salt-minion service
    ${LogMsg} "Stopping salt-minion service"
    nsExec::ExecToStack "$SSMBin stop salt-minion"
    pop $0  # ExitCode
    pop $1  # StdOut
    ${If} $0 == 0
        ${LogMsg} "Success"
    ${Else}
        ${LogMsg} "Failed"
        ${LogMsg} "ExitCode: $0"
        ${LogMsg} "StdOut: $1"
    ${EndIf}

    ${LogMsg} "Removing salt-minion service"
    nsExec::ExecToStack "$SSMBin remove salt-minion confirm"
    pop $0  # ExitCode
    pop $1  # StdOut
    ${If} $0 == 0
        ${LogMsg} "Success"
    ${Else}
        ${LogMsg} "Failed"
        ${LogMsg} "ExitCode: $0"
        ${LogMsg} "StdOut: $1"
        Abort
    ${EndIf}

    doneSSM:

    # Remove files
    ${LogMsg} "Deleting files"
    ClearErrors
    ${LogMsg} "Deleting files: $INSTDIR\multi-minion*"
    Delete "$INSTDIR\multi-minion*"
    IfErrors 0 saltFiles
    ${LogMsg} "FAILED"

    saltFiles:
    ClearErrors
    ${LogMsg} "Deleting files: $INSTDIR\salt*"
    Delete "$INSTDIR\salt*"
    IfErrors 0 ssmBin
    ${LogMsg} "FAILED"

    ssmBin:
    ClearErrors
    ${LogMsg} "Deleting file: $SSMBin"
    Delete "$SSMBin"
    IfErrors 0 uninstBin
    ${LogMsg} "FAILED"

    uninstBin:
    ClearErrors
    ${LogMsg} "Deleting file: $INSTDIR\uninst.exe"
    Delete "$INSTDIR\uninst.exe"
    IfErrors 0 vcredistBin
    ${LogMsg} "FAILED"

    vcredistBin:
    ClearErrors
    ${LogMsg} "Deleting file: $INSTDIR\vcredist.exe"
    Delete "$INSTDIR\vcredist.exe"
    IfErrors 0 removeDirs
    ${LogMsg} "FAILED"

    removeDirs:
    ${LogMsg} "Deleting directories"

    ClearErrors
    ${LogMsg} "Deleting directory: $INSTDIR\DLLS"
    RMDir /r "$INSTDIR\DLLs"
    IfErrors 0 removeInclude
    ${LogMsg} "FAILED"

    removeInclude:
    ClearErrors
    ${LogMsg} "Deleting directory: $INSTDIR\Include"
    RMDir /r "$INSTDIR\Include"
    IfErrors 0 removeLib
    ${LogMsg} "FAILED"

    removeLib:
    ClearErrors
    ${LogMsg} "Deleting directory: $INSTDIR\Lib"
    RMDir /r "$INSTDIR\Lib"
    IfErrors 0 removeLibs
    ${LogMsg} "FAILED"

    removeLibs:
    ClearErrors
    ${LogMsg} "Deleting directory: $INSTDIR\libs"
    RMDir /r "$INSTDIR\libs"
    IfErrors 0 removeScripts
    ${LogMsg} "FAILED"

    removeScripts:
    ClearErrors
    ${LogMsg} "Deleting directory: $INSTDIR\Scripts"
    RMDir /r "$INSTDIR\Scripts"  # Relenv puts bins in Scripts
    IfErrors 0 removeBin
    ${LogMsg} "FAILED"

    removeBin:
    ClearErrors
    ${LogMsg} "Deleting directory: $INSTDIR\bin"
    RMDir /r "$INSTDIR\bin"      # Older versions use bin
    IfErrors 0 removeConfigs
    ${LogMsg} "FAILED"

    removeConfigs:
    ClearErrors
    ${LogMsg} "Deleting directory: $INSTDIR\configs"
    RMDir /r "$INSTDIR\configs"  # Sometimes this gets left behind
    IfErrors 0 removeDone
    ${LogMsg} "FAILED"

    removeDone:

    # Remove everything in the 64 bit registry

    # The NSIS installer is a 32bit application and will use the WOW6432Node in
    # the registry by default. We need to look in the 64 bit location on 64 bit
    # systems
    ${If} ${RunningX64}

        ${LogMsg} "Removing 64-bit registry items"
        # https://nsis.sourceforge.io/Docs/Chapter4.html#setregview
        SetRegView 64  # View the 64 bit portion of the registry

    ${EndIf}

    ${LogMsg} "Getting RootDir from 64-bit registry"
    # Get Root Directory from the Registry (64 bit)
    ReadRegStr $RootDir HKLM "SOFTWARE\Salt Project\Salt" "root_dir"
    ${LogMsg} "RootDir: $RootDir"

    # Remove Registry entries
    ${LogMsg} "Deleting Add/Remove programs entries"
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}"

    # Remove Command Line Registry entries
    ${LogMsg} "Deleting Command Line Registry Entries"
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_CALL_REGKEY}"
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_CP_REGKEY}"
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_KEY_REGKEY}"
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_MASTER_REGKEY}"
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_MINION_REGKEY}"
    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_RUN_REGKEY}"
    DeleteRegKey HKLM "SOFTWARE\Salt Project"

    # SystemDrive is not a built in NSIS constant, so we need to get it from
    # the environment variables
    ${LogMsg} "Getting System Drive"
    ReadEnvStr $0 "SystemDrive"  # Get the SystemDrive env var
    StrCpy $SysDrive "$0\"
    ${LogMsg} "SystemDrive: $SysDrive"

    # Automatically close when finished
    SetAutoClose true

    # Old Method Installation
    ${If} $INSTDIR == "C:\salt"

        # Prompt to remove the Installation Directory. This is because that
        # directory is also the root_dir which includes the config and pki
        # directories
        ${IfNot} $DeleteInstallDir == 1
            StrCpy $msg "Would you like to completely remove $INSTDIR and all \
                of its contents?"
            ${LogMsg} $msg
            MessageBox MB_YESNO|MB_DEFBUTTON2|MB_USERICON $msg /SD IDNO IDNO finished
        ${EndIf}

        ${LogMsg} "Removing INSTDIR"
        SetOutPath "$SysDrive"  # Can't remove CWD
        RMDir /r "$INSTDIR"

    ${Else}

        # Prompt for the removal of the Installation Directory which contains
        # the extras directory and the Root Directory which contains the config
        # and pki directories. These directories will not be removed during
        # an upgrade.
        ${IfNot} $DeleteRootDir == 1
            StrCpy $msg "Would you like to completely remove the entire Salt \
                Installation? This includes the following:$\n\
                - Extra Pip Packages ($INSTDIR\extras-3.##)$\n\
                - Minion Config ($RootDir\conf)$\n\
                - Minion PKIs ($RootDir\conf\pki)"
            ${LogMsg} $msg
            MessageBox MB_YESNO|MB_DEFBUTTON2|MB_USERICON $msg /SD IDNO IDNO finished
        ${EndIf}

        # New Method Installation
        # This makes the $APPDATA variable point to the ProgramData folder instead
        # of the current user's roaming AppData folder
        ${LogMsg} "Setting Shell Context to All Users"
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
            ${LogMsg} "Removing INSTDIR"
            SetOutPath "$SysDrive"  # Can't remove CWD
            RMDir /r $INSTDIR
        ${EndIf}

        # Remove INSTDIR (The parent)
        # For example, though salt is installed in ProgramFiles\Salt Project\Salt
        # We want to remove ProgramFiles\Salt Project
        # Only delete Salt Project directory if it's in Program Files
        # Otherwise, we can't guess where the user may have installed salt
        ${LogMsg} "Getting InstDir Parent Directory"
        ${GetParent} $INSTDIR $R0  # Get parent directory (Salt Project)
        ${LogMsg} "Parent: $R0"
        ${If} $R0 == "$ProgramFiles\Salt Project"  # Make sure it's ProgramFiles
        ${OrIf} $R0 == "$ProgramFiles64\Salt Project"  # Make sure it's Program Files (x86)
            ${LogMsg} "Removing Salt Project directory from Program Files"
            SetOutPath "$SysDrive"  # Can't remove CWD
            RMDir /r $R0
        ${EndIf}

        # If RootDir is still empty, use C:\salt
        ${If} $RootDir == ""
            StrCpy $RootDir "C:\salt"
        ${EndIf}

        # Expand any environment variables
        ExpandEnvStrings $RootDir $RootDir

        ${LogMsg} "Removing RootDir: $RootDir"

        # Remove the Salt Project directory in ProgramData
        # The Salt Project directory will only ever be in ProgramData
        # It is not user selectable
        ${LogMsg} "Getting RootDir Parent Directory"
        ${GetParent} $RootDir $R0  # Get parent directory
        ${LogMsg} "Parent: $R0"
        ${If} $R0 == "$APPDATA\Salt Project"  # Make sure it's not ProgramData
            ${LogMsg} "Removing Parent Directory from APPDATA"
            SetOutPath "$SysDrive"  # Can't remove CWD
            RMDir /r $R0
        ${EndIf}

    ${EndIf}

    finished:
        ${LogMsg} "Uninstall Complete"

FunctionEnd
!macroend
!insertmacro uninstallSalt ""
!insertmacro uninstallSalt "un."


Function un.onUninstSuccess

    HideWindow

    StrCpy $msg "$(^Name) was successfully removed from your computer."
    ${LogMsg} $msg
    MessageBox MB_OK|MB_USERICON $msg /SD IDOK

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
!macro Func_Trim un
    Function ${un}Trim

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
!macroend
!insertmacro Func_Trim ""
!insertmacro Func_Trim "un."


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

    ${LogMsg} "Detecting existing installation"

    # Reset ExistingInstallation
    StrCpy $ExistingInstallation 0

    # Get ProgramFiles
    # Use RunningX64 here to get the Architecture for the system running the
    # installer.
    # There are 3 scenarios here:
    ${LogMsg} "Setting Default InstDir"
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
    ${LogMsg} "Setting Default RootDir"
    StrCpy $RootDir "$APPDATA\Salt Project\Salt"

    # The NSIS installer is a 32bit application and will use the WOW6432Node in
    # the registry by default. We need to look in the 64 bit location on 64 bit
    # systems
    ${If} ${RunningX64}
        # https://nsis.sourceforge.io/Docs/Chapter4.html#setregview
        SetRegView 64  # View the 64 bit portion of the registry
    ${EndIf}

    # Check for existing new method installation from registry
    ${LogMsg} "Looking for New Method installation"

    # Look for `install_dir` in HKLM\SOFTWARE\Salt Project\Salt
    ${LogMsg} "Getting INSTDIR from Registry"
    ReadRegStr $R0 HKLM "SOFTWARE\Salt Project\Salt" "install_dir"
    StrCmp $R0 "" checkOldInstallation

    ${LogMsg} "Detected existing installation"
    StrCpy $ExistingInstallation 1

    # Set INSTDIR to the location in the registry
    StrCpy $INSTDIR $R0
    # Expand any environment variables it contains
    ExpandEnvStrings $INSTDIR $INSTDIR

    ${LogMsg} "INSTDIR: $INSTDIR"

    # Set RootDir, if defined
    ${LogMsg} "Getting RootDir"
    ReadRegStr $R0 HKLM "SOFTWARE\Salt Project\Salt" "root_dir"
    StrCmp $R0 "" finished
    StrCpy $RootDir $R0
    # Expand any environment variables it contains
    ExpandEnvStrings $RootDir $RootDir
    ${LogMsg} "RootDir: $RootDir"
    Goto finished

    # Check for existing old method installation
    # Look for `python.exe` in C:\salt\bin
    checkOldInstallation:
        ${LogMsg} "Looking for Old Method installation"
        IfFileExists "C:\salt\bin\python.exe" 0 newInstallation
        StrCpy $ExistingInstallation 1
        StrCpy $INSTDIR "C:\salt"
        StrCpy $RootDir "C:\salt"
        ${LogMsg} "Found Old Method installation"
        Goto finished

    # This is a new installation
    # Check if custom location was passed via command line
    newInstallation:
        ${LogMsg} "This is a New Installation"
        ${IfNot} $CustomLocation == ""
            StrCpy $INSTDIR $CustomLocation
        ${EndIf}

    finished:
        ${LogMsg} "Finished detecting installation type"
        SetRegView 32  # View the 32 bit portion of the registry

FunctionEnd


Function getExistingMinionConfig

    ${LogMsg} "Getting existing Minion Config"

    # Set Config Found Default Value
    StrCpy $ExistingConfigFound 0

    # Find config, should be in $RootDir\conf\minion
    # Root dir is usually ProgramData\Salt Project\Salt\conf though it may be
    # C:\salt\conf if Salt was installed the old way

    ${LogMsg} "Looking for minion config in $RootDir"
    IfFileExists "$RootDir\conf\minion" check_owner
    ${LogMsg} "Looking for minion config in C:\salt"
    IfFileExists "C:\salt\conf\minion" old_location confNotFound

    old_location:
    ${LogMsg} "Found config in old location. Updating RootDir"
    StrCpy $RootDir "C:\salt"
    ${LogMsg} "RootDir: $RootDir"

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

        ${LogMsg} "Validating permissions to config"
        AccessControl::GetFileOwner /SID "$RootDir\conf"
        Pop $0

        # Check for valid SIDs
        StrCmp $0 "S-1-5-32-544" correct_owner  # Administrators Group (NullSoft)
        StrCmp $0 "S-1-5-18" correct_owner      # Local System (MSI)
        StrCpy $msg "Insecure config found at $RootDir\conf. If you continue, the \
                config directory will be renamed to $RootDir\conf.insecure \
                and the default config will be used. Continue?"
        ${LogMsg} $msg
        MessageBox MB_YESNO $msg /SD IDYES IDYES insecure_config
            ${LogMsg} "Aborting"
            Abort

    insecure_config:
        # Backing up insecure config
        ${LogMsg} "Backing up insecure config"
        Rename "$RootDir\conf" "$RootDir\conf.insecure-$TimeStamp"
        Goto confNotFound

    correct_owner:
        ${LogMsg} "Found existing config with correct permissions"
        StrCpy $ExistingConfigFound 1
        ${LogMsg} "Opening minion config read-only"
        ClearErrors
        FileOpen $0 "$RootDir\conf\minion" r
        IfErrors 0 get_config_values
        ${LogMsg} "There was an error opening the minion config"
        ${LogMsg} "Config values will not be detected"
        Goto set_default_values

    get_config_values:
    ${LogMsg} "Getting config values from existing config"

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
        ${LogMsg} "Config not found"

    set_default_values:
        # Set Default Config Values if not found
        ${If} $MasterHost_Cfg == ""
            ${LogMsg} "Setting master host setting to default: salt"
            StrCpy $MasterHost_Cfg "salt"
        ${EndIf}
        ${If} $MinionName_Cfg == ""
            ${LogMsg} "Setting minion id setting to default: hostname"
            StrCpy $MinionName_Cfg "hostname"
        ${EndIf}

FunctionEnd


Var cfg_line
Var chk_line
Var lst_check
Var tgt_file
Var tmp_file
Function updateMinionConfig

    StrCpy $ConfigWriteMaster 1                         # write the master config value
    StrCpy $ConfigWriteMinion 1                         # write the minion config value

    ${If} $MasterHost == ""                             # if master is empty
    ${OrIf} $MasterHost == "salt"                       # or if master is 'salt'
        StrCpy $ConfigWriteMaster 0                     # no need to write master config
    ${EndIf}                                            # close if statement
    ${If} $MinionName == ""                             # if minion is empty
    ${OrIf} $MinionName == "hostname"                   # and if minion is not 'hostname'
        StrCpy $ConfigWriteMinion 0                     # no need to write minion config
    ${EndIf}                                            # close if statement

    ${If} $ConfigWriteMaster == 0
    ${AndIf} $ConfigWriteMinion == 0
        ${LogMsg} "No config values to update. Config will not be updated"
        Goto update_minion_config_finished
    ${EndIf}

    ${LogMsg} "Updating Minion Config"

    ${LogMsg} "Opening target file: $RootDir\conf\minion"
    ClearErrors
    FileOpen $tgt_file "$RootDir\conf\minion" r         # open target file for reading
    ${If} ${Errors}
        ${LogMsg} "Target file could not be opened read-only"
        ${LogMsg} "Minion config will not be updated"
        Goto update_minion_config_finished
    ${EndIf}

    GetTempFileName $R0                                 # get new temp file name
    ${LogMsg} "Opening temp file: $R0"
    ClearErrors
    FileOpen $tmp_file "$R0" w                          # open temp file for writing
    ${If} ${Errors}
        ${LogMsg} "Temp file could not be opened for writing"
        ${LogMsg} "Minion config will not be updated"
        Goto update_minion_config_finished
    ${EndIf}

    loop:                                               # loop through each line
        ${LogMsg} "Reading line from target config file"
        ClearErrors
        FileRead $tgt_file $cfg_line                    # read line from target file
        ${If} ${Errors}
            ${LogMsg} "Error: Most likely reached End-Of-File"
            Goto done
        ${EndIf}

        loop_after_read:
        StrCpy $lst_check 0                             # list check not performed

        ${If} $ConfigWriteMaster == 1                   # if we need to write master config

            ${StrLoc} $3 $cfg_line "master:" ">"        # where is 'master:' in this line
            ${If} $3 == 0                               # is it in the first...
            ${OrIf} $3 == 1                             # or second position (account for comments)

                ${LogMsg} "Found master. Updating temp config"

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
                        FileRead $tgt_file $chk_line    # read line from target file
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
                ${LogMsg} "Found minion ID. Updating temp config"
                StrCpy $cfg_line "id: $MinionName$\r$\n"  # write the minion config setting
                StrCpy $ConfigWriteMinion 0             # minion value written to config
            ${EndIf}                                    # close if statement
        ${EndIf}                                        # close if statement

        ClearErrors
        ${LogMsg} "Writing config line(s) to temp file"
        # Enable this line for troubleshooting
        # ${LogMsg} "cfg_line: $cfg_line"
        FileWrite $tmp_file $cfg_line                   # write changed or unchanged line to temp file
        ${If} ${Errors}
            ${LogMsg} "There was an error writing new config line(s) to temp file"
            Goto update_minion_config_finished
        ${EndIf}

    ${If} $lst_check == 1                               # master not written to the config
        StrCpy $cfg_line $chk_line
        Goto loop_after_read                            # A loop was performed, skip the next read
    ${EndIf}                                            # close if statement

    Goto loop                                           # check the next line in the config file

    done:
    ClearErrors
    # Does master config still need to be written
    ${If} $ConfigWriteMaster == 1                       # master not written to the config

        ${LogMsg} "Master not found in existing config. Appending to the bottom"

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

        ClearErrors
        ${LogMsg} "Writing master config to temp file"
        FileWrite $tmp_file $cfg_line                   # write changed or unchanged line to temp file
        ${If} ${Errors}
            ${LogMsg} "There was an error writing master config to the temp file"
            ${LogMsg} "cfg_line: $cfg_line"
            Goto update_minion_config_finished
        ${EndIf}

    ${EndIf}                                            # close if statement

    ${If} $ConfigWriteMinion == 1                       # minion ID not written to the config
        ${LogMsg} "Minion ID not found in existing config. Appending to the bottom"
        StrCpy $cfg_line "$\r$\nid: $MinionName"        # write the minion config setting

        ClearErrors
        ${LogMsg} "Writing minion id to temp config file"
        FileWrite $tmp_file $cfg_line                   # write changed or unchanged line to temp file
        ${If} ${Errors}
            ${LogMsg} "There was an error writing minion id to temop config file"
            ${LogMsg} "cfg_line: $cfg_line"
            Goto update_minion_config_finished
        ${EndIf}
    ${EndIf}                                            # close if statement

    ${LogMsg} "Closing config files"
    FileClose $tgt_file                                 # close target file
    FileClose $tmp_file                                 # close temp file
    ${LogMsg} "Deleting target config"
    Delete "$RootDir\conf\minion"                       # delete target file
    ${LogMsg} "Copying new target config"
    CopyFiles /SILENT $R0 "$RootDir\conf\minion"        # copy temp file to target file
    ${LogMsg} "Deleting old temp file"
    Delete $R0                                          # delete temp file

    update_minion_config_finished:
        ${LogMsg} "Update minion config finished"

FunctionEnd


Function un.parseUninstallerCommandLineSwitches

    ${LogMsg} "Parsing command line parameters for the Uninstaller"

    # Load the parameters
    ${GetParameters} $cmdLineParams

    # Uninstaller: Remove Installation Directory
    ${LogMsg} "Checking /delete-install-dir"
    ClearErrors
    ${GetOptions} $cmdLineParams "/delete-install-dir" $R1
    ${If} ${Errors}
        ${LogMsg} "/delete-install-dir not found"
    ${Else}
        ${LogMsg} "Found /delete-install-dir"
        StrCpy $DeleteInstallDir 1
    ${EndIf}

    # Uninstaller: Remove Root Directory
    ${LogMsg} "Checking /delete-root-dir"
    ClearErrors
    ${GetOptions} $cmdLineParams "/delete-root-dir" $R1
    ${If} ${Errors}
        ${LogMsg} "/delete-root-dir not found"
    ${Else}
        ${LogMsg} "Found /delete-root-dir"
        StrCpy $DeleteRootDir 1
    ${EndIf}

FunctionEnd


Function parseInstallerCommandLineSwitches

    ${LogMsg} "Parsing command line parameters for the Installer"

    # Load the parameters
    ${GetParameters} $cmdLineParams
    ${LogMsg} "Passed: $cmdLineParams"

    # Check for start-minion switches
    ${LogMsg} "Checking for /start-minion"
    ${GetOptions} $cmdLineParams "/start-minion=" $R1
    ${IfNot} $R1 == ""
        ${LogMsg} "Found /start-minion=$R1"
        # If start-minion was passed something, then set it
        StrCpy $StartMinion $R1
    ${Else}
        # Otherwise default to 1
        ${LogMsg} "/start-minion not found. Using default"
        StrCpy $StartMinion 1
    ${EndIf}

    # Service: Minion Startup Type Delayed
    ${LogMsg} "Checking for /start-minion-delayed"
    ClearErrors
    ${GetOptions} $cmdLineParams "/start-minion-delayed" $R1
    ${If} ${Errors}
        ${LogMsg} "/start-minion-delayed not found"
    ${Else}
        ${LogMsg} "Found /start-minion-delayed"
        StrCpy $StartMinionDelayed 1
    ${EndIf}

    # Set default value for Use Existing Config
    StrCpy $ConfigType "Existing Config"

    # Minion Config: Master IP/Name
    # If setting master, we don't want to use existing config
    ${LogMsg} "Checking for /master"
    ${GetOptions} $cmdLineParams "/master=" $R1
    ${If} ${Errors}
        ${LogMsg} "/master= not found. Using default"
        StrCpy $MasterHost "salt"
    ${ElseIfNot} $R1 == ""
        ${LogMsg} "Found /master=$R1"
        StrCpy $MasterHost $R1
        StrCpy $ConfigType "Default Config"
    ${Else}
        ${LogMsg} "/master found, but value not passed. Using default value"
        StrCpy $MasterHost "salt"
    ${EndIf}

    # Minion Config: Minion ID
    # If setting minion id, we don't want to use existing config
    ${LogMsg} "Checking for /minion-name"
    ${GetOptions} $cmdLineParams "/minion-name=" $R1
    ${If} ${Errors}
        ${LogMsg} "/minion-name= not found. Using default"
        StrCpy $MinionName "hostname"
    ${ElseIfNot} $R1 == ""
        ${LogMsg} "Found /minion-name=$R1"
        StrCpy $MinionName $R1
        StrCpy $ConfigType "Default Config"
    ${Else}
        ${LogMsg} "/minion-name= found, but value not passed. Using default"
        StrCpy $MinionName "hostname"
    ${EndIf}

    # Use Default Config
    ${LogMsg} "Checking for /default-config"
    ClearErrors
    ${GetOptions} $cmdLineParams "/default-config" $R1
    ${If} ${Errors}
        ${LogMsg} "/default-config not found"
    ${Else}
        ${LogMsg} "Found /default-config"
        StrCpy $ConfigType "Default Config"
    ${EndIf}

    # Use Custom Config
    # Set default value for Use Custom Config
    ${LogMsg} "Checking for /custom-config"
    # Existing config will get a `.bak` extension
    ${GetOptions} $cmdLineParams "/custom-config=" $R1
    ${If} ${Errors}
        ${LogMsg} "/custom-config= not found"
        StrCpy $CustomConfig ""
    ${ElseIfNot} $R1 == ""
        ${LogMsg} "Found /custom-config=$R1"
        StrCpy $CustomConfig $R1
        StrCpy $ConfigType "Custom Config"
    ${Else}
        ${LogMsg} "/custom-config= found, but value not passed"
        StrCpy $CustomConfig ""
    ${EndIf}

    # Set Install Location
    ${LogMsg} "Checking for /install-dir"
    ClearErrors
    ${GetOptions} $cmdLineParams "/install-dir=" $R1
    ${If} ${Errors}
        ${LogMsg} "/install-dir= not found"
        StrCpy $CustomLocation ""
    ${ElseIfNot} $R1 == ""
        # A Custom Location was passed, set it
        ${LogMsg} "Found /install-dir=$R1"
        StrCpy $CustomLocation $R1
    ${Else}
        ${LogMsg} "/install-dir= found, but value not passed"
        StrCpy $CustomConfig ""
    ${EndIf}

    # Set Move Config Option
    ${LogMsg} "Checking for /move-config"
    ClearErrors
    ${GetOptions} $cmdLineParams "/move-config" $R1
    ${If} ${Errors}
        ${LogMsg} "/move-config not found"
        StrCpy $MoveExistingConfig 0
    ${Else}
        ${LogMsg} "Found /move-config"
        StrCpy $MoveExistingConfig 1
    ${EndIf}

FunctionEnd
