=======
Windows
=======

Salt has full support for running the Salt Minion on Windows.

There are no plans for the foreseeable future to develop a Salt Master on
Windows. For now you must run your Salt Master on a supported operating system
to control your Salt Minions on Windows.

Many of the standard Salt modules have been ported to work on Windows and many
of the Salt States currently work on Windows, as well.


Windows Installer
=================

Salt Minion Windows installers can be found here. The output of `md5sum <salt
minion exe>` should match the contents of the corresponding md5 file.

**Latest stable build from the selected branch**:
|windownload|

`Earlier builds from supported branches <https://repo.saltstack.com/windows/>`__

`Archived builds from unsupported branches <https://repo.saltstack.com/archive/>`__

.. note::

    The installation executable installs dependencies that the Salt minion
    requires.

The 64bit installer has been tested on Windows 7 64bit and Windows Server
2008R2 64bit. The 32bit installer has been tested on Windows 2003 Server 32bit.
Please file a bug report on our GitHub repo if issues for other platforms are
found.

The installer asks for 2 bits of information; the master hostname and the
minion name. The installer will update the minion config with these options and
then start the minion.

The `salt-minion` service will appear in the Windows Service Manager and can be
started and stopped there or with the command line program `sc` like any other
Windows service.

If the minion won't start, try installing the Microsoft Visual C++ 2008 x64 SP1
redistributable. Allow all Windows updates to run salt-minion smoothly.


Silent Installer option
=======================

The installer can be run silently by providing the `/S` option at the command
line. The options `/master` and `/minion-name` allow for configuring the master
hostname and minion name, respectively. Here's an example of using the silent
installer:

.. code-block:: bat

    Salt-Minion-0.17.0-Setup-amd64.exe /S /master=yoursaltmaster /minion-name=yourminionname


Setting up a Windows build environment
======================================

This document will explain how to set up a development environment for salt on
Windows. The development environment allows you to work with the source code to
customize or fix bugs. It will also allow you to build your own installation.

The Easy Way
------------

Prerequisite Software
^^^^^^^^^^^^^^^^^^^^^

To do this the easy way you only need to install `Git for Windows <https://github.com/msysgit/msysgit/releases/download/Git-1.9.5-preview20150319/Git-1.9.5-preview20150319.exe/>`_.

Create the Build Environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. Clone the `Salt-Windows-Dev <https://github.com/saltstack/salt-windows-dev/>`_
   repo from github.

   Open a command line and type:

   .. code-block:: bat

      git clone https://github.com/saltstack/salt-windows-dev

2. Build the Python Environment

   Go into the salt-windows-dev directory. Right-click the file named
   **dev_env.ps1** and select **Run with PowerShell**

   If you get an error, you may need to change the execution policy.

   Open a powershell window and type the following:

   .. code-block:: powershell

      Set-ExecutionPolicy RemoteSigned

   This will download and install Python with all the dependencies needed to
   develop and build salt.

3. Build the Salt Environment

   Right-click on the file named **dev_env_salt.ps1** and select **Run with
   Powershell**

   This will clone salt into ``C:\Salt-Dev\salt`` and set it to the 2015.5
   branch. You could optionally run the command from a powershell window with a
   ``-Version`` switch to pull a different version. For example:

   .. code-block:: powershell

      dev_env_salt.ps1 -Version '2014.7'

   To view a list of available branches and tags, open a command prompt in your
   `C:\Salt-Dev\salt` directory and type:

   .. code-block:: bat

      git branch -a
      git tag -n


The Hard Way
------------

Prerequisite Software
^^^^^^^^^^^^^^^^^^^^^

Install the following software:

1. `Git for Windows <https://github.com/msysgit/msysgit/releases/download/Git-1.9.5-preview20150319/Git-1.9.5-preview20150319.exe/>`_
2. `Nullsoft Installer <http://downloads.sourceforge.net/project/nsis/NSIS%203%20Pre-release/3.0b1/nsis-3.0b1-setup.exe/>`_

Download the Prerequisite zip file for your CPU architecture from the
SaltStack download site:

* `Salt32.zip <http://docs.saltstack.com/downloads/windows-deps/Salt32.zip/>`_
* `Salt64.zip <http://docs.saltstack.com/downloads/windows-deps/Salt64.zip/>`_

These files contain all sofware required to build and develop salt. Unzip the
contents of the file to ``C:\Salt-Dev\temp``.

Create the Build Environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. Build the Python Environment

   * Install Python:

     Browse to the ``C:\Salt-Dev\temp`` directory and find the Python
     installation file for your CPU Architecture under the corresponding
     subfolder. Double-click the file to install python.

     Make sure the following are in your **PATH** environment variable:

     .. code-block:: bat

        C:\Python27
        C:\Python27\Scripts

   * Install Pip

     Open a command prompt and navigate to ``C:\Salt-Dev\temp``
     Run the following command:

     .. code-block:: bat

        python get-pip.py

   * Easy Install compiled binaries.

     M2Crypto, PyCrypto, and PyWin32 need to be installed using Easy Install.
     Open a command prompt and navigate to ``C:\Salt-Dev\temp\<cpuarch>``.
     Run the following commands:

     .. code-block:: bat

        easy_install -Z <M2Crypto file name>
        easy_install -Z <PyCrypto file name>
        easy_install -Z <PyWin32 file name>

     .. note::
        You can type the first part of the file name and then press the tab key
        to auto-complete the name of the file.

   * Pip Install Additional Prerequisites

     All remaining prerequisites need to be pip installed. These prerequisites
     are as follow:

     * MarkupSafe
     * Jinja
     * MsgPack
     * PSUtil
     * PyYAML
     * PyZMQ
     * WMI
     * Requests
     * Certifi

     Open a command prompt and navigate to ``C:\Salt-Dev\temp``. Run the following
     commands:

     .. code-block:: bat

        pip install <cpuarch>\<MarkupSafe file name>
        pip install <Jinja file name>
        pip install <cpuarch>\<MsgPack file name>
        pip install <cpuarch>\<psutil file name>
        pip install <cpuarch>\<PyYAML file name>
        pip install <cpuarch>\<pyzmq file name>
        pip install <WMI file name>
        pip install <requests file name>
        pip install <certifi file name>

2. Build the Salt Environment

   * Clone Salt

     Open a command prompt and navigate to ``C:\Salt-Dev``. Run the following command
     to clone salt:

     .. code-block:: bat

        git clone https://github.com/saltstack/salt

   * Checkout Branch

     Checkout the branch or tag of salt you want to work on or build. Open a
     command prompt and navigate to ``C:\Salt-Dev\salt``. Get a list of
     available tags and branches by running the following commands:

     .. code-block:: bat

        git fetch --all

        To view a list of available branches:
        git branch -a

        To view a list of availabel tags:
        git tag -n

     Checkout the branch or tag by typing the following command:

     .. code-block:: bat

        git checkout <branch/tag name>

   * Clean the Environment

     When switching between branches residual files can be left behind that
     will interfere with the functionality of salt. Therefore, after you check
     out the branch you want to work on, type the following commands to clean
     the salt environment:

     .. code-block: bat

        git clean -fxd
        git reset --hard HEAD


Developing with Salt
====================
There are two ways to develop with salt. You can run salt's setup.py each time
you make a change to source code or you can use the setup tools develop mode.


Configure the Minion
--------------------
Both methods require that the minion configuration be in the ``C:\salt``
directory. Copy the conf and var directories from ``C:\Salt-Dev\salt\pkg\
windows\buildenv`` to ``C:\salt``. Now go into the ``C:\salt\conf`` directory
and edit the file name ``minion`` (no extension). You need to configure the
master and id parameters in this file. Edit the following lines:

.. code-block:: bat

   master: <ip or name of your master>
   id: <name of your minion>

Setup.py Method
---------------
Go into the ``C:\Salt-Dev\salt`` directory from a cmd prompt and type:

.. code-block:: bat

   python setup.py install --force

This will install python into your python installation at ``C:\Python27``.
Everytime you make an edit to your source code, you'll have to stop the minion,
run the setup, and start the minion.

To start the salt-minion go into ``C:\Python27\Scripts`` from a cmd prompt and
type:

.. code-block:: bat

   salt-minion

For debug mode type:

.. code-block:: bat

   salt-minion -l debug

To stop the minion press Ctrl+C.


Setup Tools Develop Mode (Preferred Method)
-------------------------------------------
To use the Setup Tools Develop Mode go into ``C:\Salt-Dev\salt`` from a cmd
prompt and type:

.. code-block:: bat

   pip install -e .

This will install pointers to your source code that resides at
``C:\Salt-Dev\salt``. When you edit your source code you only have to restart
the minion.


Build the windows installer
===========================
This is the method of building the installer as of version 2014.7.4.

Clean the Environment
---------------------
Make sure you don't have any leftover salt files from previous versions of salt
in your Python directory.

1. Remove all files that start with salt in the ``C:\Python27\Scripts``
   directory

2. Remove all files and directorys that start with salt in the
   ``C:\Python27\Lib\site-packages`` directory

Install Salt
------------
Install salt using salt's setup.py. From the ``C:\Salt-Dev\salt`` directory
type the following command:

.. code-block:: bat

   python setup.py install --force

Build the Installer
-------------------

From cmd prompt go into the ``C:\Salt-Dev\salt\pkg\windows`` directory. Type
the following command for the branch or tag of salt you're building:

.. code-block:: bat

   BuildSalt.bat <branch or tag>

This will copy python with salt installed to the ``buildenv\bin`` directory,
make it portable, and then create the windows installer . The .exe for the
windows installer will be placed in the ``installer`` directory.


Testing the Salt minion
=======================

1.  Create the directory C:\\salt (if it doesn't exist already)

2.  Copy the example ``conf`` and ``var`` directories from
    ``pkg/windows/buildenv/`` into C:\\salt

3.  Edit C:\\salt\\conf\\minion

    .. code-block:: bash

        master: ipaddress or hostname of your salt-master

4.  Start the salt-minion

    .. code-block:: bash

        cd C:\Python27\Scripts
        python salt-minion

5.  On the salt-master accept the new minion's key

    .. code-block:: bash

        sudo salt-key -A

    This accepts all unaccepted keys. If you're concerned about security just
    accept the key for this specific minion.

6.  Test that your minion is responding

    On the salt-master run:

    .. code-block:: bash

        sudo salt '*' test.ping


You should get the following response: ``{'your minion hostname': True}``


Single command bootstrap script
===============================

On a 64 bit Windows host the following script makes an unattended install of
salt, including all dependencies:

.. admonition:: Not up to date.

    This script is not up to date. Please use the installer found above

.. code-block:: powershell

    # (All in one line.)

    "PowerShell (New-Object System.Net.WebClient).DownloadFile('http://csa-net.dk/salt/bootstrap64.bat','C:\bootstrap.bat');(New-Object -com Shell.Application).ShellExecute('C:\bootstrap.bat');"

You can execute the above command remotely from a Linux host using winexe:

.. code-block:: bash

    winexe -U "administrator" //fqdn "PowerShell (New-Object ......);"


For more info check `http://csa-net.dk/salt`_

Packages management under Windows 2003
======================================

On windows Server 2003, you need to install optional component "wmi windows
installer provider" to have full list of installed packages. If you don't have
this, salt-minion can't report some installed softwares.


.. _http://csa-net.dk/salt: http://csa-net.dk/salt
.. _msysgit: http://code.google.com/p/msysgit/downloads/list?can=3
.. _Python 2.7: http://www.python.org/downloads
.. _ez_setup.py: https://bitbucket.org/pypa/setuptools/raw/bootstrap/ez_setup.py
.. _OpenSSL for Windows: http://slproweb.com/products/Win32OpenSSL.html
.. _M2Crypto: http://chandlerproject.org/Projects/MeTooCrypto
.. _pycrypto: http://www.voidspace.org.uk/python/modules.shtml#pycrypto
.. _pywin32: http://sourceforge.net/projects/pywin32/files/pywin32
.. _Cython: http://www.lfd.uci.edu/~gohlke/pythonlibs/#cython
.. _jinja2: http://www.lfd.uci.edu/~gohlke/pythonlibs/#jinja2
.. _msgpack: http://www.lfd.uci.edu/~gohlke/pythonlibs/#msgpack

