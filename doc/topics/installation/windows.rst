=======
Windows
=======

Salt has full support for running the Salt Minion on Windows.

There are no plans for the foreseeable future to develop a Salt
Master on Windows. For now you must run your Salt Master on a
supported operating system to control your Salt Minions on Windows.

Many of the standard Salt modules have been ported to work on Windows
and many of the Salt States currently work on Windows, as well.

Windows Installer
=================

A Salt Minion Windows installer can be found here:

.. admonition:: Download here

    * 0.16.0
    * http://saltstack.com/downloads/Salt-Minion-0.16.0-win32-Setup.exe
    * http://saltstack.com/downloads/Salt-Minion-0.16.0-AMD64-Setup.exe

    * 0.15.3
    * http://saltstack.com/downloads/Salt-Minion-0.15.3-win32-Setup.exe
    * http://saltstack.com/downloads/Salt-Minion-0.15.3-AMD64-Setup.exe

    * 0.14.1
    * http://saltstack.com/downloads/Salt-Minion-0.14.1-win32-Setup.exe
    * http://saltstack.com/downloads/Salt-Minion-0.14.1-AMD64-Setup.exe

    * 0.14.0
    * http://saltstack.com/downloads/Salt-Minion-0.14.0-win32-Setup.exe
    * http://saltstack.com/downloads/Salt-Minion-0.14.0-AMD64-Setup.exe


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

Make sure that the minion config file has the line `ipc_mode: tcp`

Silent Installer option
=======================

The installer can be run silently by providing the `/S` option at the command
line. The options `/master` and `/minion-name` allow for configuring the master
hostname and minion name, respectively. Here's an example of using the silent
installer:

.. code-block:: bash

    Salt-Minion-0.15.3-Setup-amd64.exe /S /master=yoursaltmaster /minion-name=yourminionname

Installer Source
================

The Salt Windows installer is built with the open-source NSIS compiler. The
source for the installer is found in the pkg directory of the Salt repo here:
https://github.com/saltstack/salt/blob/develop/pkg/windows/installer/Salt-Minion-Setup.nsi.
To create the installer run ``python setup.py bdist_esky``, extract the
frozen archive from ``dist/`` into ``pkg/windows/buildenv/`` and run NSIS.

The NSIS installer can be found here: http://nsis.sourceforge.net/Main_Page


Installation from source
========================

To install Salt from source one must install each dependency separately and
configure Salt to run on your Windows host.

Rather than send you on a wild goose chase across the Internet, we've collected
some of the more difficult to find installers in our GitHub repo for you.


Install on Windows XP 32bit
===========================
1.  Install `msysgit`_

    1. Clone the Salt git repository from GitHub

.. code-block:: bash

        git clone git://github.com/saltstack/salt.git

2.  Install Microsoft Visual Studio 2008 Express.
    You must use Visual Studio 2008 Express, **not** Visual Studio 2010 Express.

3.  Install `Python 2.7.x`_

4.  Add c:\\Python27 to your system path

5.  Install the Microsoft Visual C++ 2008 SP1 Redistributable, `vcredist_x86`_.

6.  Install `Win32OpenSSL-1_0_0e.exe`_

    #.  Choose first option to install in Windows system directory

7.  Install `pyzmq-2.1.11.win32-py2.7.msi`_

8.  Install `pycrypto-2.3.win32-py2.7.msi`_

9.  Install `M2Crypto`_

10.  Install `pywin32`_

11.  Install `PyYAML-3.10.win32-py2.7.msi`_

12.  Install `Cython-0.15.1.win32-py2.79.exe`_

13.  Download and run `distribute_setup.py`_

.. code-block:: bash

    python distribute_setup.py

14.  Download and run `pip`_

.. code-block:: bash

        python get-pip.py

15.  Add c:\\python27\\scripts to your path

16.  Close terminal window and open a new terminal window (*cmd*)

17.  Install jinja2

.. code-block:: bash

        pip install jinja2

18.  Install wmi 

.. code-block:: bash

        pip install wmi

19.  Install Messagepack

.. code-block:: bash

        pip install msgpack-python

20.  Install Salt

.. code-block:: bash

        cd ./salt
        python setup.py install

21.  Edit c:\\etc\\salt\\minion

.. code-block:: bash

        master: ipaddress or hostname of your salt-master
        master_port: 4506
        ipc_mode: tcp
        root_dir: c:\
        pki_dir: /etc/salt/pki
        cachedir: /var/cache/salt
        renderer: yaml_jinja
        open_mode: False
        multiprocessing: False

22.  Start the salt-minion

.. code-block:: bash

        cd c:\python27\scripts
        python salt-minion

23.  On the salt-master accept the new minion's key

.. code-block:: bash

        sudo salt-key -A

        (This accepts all unaccepted keys. If you're concerned about security just accept the key for this specific minion)

24.  Test that your minion is responding

        a.  On the salt-master run:

.. code-block:: bash

        sudo salt '*' test.ping


You should get the following response: {'your minion hostname': True}


Single command bootstrap script
===============================

On a 64 bit Windows host the following script makes an unattended install of salt, including all dependencies:

.. admonition:: Not up to date.

      This script is not up to date. Please use the installer found above

.. code-block:: bash

        "PowerShell (New-Object System.Net.WebClient).DownloadFile('http://csa-net.dk/salt/bootstrap64.bat','C:\bootstrap.bat');(New-Object -com Shell.Application).ShellExecute('C:\bootstrap.bat');"

	(All in one line.)

You can execute the above command remotely from a Linux host using winexe:

.. code-block:: bash

        winexe -U "administrator" //fqdn "PowerShell (New-Object ......);"


For more info check `http://csa-net.dk/salt`_


.. _http://csa-net.dk/salt: http://csa-net.dk/salt
.. _msysgit: http://code.google.com/p/msysgit/downloads/list?can=3
.. _Microsoft Visual Studio 2008 Express: http://www.microsoft.com/en-gb/download/details.aspx?id=20682
.. _Python 2.7.x: http://www.python.org
.. _vcredist_x86: http://www.microsoft.com/download/en/details.aspx?id=5582
.. _Win32OpenSSL-1_0_0e.exe: http://www.slproweb.com/products/Win32OpenSSL.html
.. _pyzmq-2.1.11.win32-py2.7.msi: https://github.com/zeromq/pyzmq/downloads
.. _pycrypto-2.3.win32-py2.7.msi: http://www.voidspace.org.uk/python/modules.shtml#pycrypto
.. _PyYAML-3.10.win32-py2.7.msi: http://pyyaml.org/wiki/PyYAML
.. _Cython-0.15.1.win32-py2.79.exe: http://www.lfd.uci.edu/~gohlke/pythonlibs/#cython
.. _distribute_setup.py: http://python-distribute.org/distribute_setup.py
.. _pip: https://raw.github.com/pypa/pip/master/contrib/get-pip.py
.. _M2Crypto: http://chandlerproject.org/pub/Projects/MeTooCrypto/M2Crypto-0.21.1.win32-py2.7.exe
.. _pywin32: http://sourceforge.net/projects/pywin32/files/
