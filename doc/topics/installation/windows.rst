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

A Salt Minion Windows installer can be found here:

.. admonition:: Download here

    * 0.17.4
    * http://docs.saltstack.com/downloads/Salt-Minion-0.17.4-win32-Setup.exe
    * http://docs.saltstack.com/downloads/Salt-Minion-0.17.4-AMD64-Setup.exe

    * 0.17.2
    * http://docs.saltstack.com/downloads/Salt-Minion-0.17.2-win32-Setup.exe
    * http://docs.saltstack.com/downloads/Salt-Minion-0.17.2-AMD64-Setup.exe

    * 0.17.1.1 - Windows Installer bugfix release
    * http://docs.saltstack.com/downloads/Salt-Minion-0.17.1.1-win32-Setup.exe
    * http://docs.saltstack.com/downloads/Salt-Minion-0.17.1.1-AMD64-Setup.exe

    * 0.17.1
    * http://docs.saltstack.com/downloads/Salt-Minion-0.17.1-win32-Setup.exe
    * http://docs.saltstack.com/downloads/Salt-Minion-0.17.1-AMD64-Setup.exe

    * 0.17.0
    * http://docs.saltstack.com/downloads/Salt-Minion-0.17.0-win32-Setup.exe
    * http://docs.saltstack.com/downloads/Salt-Minion-0.17.0-AMD64-Setup.exe

    * 0.16.3
    * http://docs.saltstack.com/downloads/Salt-Minion-0.16.3-win32-Setup.exe
    * http://docs.saltstack.com/downloads/Salt-Minion-0.16.3-AMD64-Setup.exe

    * 0.16.2
    * http://docs.saltstack.com/downloads/Salt-Minion-0.16.2-win32-Setup.exe
    * http://docs.saltstack.com/downloads/Salt-Minion-0.16.2-AMD64-Setup.exe

    * 0.16.0
    * http://docs.saltstack.com/downloads/Salt-Minion-0.16.0-win32-Setup.exe
    * http://docs.saltstack.com/downloads/Salt-Minion-0.16.0-AMD64-Setup.exe

    * 0.15.3
    * http://docs.saltstack.com/downloads/Salt-Minion-0.15.3-win32-Setup.exe
    * http://docs.saltstack.com/downloads/Salt-Minion-0.15.3-AMD64-Setup.exe

    * 0.14.1
    * http://docs.saltstack.com/downloads/Salt-Minion-0.14.1-win32-Setup.exe
    * http://docs.saltstack.com/downloads/Salt-Minion-0.14.1-AMD64-Setup.exe

    * 0.14.0
    * http://docs.saltstack.com/downloads/Salt-Minion-0.14.0-win32-Setup.exe
    * http://docs.saltstack.com/downloads/Salt-Minion-0.14.0-AMD64-Setup.exe

.. note::

    The executables above will install dependencies that the Salt minion
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

.. code-block:: bash

    Salt-Minion-0.17.0-Setup-amd64.exe /S /master=yoursaltmaster /minion-name=yourminionname


Setting up a Windows build environment
======================================

1.  Install the Microsoft Visual C++ 2008 SP1 Redistributable, `vcredist_x86`_ or `vcredist_x64`_.

2.  Install `msysgit`_

3. Clone the Salt git repository from GitHub
    
.. code-block:: bash

    git clone git://github.com/saltstack/salt.git

4.  Install the latest point release of `Python 2.7`_ for the architecture you wish to target

5.  Add C:\\Python27 and C:\\Python27\\Scripts to your system path

6.  Download and run the Setuptools bootstrap - `ez_setup.py`_

.. code-block:: bash

    python ez_setup.py
    
7.  Install Pip

.. code-block:: bash
    
    easy_install pip

8.  Install the latest point release of `OpenSSL for Windows`_

    #.  During setup, choose first option to install in Windows system directory

9.  Install the latest point release of `M2Crypto`_

    #.  In general, be sure to download installers targeted at py2.7 for your chosen architecture

10.  Install the latest point release of `pycrypto`_

11.  Install the latest point release of `pywin32`_

12.  Install the latest point release of `Cython`_

13.  Install the latest point release of `jinja2`_

14.  Install the latest point release of `msgpack`_

15.  Install psutil

.. code-block:: bash

        easy_install psutil

16.  Install pyzmq

.. code-block:: bash

        easy_install pyzmq
        
17.  Install PyYAML

.. code-block:: bash

        easy_install pyyaml
        
18.  Install bbfreeze

.. code-block:: bash

        easy_install bbfreeze

19.  Install wmi 

.. code-block:: bash

        pip install wmi

20.  Install esky 

.. code-block:: bash

        pip install esky

21.  Install Salt

.. code-block:: bash

        cd salt
        python setup.py install

22.  Build a frozen binary distribution of Salt

.. code-block:: bash

	python setup.py bdist_esky

A zip file has been created in the ``dist/`` folder, containing a frozen copy of Python and the 
dependency libraries, along with Windows executables for each of the Salt scripts.


Building the installer
======================

The Salt Windows installer is built with the open-source NSIS compiler. The
source for the installer is found in the pkg directory of the Salt repo here:
https://github.com/saltstack/salt/blob/develop/pkg/windows/installer/Salt-Minion-Setup.nsi.
To create the installer, extract the frozen archive from ``dist/`` into ``pkg/windows/buildenv/``
and run NSIS.

The NSIS installer can be found here: http://nsis.sourceforge.net/Main_Page


Testing the Salt minion
=======================

1.  Create the directory C:\\salt (if it doesn't exist already)

2.  Copy the example ``conf`` and ``var`` directories from ``pkg/windows/buildenv/`` into C:\\salt

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

        (This accepts all unaccepted keys. If you're concerned about security just accept the key for this specific minion)

6.  Test that your minion is responding

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

Packages management under Windows 2003
======================================

On windows Server 2003, you need to install optional component "wmi windows installer provider" to have full list of installed packages. If you don't have this, salt-minion can't report some installed softwares.


.. _http://csa-net.dk/salt: http://csa-net.dk/salt
.. _vcredist_x86: http://www.microsoft.com/download/en/details.aspx?id=5582
.. _vcredist_x64: http://www.microsoft.com/download/en/details.aspx?id=2092
.. _msysgit: http://code.google.com/p/msysgit/downloads/list?can=3
.. _Python 2.7: http://www.python.org/getit
.. _ez_setup.py: https://bitbucket.org/pypa/setuptools/raw/bootstrap/ez_setup.py
.. _OpenSSL for Windows: http://www.slproweb.com/products/Win32OpenSSL.html
.. _M2Crypto: http://chandlerproject.org/Projects/MeTooCrypto
.. _pycrypto: http://www.voidspace.org.uk/python/modules.shtml#pycrypto
.. _pywin32: http://sourceforge.net/projects/pywin32/files/pywin32
.. _Cython: http://www.lfd.uci.edu/~gohlke/pythonlibs/#cython
.. _jinja2: http://www.lfd.uci.edu/~gohlke/pythonlibs/#jinja2
.. _msgpack: http://www.lfd.uci.edu/~gohlke/pythonlibs/#msgpack

