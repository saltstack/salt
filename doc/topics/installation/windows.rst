.. _windows:

=======
Windows
=======

Salt has full support for running the Salt minion on Windows. You must connect
Windows Salt minions to a Salt master on a supported operating system to
control your Salt Minions.

Many of the standard Salt modules have been ported to work on Windows and many
of the Salt States currently work on Windows as well.

.. _windows-installer:

Installation from the Official SaltStack Repository
===================================================

**Latest stable build from the selected branch**:
|windownload|

The output of ``md5sum <salt minion exe>`` should match the contents of the
corresponding md5 file.

`Earlier builds from supported branches <https://repo.saltstack.com/windows/>`__

`Archived builds from unsupported branches <https://repo.saltstack.com/windows/archive/>`__

.. note::

    The installation executable installs dependencies that the Salt minion
    requires.

The 64bit installer has been tested on Windows 7 64bit and Windows Server
2008R2 64bit. The 32bit installer has been tested on Windows 2008 Server 32bit.
Please file a bug report on our GitHub repo if issues for other platforms are
found.

There are installers available for Python 2 and Python 3.

The installer will detect previous installations of Salt and ask if you would
like to remove them. Clicking OK will remove the Salt binaries and related files
but leave any existing config, cache, and PKI information.

Salt Minion Installation
========================

If the system is missing the appropriate version of the Visual C++
Redistributable (vcredist) the user will be prompted to install it. Click ``OK``
to install the vcredist. Click ``Cancel`` to abort the installation without
making modifications to the system.

If Salt is already installed on the system the user will be prompted to remove
the previous installation. Click ``OK`` to uninstall Salt without removing the
configuration, PKI information, or cached files. Click ``Cancel`` to abort the
installation before making any modifications to the system.

After the Welcome and the License Agreement, the installer asks for two bits of
information to configure the minion; the master hostname and the minion name.
The installer will update the minion config with these options.

If the installer finds an existing minion config file, these fields will be
populated with values from the existing config, but they will be grayed out.
There will also be a checkbox to use the existing config. If you continue, the
existing config will be used. If the checkbox is unchecked, default values are
displayed and can be changed. If you continue, the existing config file in
``c:\salt\conf`` will be removed along with the ``c:\salt\conf\minion.d``
directory. The values entered will be used with the default config.

The final page allows you to start the minion service and optionally change its
startup type. By default, the minion is set to ``Automatic``. You can change the
minion start type to ``Automatic (Delayed Start)`` by checking the 'Delayed
Start' checkbox.

.. note::
    Highstates that require a reboot may fail after reboot because salt
    continues the highstate before Windows has finished the booting process.
    This can be fixed by changing the startup type to 'Automatic (Delayed
    Start)'. The drawback is that it may increase the time it takes for the
    'salt-minion' service to actually start.

The ``salt-minion`` service will appear in the Windows Service Manager and can
be managed there or from the command line like any other Windows service.

.. code-block:: bat

    sc start salt-minion
    net start salt-minion

Installation Prerequisites
--------------------------

Most Salt functionality should work just fine right out of the box. A few Salt
modules rely on PowerShell. The minimum version of PowerShell required for Salt
is version 3. If you intend to work with DSC then Powershell version 5 is the
minimum.

.. _windows-installer-options:

Silent Installer Options
========================

The installer can be run silently by providing the ``/S`` option at the command
line. The installer also accepts the following options for configuring the Salt
Minion silently:

=========================  =====================================================
Option                     Description
=========================  =====================================================
``/master=``               A string value to set the IP address or hostname of
                           the master. Default value is 'salt'. You can pass a
                           single master or a comma-separated list of masters.
                           Setting the master will cause the installer to use
                           the default config or a custom config if defined.
``/minion-name=``          A string value to set the minion name. Default value
                           is 'hostname'. Setting the minion name causes the
                           installer to use the default config or a custom
                           config if defined.
``/start-minion=``         Either a 1 or 0. '1' will start the salt-minion
                           service, '0' will not. Default is to start the
                           service after installation.
``/start-minion-delayed``  Set the minion start type to
                           ``Automatic (Delayed Start)``.
``/default-config``        Overwrite the existing config if present with the
                           default config for salt. Default is to use the
                           existing config if present. If ``/master`` and/or
                           ``/minion-name`` is passed, those values will be used
                           to update the new default config.
``/custom-config=``        A string value specifying the name of a custom config
                           file in the same path as the installer or the full
                           path to a custom config file. If ``/master`` and/or
                           ``/minion-name`` is passed, those values will be used
                           to update the new custom config.
``/S``                     Runs the installation silently. Uses the above
                           settings or the defaults.
``/?``                     Displays command line help.
=========================  =====================================================

.. note::
    ``/start-service`` has been deprecated but will continue to function as
    expected for the time being.

.. note::
    ``/default-config`` and ``/custom-config=`` will backup an existing config
    if found. A timestamp and a ``.bak`` extension will be added. That includes
    the ``minion`` file and the ``minion.d`` directory.

Here are some examples of using the silent installer:

.. code-block:: bat

    # Install the Salt Minion
    # Configure the minion and start the service

    Salt-Minion-2017.7.1-Py2-AMD64-Setup.exe /S /master=yoursaltmaster /minion-name=yourminionname

.. code-block:: bat

    # Install the Salt Minion
    # Configure the minion but don't start the minion service

    Salt-Minion-2017.7.1-Py3-AMD64-Setup.exe /S /master=yoursaltmaster /minion-name=yourminionname /start-minion=0

.. code-block:: bat

    # Install the Salt Minion
    # Configure the minion using a custom config and configuring multimaster

    Salt-Minion-2017.7.1-Py3-AMD64-Setup.exe /S /custom-config=windows_minion /master=prod_master1,prod_master2


Running the Salt Minion on Windows as an Unprivileged User
==========================================================

Notes:

- These instructions were tested with Windows Server 2008 R2
- They are generalizable to any version of Windows that supports a salt-minion

Create the Unprivileged User that the Salt Minion will Run As
-------------------------------------------------------------

1. Click ``Start`` > ``Control Panel`` > ``User Accounts``.

2. Click ``Add or remove user accounts``.

3. Click ``Create new account``.

4. Enter ``salt-user`` (or a name of your preference) in the ``New account name`` field.

5. Select the ``Standard user`` radio button.

6. Click the ``Create Account`` button.

7. Click on the newly created user account.

8. Click the ``Create a password`` link.

9. In the ``New password`` and ``Confirm new password`` fields, provide
   a password (e.g "SuperSecretMinionPassword4Me!").

10. In the ``Type a password hint`` field, provide appropriate text (e.g. "My Salt Password").

11. Click the ``Create password`` button.

12. Close the ``Change an Account`` window.


Add the New User to the Access Control List for the Salt Folder
---------------------------------------------------------------

1. In a File Explorer window, browse to the path where Salt is installed (the default path is ``C:\Salt``).

2. Right-click on the ``Salt`` folder and select ``Properties``.

3. Click on the ``Security`` tab.

4. Click the ``Edit`` button.

5. Click the ``Add`` button.

6. Type the name of your designated Salt user and click the ``OK`` button.

7. Check the box to ``Allow`` the ``Modify`` permission.

8. Click the ``OK`` button.

9. Click the ``OK`` button to close the ``Salt Properties`` window.


Update the Windows Service User for the ``salt-minion`` Service
---------------------------------------------------------------

1. Click ``Start`` > ``Administrative Tools`` > ``Services``.

2. In the Services list, right-click on ``salt-minion`` and select ``Properties``.

3. Click the ``Log On`` tab.

4. Click the ``This account`` radio button.

5. Provide the account credentials created in section A.

6. Click the ``OK`` button.

7. Click the ``OK`` button to the prompt confirming that the user ``has been
   granted the Log On As A Service right``.

8. Click the ``OK`` button to the prompt confirming that ``The new logon name
   will not take effect until you stop and restart the service``.

9. Right-Click on ``salt-minion`` and select ``Stop``.

10. Right-Click on ``salt-minion`` and select ``Start``.

.. _building-developing-windows:

Building and Developing on Windows
==================================

This document will explain how to set up a development environment for Salt on
Windows. The development environment allows you to work with the source code to
customize or fix bugs. It will also allow you to build your own installation.

There are several scripts to automate creating a Windows installer as well as
setting up an environment that facilitates developing and troubleshooting Salt
code. They are located in the ``pkg\windows`` directory in the Salt repo
`(here) <https://github.com/saltstack/salt/tree/|repo_primary_branch|/pkg/windows>`_.

Scripts:
--------

===================  ===========
Script               Description
===================  ===========
``build_env_2.ps1``  A PowerShell script that sets up a Python 2 build
                     environment
``build_env_3.ps1``  A PowerShell script that sets up a Python 3 build
                     environment
``build_pkg.bat``    A batch file that builds a Windows installer based on the
                     contents of the ``C:\Python27`` directory
``build.bat``        A batch file that fully automates the building of the
                     Windows installer using the above two scripts
===================  ===========

.. note::
    The ``build.bat`` and ``build_pkg.bat`` scripts both accept a parameter to
    specify the version of Salt that will be displayed in the Windows installer.
    If no version is passed, the version will be determined using git.

    Both scripts also accept an additional parameter to specify the version of
    Python to use. The default is 2.

Prerequisite Software
---------------------

The only prerequisite is `Git for Windows <https://git-scm.com/download/win/>`_.

.. _create-build-environment:

Create a Build Environment
--------------------------

1. Working Directory
^^^^^^^^^^^^^^^^^^^^

Create a ``Salt-Dev`` directory on the root of ``C:``. This will be our working
directory. Navigate to ``Salt-Dev`` and clone the
`Salt <https://github.com/saltstack/salt/>`_ repo from GitHub.

Open a command line and type:

.. code-block:: bat

    cd \
    md Salt-Dev
    cd Salt-Dev
    git clone https://github.com/saltstack/salt

Go into the ``salt`` directory and checkout the version of salt to work with
(2016.3 or higher).

.. code-block:: bat

    cd salt
    git checkout 2017.7.2

2. Setup the Python Environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Navigate to the ``pkg\windows`` directory and execute the **build_env.ps1**
PowerShell script.

.. code-block:: bat

    cd pkg\windows
    powershell -file build_env_2.ps1

.. note::
    You can also do this from Explorer by navigating to the ``pkg\windows``
    directory, right clicking the **build_env_2.ps1** powershell script and
    selecting **Run with PowerShell**

This will download and install Python 2 with all the dependencies needed to
develop and build Salt.

.. note::
    If you get an error or the script fails to run you may need to change the
    execution policy. Open a powershell window and type the following command:

.. code-block:: powershell

    Set-ExecutionPolicy RemoteSigned

3. Salt in Editable Mode
^^^^^^^^^^^^^^^^^^^^^^^^

Editable mode allows you to more easily modify and test the source code. For
more information see the `Pip documentation
<https://pip.pypa.io/en/stable/reference/pip_install/#editable-installs>`_.

Navigate to the root of the ``salt`` directory and install Salt in editable mode
with ``pip``

.. code-block:: bat

    cd \Salt-Dev\salt
    pip install -e .

.. note::
    The ``.`` is important

.. note::
    If ``pip`` is not recognized, you may need to restart your shell to get the
    updated path

.. note::
    If ``pip`` is still not recognized make sure that the Python Scripts folder
    is in the System ``%PATH%``. (``C:\Python2\Scripts``)

4. Setup Salt Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Salt requires a minion configuration file and a few other directories. The
default config file is named ``minion`` located in ``C:\salt\conf``. The
easiest way to set this up is to copy the contents of the
``salt\pkg\windows\buildenv`` directory to ``C:\salt``.

.. code-block:: bat

    cd \
    md salt
    xcopy /s /e \Salt-Dev\salt\pkg\windows\buildenv\* \salt\

Now go into the ``C:\salt\conf`` directory and edit the minion config file named
``minion`` (no extension). You need to configure the master and id parameters in
this file. Edit the following lines:

.. code-block:: bat

    master: <ip or name of your master>
    id: <name of your minion>

.. _create-windows-installer:

Create a Windows Installer
==========================

To create a Windows installer, follow steps 1 and 2 from
:ref:`Create a Build Environment <create-build-environment>` above. Then proceed
to 3 below:

3. Install Salt
---------------

To create the installer for Window we install Salt using Python instead of pip.
Navigate to the root ``salt`` directory and install Salt.

.. code-block:: bat

    cd \Salt-Dev\salt
    python setup.py install

4. Create the Windows Installer
-------------------------------

Navigate to the ``pkg\windows`` directory and run the ``build_pkg.bat``
with the build version (2017.7.2) and the Python version as parameters.

.. code-block:: bat

    cd pkg\windows
    build_pkg.bat 2017.7.2 2
                  ^^^^^^^^ ^
                      |    |
    # build version --     |
    # python version ------

.. note::
    If no version is passed, the ``build_pkg.bat`` will guess the version number
    using git. If the python version is not passed, the default is 2.

.. _create-windows-installer-easy:

Creating a Windows Installer: Alternate Method (Easier)
=======================================================

Clone the `Salt <https://github.com/saltstack/salt/>`_ repo from GitHub into the
directory of your choice. We're going to use ``Salt-Dev``.

.. code-block:: bat

    cd \
    md Salt-Dev
    cd Salt-Dev
    git clone https://github.com/saltstack/salt

Go into the ``salt`` directory and checkout the version of Salt you want to
build.

.. code-block:: bat

    cd salt
    git checkout 2017.7.2

Then navigate to ``pkg\windows`` and run the ``build.bat`` script with the
version you're building.

.. code-block:: bat

    cd pkg\windows
    build.bat 2017.7.2 3
              ^^^^^^^^ ^
                  |    |
    # build version    |
    # python version --

This will install everything needed to build a Windows installer for Salt using
Python 3. The binary will be in the ``salt\pkg\windows\installer`` directory.

.. _test-salt-minion:

Testing the Salt minion
=======================

1. Create the directory ``C:\salt`` (if it doesn't exist already)

2. Copy the example ``conf`` and ``var`` directories from
    ``pkg\windows\buildenv`` into ``C:\salt``

3. Edit ``C:\salt\conf\minion``

    .. code-block:: bash

        master: ipaddress or hostname of your salt-master

4. Start the salt-minion

    .. code-block:: bash

        cd C:\Python27\Scripts
        python salt-minion -l debug

5. On the salt-master accept the new minion's key

    .. code-block:: bash

        sudo salt-key -A

    This accepts all unaccepted keys. If you're concerned about security just
    accept the key for this specific minion.

6. Test that your minion is responding

    On the salt-master run:

    .. code-block:: bash

        sudo salt '*' test.version

You should get the following response: ``{'your minion hostname': True}``

Packages Management Under Windows 2003
======================================

Windows Server 2003 and Windows XP have both reached End of Support. Though Salt
is not officially supported on operating systems that are EoL, some
functionality may continue to work.

On Windows Server 2003, you need to install optional component "WMI Windows
Installer Provider" to get a full list of installed packages. If you don't have
this, salt-minion can't report some installed software.
