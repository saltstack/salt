# How to build the msi

## Build client requirements

The build client is where the msi installer is built.

You need
- 64bit Windows 10 (or Windows 11 on Arm for arm64 packages)
- Git repository `salt`
- .Net 3.5 SDK (for WiX)<sup>*</sup>
- [Wix 3](http://wixtoolset.org/releases/)<sup>**</sup> (includes Burn / Bal extension)
- [Build tools 2015](https://www.microsoft.com/en-US/download/confirmation.aspx?id=48159)<sup>**</sup>

`build_pkg.ps1` downloads the arch-matching `vcredist_*_2022.exe` from
salt-windows-deps when linking the Burn Bundle (not merge modules).

Notes:
- <sup>*</sup> `build.cmd` will open `optionalfeatures` if necessary.
- <sup>**</sup> `build.cmd` will download them to `.\_cache.dir` and install if necessary.

### Step 1: build the Nullsoft (NSIS) exe installer or use the mockup

- Build the Nullsoft (NSIS) exe installer

- Or execute `test-copy_mock_files_to_salt_repo.cmd` for only testing configuration

### Step 2: build the msi installer

Execute

    build.cmd

### Remark on transaction safety

- Wix is transaction safe: either the product is installed or the prior state is restored/rolled back.
- C# is not.

### Directory structure

- Product.wxs: Salt Minion MSI (no CRT)
- Bundle.wxs: Burn bootstrapper (VCRedist + MSI) → `*-Bundle.exe`
- CustomAction01/: custom actions in C#
- *-discovered-files.wxs: TEMPORARY FILE

### Naming conventions

- **Immediate** custom actions serve initialization (before the install transaction starts) and must not change the system.
- **Deferred** custom action may change the system but run in a "sandbox".

Postfix  | Example                            | Meaning
-------- | ---------------------------------- | -------
`_IMCAC` | `ReadConfig_IMCAC`                 | Immediate custom action written in C#
`_DECAC` | `WriteConfig_DECAC`                | Deferred custom action written in C#
`_CADH`  | `WriteConfig_CADH`                 | Custom action data helper (only for deferred custom action)

"Custom action data helper" send properties to the deferreed actions in the sandbox.

### Other Notes
msi conditions for install, uninstall, upgrade:
- https://stackoverflow.com/a/17608049


Install sequences documentation:

- [standard-actions-reference](https://docs.microsoft.com/en-us/windows/win32/msi/standard-actions-reference)
- [suggested-installuisequence](https://docs.microsoft.com/en-us/windows/win32/msi/suggested-installuisequence)
- [suggested-installexecutesequence](https://docs.microsoft.com/en-us/windows/win32/msi/suggested-installexecutesequence)
- [other docs](https://www.advancedinstaller.com/user-guide/standard-actions.html)

The Windows installer restricts the maximum values of the [ProductVersion property](https://docs.microsoft.com/en-us/windows/win32/msi/productversion):

- major.minor.build
- `255.255.65535`

Therefore we generate an "internal version":
 - Salt 3002.1 becomes `30.02.1`


[Which Python version uses which MS VC CRT version](https://wiki.python.org/moin/WindowsCompilers)

- Python 2.7 = VC CRT 9.0 = VS 2008
- Python 3.6 = VC CRT 14.0 = VS 2017
