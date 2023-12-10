=============================
Multi-minion setup on Windows
=============================

There may be a scenario where having a minion running in the context of the
current, logged-in user would be useful. For example, the normal minion running
under the service account would perform machine-wide, administrative tasks. The
minion running under the user context could be launched when the user logs in
and would be able to perform configuration tasks as if it were the user itself.

The steps required to do this are as follows:

1. Create new root_dir
2. Set root_dir permissions
3. Create directory structure
4. Write minion config
5. Start the minion
6. Register the minion as a service (optional)

.. note::

    The Salt Project has created a powershell script that will configure an
    additional minion on the system for you. It can be found in the root of the
    Salt installation. The script is named ``multi-minion.ps1``. You can get
    help on how to use the script by running the following in a PowerShell
    prompt:

    ``Get-Help .\multi-minion.ps1 -Detailed``

The following guide explains these steps in more detail.

1. Create new ``root_dir``
--------------------------

The minion requires a root directory to store config, cache, logs, etc. The user
must have full permissions to this directory. The easiest way to do this is to
put the ``root_dir`` in the Local AppData directory (``$env:LocalAppData``).

.. code-block:: powershell

    New-Item -Path "$env:LocalAppData\Salt Project\Salt" -Type Directory

2. Set ``root_dir`` permissions
-------------------------------

The user running Salt requires full access to the ``root_dir``. If you have
placed the root_dir in a location that the user does not have access to, you'll
need to give the user full permissions to that directory. Replace the
<placeholder variables> in this example with your own configuration information.

.. code-block:: powershell

    $RootDir = "<new root_dir location>"
    $User    = "<user running salt>"
    $acl = Get-Acl -Path "$RootDir"
    $access_rule = New-Object System.Security.AccessControl.FileSystemAccessRule($User, "Modify", "Allow")
    $acl.AddAccessRule($access_rule)
    Set-Acl -Path "$RootDir" -AclObject $acl

3. Create directory structure
-----------------------------

Salt expects a certain directory structure to be present to avoid unnecessary
messages in the logs. This is usually handled by the installer. Since you're
running your own instance, you need to do it. Make sure the following
directories are present:

  - root_dir\\conf\\minion.d
  - root_dir\\conf\\pki
  - root_dir\\var\\log\\salt
  - root_dir\\var\\run
  - root_dir\\var\\cache\\salt\\minion\\extmods\\grains
  - root_dir\\var\\cache\\salt\\minion\\proc

.. code-block:: powershell

    $RootDir = "<new root_dir location>"
    $cache_dir = "$RootDir\var\cache\salt\minion"
    New-Item -Path "$RootDir\conf" -Type Directory
    New-Item -Path "$RootDir\conf\minion.d" -Type Directory
    New-Item -Path "$RootDir\conf\pki" -Type Directory
    New-Item -Path "$RootDir\var\log\salt" -Type Directory
    New-Item -Path "$RootDir\var\run" -Type Directory
    New-Item -Path "$cache_dir\extmods\grains" -Type Directory
    New-Item -Path "$cache_dir\proc" -Type Directory

4. Write minion config
----------------------

The minion will need its own config, separate from the system minion config.
This config tells the minion where everything is located in the file structure
and also defines the master and minion id. Create a minion config file named
``minion`` in the conf directory.

.. code-block:: powershell

    New-Item -Path "$env:LocalAppData\Salt Project\Salt\conf\minion" -Type File

Make sure the config file has at least the following contents:

.. code-block:: yaml

    master: <ip address, dns name, etc>
    id: <minion id>

    root_dir: <root_dir>
    log_file: <root_dir>\val\log\salt\minion
    utils_dirs:
      - <root_dir>\var\cache\salt\minion\extmods
    winrepo_dir: <root_dir>\srv\salt\win\repo
    winrepo_dir_ng: <root_dir>\srv\salt\win\repo-ng

    file_roots:
      base:
        - <root_dir>\srv\salt
        - <root_dir>\srv\spm\salt

    pillar_roots:
      base:
        - <root_dir>\srv\pillar
        - <root_dir>\srv\spm\pillar

    thorium_roots:
      base:
        - <root_dir>\srv\thorium

5. Run the minion
-----------------

Everything is now set up to run the minion. You can start the minion as you
would normally, but you need to specify the full path to the config file you
created above.

.. code-block:: powershell

    salt-minion.exe -c <root_dir>\conf

6. Register the minion as a service (optional)
----------------------------------------------

You can also register the minion as a service, but you need to understand the
implications of doing so.

- You will need to have administrator privileges to register this minion
  service.
- You will need the password to the user account that will be running the
  minion.
- If the user password changes, you will have to update the service definition
  to reflect the new password.
- The minion runs all the time under the user context, whether that user is
  logged in or not.
- This requires great trust from the user as the minion will be able to perform
  operations under the user's name without the user knowing, whether they are
  logged in or not.
- If you decide to run the new minion under the Local System account, it might
  as well just be a normal minion.
- The helper script does not support registering the second minion as a service.

To register the minion as a service, use the ``ssm.exe`` binary that came with
the Salt installation. Run the following commands, replacing ``<service-name>``,
``<root_dir>``, ``<user_name>``, and ``<password>`` as necessary:

.. code-block:: powershell

    ssm.exe install <service-name> "salt-minion.exe" "-c `"<root_dir>\conf`" -l quiet"
    ssm.exe set <service-name> Description "Salt Minion <user_name>"
    ssm.exe set <service-name> Start SERVICE_AUTO_START
    ssm.exe set <service-name> AppStopMethodConsole 24000
    ssm.exe set <service-name> AppStopMethodWindow 2000
    ssm.exe set <service-name> AppRestartDelay 60000
    ssm.exe set <service-name> ObjectName ".\<user_name>" "<password>"
