# Salt Minion MSI — maintainer notes

> **Line length:** Body text is wrapped to 80 columns. URL-only lines in
> [Link reference definitions](#link-reference-definitions) may run longer
> because Markdown does not allow splitting long URLs across lines.

## Purpose and audience

This file is for **people changing the WiX package**
([Product.wxs](Product.wxs)) and **C# custom actions**
([CustomAction01](CustomAction01/)). It explains MSI concepts as used here,
directory layout (onedir / relenv), and the order of custom actions.

**Operators** (silent install, properties, `msiexec` examples) should use
[README.md](README.md) as the primary reference. Link from there to this file
only when editing the installer itself.

## Onedir layout (what `[INSTALLDIR]` and `[ROOTDIR]` mean)

- **`[INSTALLDIR]`** — Onedir / relenv **binary root** (under Program Files by
  default): `salt-minion.exe`, embedded Python (`Lib\`, `Scripts\`, etc.),
  `ssm.exe`, and PATH entry. Declared in [Product.wxs](Product.wxs) as directory
  `INSTALLDIR`; written to registry as `install_dir`.
- **`[ROOTDIR]`** — Minion **`root_dir`** (default under ProgramData): `conf\`,
  `var\`, logs, caches, user-dropped modules. Directory `ROOTDIR` (and
  `VARDIR` under it); registry `root_dir`.

WiX **Util** extension is used for **`util:ServiceConfig`** and
**`util:EventSource`** only — not `util:RemoveFolderEx`. Folder / bytecode
hygiene is implemented in **custom actions** (see below), not RemoveFolderEx.

## Custom actions in `InstallExecuteSequence`

Order and conditions follow [Product.wxs](Product.wxs) `InstallExecuteSequence`
(execute phase). Deferred actions use **CADH** rows (`*_CADH`) to pass
`CustomActionData` into `*_DECAC`.

1. **`stopSalt`** — condition `1` (always); before `kill_python_exe`. Stops the
   `salt-minion` service so log files are not locked during validation.
2. **`kill_python_exe`** — `(REMOVE ~= "ALL") or WIX_UPGRADE_DETECTED`; before
   `InstallValidate`. Ends Python processes that would hold DLLs open.
3. **`clear_python_caches_IMCAC`** — `NOT (REMOVE = "ALL")`; after
   `kill_python_exe`. Clears **`__pycache__`**, stray **`*.pyc`**, and empty
   dirs under **`[INSTALLDIR]`** (see
   `CustomAction01Util.clear_python_bytecode_caches_under_dir`).
4. **`ReadConfig_IMCAC`** — `NOT Installed`; before `CostInitialize`. Reads
   existing minion config; must run before cost / `INSTALLDIR` is finalized for
   new installs (see notes at end of **Standard action sequence**).
5. **`remove_NSIS_IMCAC`** — `nsis_install_found`; before `InstallValidate`.
   Removes a prior **NSIS** minion when ARP reports `UninstallString` (see
   **Standard action sequence**).
6. **`DeleteConfig2_*`** — `CLEAN_INSTALL and ((NOT Installed) or
   WIX_UPGRADE_DETECTED)`: CADH before deferred `DeleteConfig2_DECAC`; deferred
   after `InstallInitialize`. Clears config/cache before laydown when user
   requests clean install / upgrade clean. Uses the same C# **`DeleteConfig_DECAC`**
   entry as item 10 (shared `DllEntry` in Product.wxs).
7. **`MoveInsecureConfig_*`**, **`BackupConfig_DECAC`**, **`MoveConfig_DECAC`**
   — various `NOT Installed` paths before `CreateFolders` as in Product.wxs.
8. **`WriteConfig_*`** — `NOT Installed`; CADH before `WriteConfig_DECAC`;
   deferred after `WriteIniValues`.
9. **`StartServices`** — `START_MINION`; sequence 5900.
10. **`DeleteConfig_*`** — `REMOVE ~= "ALL"`: CADH before `DeleteConfig_DECAC`;
    deferred after `RemoveFolders`. Full uninstall cleanup. C# **`DeleteConfig_DECAC`**
    (also used by **`DeleteConfig2_DECAC`**, item 6) calls **`clear_python_bytecode_caches_under_dir`**
    on **`[INSTALLDIR]`** first, then removes **`Scripts`** / **`bin`** and config
    trees per **`CLEAN_INSTALL`** / **`REMOVE_CONFIG`**.

**`VC143` feature** — Hidden merge of **Microsoft VC++ 2022** CRT
(`MSM_VC143_CRT` `.msm`); skipped when `VCREDIST_INSTALLED` registry probe says
already present. See **VC++ runtime** below.


## Product attributes

### UpgradeCode
GUID defining the product across versions. E.g. a previous version is
uninstalled during upgrade.
In other words: for update (or upgrade), Windows Installer relies on the
UpgradeCode attribute of the Product tag.
Keep the same UpgradeCode GUID as long as you want the products to be upgraded
by the installer.

### Id
[WiX](https://wixtoolset.org/documentation/manual/v3/xsd/wix/product.html)

The product code GUID for the product. Type: AutogenGuid

[MS](https://docs.microsoft.com/windows/win32/msi/product-codes):
The product code is a GUID that is the principal identification of an
application or product.

[MS](https://docs.microsoft.com/windows/win32/msi/productcode):
This ID must vary for different versions and languages.

[MS](https://docs.microsoft.com/windows/win32/msi/changing-the-product-code)

The product code must be changed if any of the following are true for the
update:
- The name of the .msi file has been changed.

[MS](https://docs.microsoft.com/windows/win32/msi/major-upgrades):
A major upgrade is a comprehensive update of a product that needs a change of
the ProductCode Property.
A typical major upgrade removes a previous version of an application and
installs a new version.

A constant Product code GUID is (only) useful for a subsequent mst (transform).
To be safe for a major upgrade, the Id (product code GUI) is
dynamic/autogenerated: * (star)

Therefore: we use dynamic/autogenerated: * (star)


## Conditions (for install)

[doc](https://wixtoolset.org/documentation/manual/v3/xsd/wix/condition.html)

[expression-syntax][fg-expr-syntax]

The XML CDATA Section <![CDATA[ and ]]> is safer.

## Properties
Most important documentation:
[Naming conventions][msi-prop-names]

- Public properties may be changed by the user and must be upper-case.

Logic value and checkboxes:

-  A msi property is false if and only if it is unset, undefined, missing, the
   empty string (msi properties are strings).
-  A checkbox is empty if and only if the relevant msi property is false.


[OS Properties][wix-os-props]

- MsiNTProductType:  1=Workstation  2=Domain controller  3=Server
- VersionNT:
  - Windows  7=601   [msdn](https://msdn.microsoft.com/library/aa370556.aspx)
  - Windows 10=603 [ms][ms-versionnt-win10]
- PhysicalMemory
  [ms](https://docs.microsoft.com/windows/desktop/Msi/physicalmemory)




msi properties, use in custom actions:
-  DECAC = "Deferred custom action in C#"
-  IMCAC = "Immediate custom action in C#" — reads MSI properties via
   `session["..."]` (not `CustomActionData`). In this project the `_DECAC`
   suffix is for deferred CAs that use a CADH; immediate DLL exports use
   `_IMCAC` even when WiX `Execute` is `immediate` or `firstSequence`.
-  CADH  = "Custom action data helper"
-  The CADH helper must mention each msi property or the DECAC function will
   crash:
-  A DECAC that tries to use a msi property not listed in its CADH crashes.

Example:

In the CADH:

    master=[MASTER];minion_id=[MINION_ID]

In the DECAC:

    session.CustomActionData["master"]      THIS IS OK
    session.CustomActionData["mister"]      THIS WILL CRASH


### Conditional removal of lifetime data
"Lifetime data" means any change that was not installed by the msi (during the
life time of the application).

When uninstalling an application, an msi only removes exactly the data it
installed, unless explicit actions are taken.

Salt creates life time data which must be removed, some of it during upgrade,
all of it (except configuration) during uninstall.

This package does **not** use `util:RemoveFolderEx` for those trees; behavior is
implemented in **C# custom actions** and WiX sequencing instead:
- Under **`[INSTALLDIR]`** (onedir / relenv root), Python bytecode such as
  **`__pycache__`** trees and stray **`*.pyc`** is not fully MSI-owned; clearing
  it on upgrade/repair is appropriate (see `clear_python_caches_IMCAC` in
  [Product.wxs](Product.wxs) and `CustomAction01Util`).
- Under **`[ROOTDIR]`** (minion `root_dir`: logs, `var`, extmods, custom drops,
  etc.), we restrict deletion to full uninstall only (`REMOVE ~= "ALL"`).


### Delete minion_id file
Alternatives

https://wixtoolset.org/documentation/manual/v3/xsd/wix/removefile.html

https://stackoverflow.com/questions/7120238/wix-remove-config-file-on-install




## Sequences
An msi is no linear program.
To understand when custom actions will be executed, one must look at the
condition within the tag and Before/After:

On custom action conditions:
[Common-MSI-Conditions.pdf][msi-cond-pdf]
[ms](https://docs.microsoft.com/windows/win32/msi/property-reference)

On the upgrade custom action condition:

|  Property   |  Comment  |
| --- |  --- |
|  UPGRADINGPRODUCTCODE | does not work
|  Installed            | per-machine or per-user install
|  Not Installed        | there is no previous version with the same UpgradeCode
|  REMOVE ~= "ALL"      | Uninstall

[Custom action introduction][ms-ca-intro]

### Articles
"Installation Phases and In-Script Execution Options for Custom Actions in
Windows Installer"
http://www.installsite.org/pages/en/isnews/200108/


## Standard action sequence

[Standard actions reference][ms-std-actions]

[Standard actions WiX default sequence][fg-seq]

[coding bee on Standard actions WiX default sequence][codingbee-seq]

You get error LGHT0204 when  After or Before are wrong. Example:

    remove_NSIS_IMCAC is an immediate C# in-script custom action. In
    Product.wxs it is sequenced `Before="InstallValidate"` in
    `InstallExecuteSequence` with `Execute="immediate"`.

When an NSIS-based Salt Minion is present, `remove_NSIS_IMCAC` runs the
installed **`uninst.exe`** with **`/S`** only (no temp copy; NSIS infers install
dir from the uninstaller path). After the stub exits, it polls until
**`ssm.exe`** under that install dir is gone (NSIS removes it; the directory may
remain; up to 600s). WMI reports matching **NSIS `Un*.exe`** children for
logging while waiting. `NSIS_UNINSTALLSTRING` comes from WiX ARP
`UninstallString`.

**`clear_python_caches_IMCAC`** (immediate, sequenced `After="kill_python_exe"`,
not on `REMOVE="ALL"`): walks **`[INSTALLDIR]`** and removes every
**`__pycache__`** directory (deepest-first), then stray **`*.pyc`**, then prunes
empty directories (deepest-first), so runtime bytecode not tracked by the MSI
does not survive upgrades. The same **`clear_python_bytecode_caches_under_dir`**
logic also runs at the **start** of deferred **`DeleteConfig_DECAC`** (full
uninstall, `REMOVE ~= "ALL"`) and whenever **`DeleteConfig2_DECAC`** invokes that
same C# method (`CLEAN_INSTALL` / upgrade path; see items 6 and 10 above).

Notes on ReadConfig_IMCAC

    Note 1:
      Problem: INSTALLDIR was not set in ReadConfig_IMCAC
      Solution:
      ReadConfig_IMCAC must not be called BEFORE FindRelatedProducts, but
      BEFORE MigrateFeatureStates because INSTALLDIR in only set in
      CostFinalize, which comes after FindRelatedProducts
      Maybe one could call ReadConfig_IMCAC AFTER FindRelatedProducts
    Note 2:
      ReadConfig_IMCAC is in both InstallUISequence and InstallExecuteSequence,
      but because it is declared Execute='firstSequence', it will not be
      repeated in InstallExecuteSequence if it has been called in
      InstallUISequence.


## Don't allow downgrade
http://wixtoolset.org/documentation/manual/v3/howtos/updates/major_upgrade.html


## VC++ runtime (what this MSI ships)

The minion ships as **onedir** with an embedded Python and native dependencies.
[Product.wxs](Product.wxs) merges the **Microsoft Visual C++ 2022** CRT via
WiX **Merge** modules:

- **`MSM_VC143_CRT`** — `Microsoft_VC143_CRT_x64.msm` or `_x86.msm` from
  `$(var.WEBCACHE_DIR)` (see [build_pkg.ps1](build_pkg.ps1) for download URLs
  and SHA-256 checks).
- Feature **`VC143`** (hidden) references that merge; **`Condition Level="0"`**
  skips install when **`VCREDIST_INSTALLED`** registry search reports the
  runtime already present (see `Product.wxs`).

Merge-module packaging follows the WiX
[how-to][wix-vcredist-howto]. Developers extending the **build** with extra
native wheels may still need a full MSVC toolchain on the **build machine**;
see [PythonWiki](https://wiki.python.org/moin/WindowsCompilers) for background.


## Images
Images:

- Dimensions of images must follow [WiX rules][wix-ui-custom]
- WixUIDialogBmp must be transparent

Create Product-imgLeft.png from panel.bmp:

- Open paint3D:
  - new image, ..., canvas options: Transparent canvas off, Resize image with
    canvas NO, Width 493 Height 312
  - paste panel.bmp, move to the left, save as



## Note on Create folder

          Function `win_verify_env()` in `salt/utils/verify.py` sets permissions
          on each start of the salt-minion service. The installer must create
          **`[ROOTDIR]`** (and related dirs) with the same effective permissions
          so they stay in sync with what the minion enforces at runtime.

          The `Permission` element(s) in Product.wxs replace any present
          permissions, except `NT AUTHORITY\SYSTEM:(OI)(CI)(F)`, which seems to be
          the basis. Therefore, you don't need to specify
          `User="[WIX_ACCOUNT_LOCALSYSTEM]"` `GenericAll="yes"`.

          Use `icacls` to test the result (adjust paths to your `ROOTDIR`, e.g.
          `C:\ProgramData\Salt Project\Salt`):

            C:\>icacls "C:\ProgramData\Salt Project\Salt"
            ... BUILTIN\Administrators:(OI)(CI)(F)
                NT AUTHORITY\SYSTEM:(OI)(CI)(F)
            ~~ read ~~
            (object inherit)(container inherit)(full access)

            C:\>icacls "C:\ProgramData\Salt Project\Salt\conf"
            ... BUILTIN\Administrators:(I)(OI)(CI)(F)
                NT AUTHORITY\SYSTEM:(I)(OI)(CI)(F)
            ~~ read ~~
            (permission inherited from parent container)(object inherit)
            (container inherit)(full access)

          Maybe even the Administrator group full access is "basis", so there is
          no result of the instruction,
          I leave it for clarity, and potential future use.

## Set permissions of the install folder with WixQueryOsWellKnownSID

[doc](http://wixtoolset.org/documentation/manual/v3/customactions/osinfo.html)

## Link reference definitions

Markdown link targets (see line-length note at top of this file).

[fg-expr-syntax]: https://www.firegiant.com/wix/tutorial/com-expression-syntax-miscellanea/expression-syntax
[msi-prop-names]: https://docs.microsoft.com/windows/win32/msi/restrictions-on-property-names
[wix-os-props]: http://wixtoolset.org/documentation/manual/v3/howtos/redistributables_and_install_checks/block_install_on_os.html
[ms-versionnt-win10]: https://support.microsoft.com/help/3202260/versionnt-value-for-windows-10-and-windows-server-2016
[msi-cond-pdf]: http://resources.flexerasoftware.com/web/pdf/archive/IS-CHS-Common-MSI-Conditions.pdf
[ms-ca-intro]: https://docs.microsoft.com/archive/blogs/alexshev/from-msi-to-wix-part-5-custom-actions-introduction
[ms-std-actions]: https://docs.microsoft.com/windows/win32/msi/standard-actions-reference
[fg-seq]: https://www.firegiant.com/wix/tutorial/events-and-actions/queueing-up/
[codingbee-seq]: https://codingbee.net/wix/wix-the-installation-sequence
[wix-vcredist-howto]: https://wixtoolset.org/documentation/manual/v3/howtos/redistributables_and_install_checks/install_vcredist.html
[wix-ui-custom]: http://wixtoolset.org/documentation/manual/v3/wixui/wixui_customizations.html
