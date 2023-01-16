# Salt Minion msi installer

The installer offers properties for unattended/silent installations.

Example: install silently, set the master, don't start the service:

> msiexec /i *.msi MASTER=salt2 START_MINION=""

Example: uninstall and remove configuration

> MsiExec.exe /X *.msi REMOVE_CONFIG=1

##  Notes

- The installer requires a privileged user
- Properties must be upper case
- Values of properties are case sensitve
- Values must be quoted when they contain whitespace, or to unset a property, as in `START_MINION=""`
- Creates a verbose log file, by default `%TEMP%\MSIxxxxx.LOG`, where xxxxx is random. The name of the log can be specified with `msiexec /log example.log`
- extends the system `PATH` environment variable

## Properties

  Property              |  Default value          | Comment
 ---------------------- | ----------------------- | ------
 `MASTER`               | `salt`                  | The master (name or IP). Separate multiple masters by comma.
 `MASTER_KEY`           |                         | The master public key. See below.
 `MINION_ID`            | Hostname                | The minion id.
 `MINION_CONFIG`        |                         | Content to be written to the `minion` config file. See below.
 `START_MINION`         | `1`                     | Set to `""` to prevent the start of the `salt-minion` service.
 `MOVE_CONF`            |                         | Set to `1` to move configuration from `C:\salt` to `%ProgramData%`.
 `REMOVE_CONFIG`        |                         | Set to `1` to remove configuration on uninstall. Implied by `MINION_CONFIG`.
 `CLEAN_INSTALL`        |                         | Set to `1` to remove configuration and cache before install or upgrade.
 `CONFIG_TYPE`          | `Existing`              | Set to `Custom` or `Default` for scenarios below.
 `CUSTOM_CONFIG`        |                         | Name of a custom config file in the same path as the installer or full path. Requires `CONFIG_TYPE=Custom`. __ONLY FROM COMMANDLINE__
 `INSTALLDIR`           | Windows default         | Where to install binaries.
 `ROOTDIR`              | `C:\ProgramData\Salt Project\Salt` | Where to install configuration.
 `ARPSYSTEMCOMPONENT`   |                         | Set to `1` to hide "Salt Minion" in "Programs and Features".


Master and id are read from file `conf\minion`

You can set a master with `MASTER`.

You can set a master public key with `MASTER_KEY`, after you converted it into one line like so:

- Remove the first and the last line (`-----BEGIN PUBLIC KEY-----` and `-----END PUBLIC KEY-----`).
- Remove linebreaks.

### Property `MINION_CONFIG`

If `MINION_CONFIG` is set:

- Its content is written to configuraton file `conf\minion`, with `^` replaced by line breaks
- All prior configuration is deleted:
  - all `minion.d\*.conf` files
  - the `minion_id` file
- Implies `REMOVE_CONFIG=1`: uninstall will remove all configuration.

Example `MINION_CONFIG="master: Anna^id: Bob"` results in:

    master: Anna
    id: Bob


### Property `CONFIG_TYPE`

There are 3 scenarios the installer tries to account for:

1. existing-config
2. custom-config
3. default-config

Existing

This setting makes no changes to the existing config and just upgrades/downgrades salt.
Makes for easy upgrades. Just run the installer with a silent option.
If there is no existing config, then the default is used and `master` and `minion id` are applied if passed.

Custom

This setting will lay down a custom config passed via the command line.
Since we want to make sure the custom config is applied correctly, we'll need to back up any existing config.
1. `minion` config renamed to `minion-<timestamp>.bak`
2. `minion_id` file renamed to `minion_id-<timestamp>.bak`
3. `minion.d` directory renamed to `minion.d-<timestamp>.bak`
Then the custom config is laid down by the installer... and `master` and `minion id` should be applied to the custom config if passed.

Default

This setting will reset config to be the default config contained in the pkg.
Therefore, all existing config files should be backed up
1. `minion` config renamed to `minion-<timestamp>.bak`
2. `minion_id` file renamed to `minion_id-<timestamp>.bak`
3. `minion.d` directory renamed to `minion.d-<timestamp>.bak`
Then the default config file is laid down by the installer... settings for `master` and `minion id` should be applied to the default config if passed


### Previous installation in C:\salt and how to install into C:\salt
A previous installation or configuration in `C:\salt` causes an upgrade into `C:\salt`, unless you set `MOVE_CONF=1`.
Set the two properties `INSTALLDIR=c:\salt ROOTDIR=c:\salt` to install binaries and configuration into `C:\salt`.

## Client requirements

- Windows 7 (for workstations), Server 2012 (for domain controllers), or higher.
