=======
Windows
=======

Salt currently has experimental support for Salt Minions on Windows.

There are no plans for the forseeable future to develop a Salt
Master on Windows. For now you must run your Salt Master on a
supported operating system to control your Salt Minions on Windows.

Many of the standard Salt modules have been ported to work on Windows
and many of the Salt States currently work on Windows, as well.

Installation from source
========================

Work is under way to create a Windows installer for Salt, but for now
one must install each dependency separately and configure Salt to
run on your Windows host.

Rather than send you on a wild goose chase across the Internet, we've
collected some of the more difficult to find installers in our github repo for you.


Install on Windows XP 32bit
===========================
1.  Install `msysgit`_

    1. Clone the Salt git repository from github

.. code-block:: bash

        git clone git://github.com/saltstack/salt.git

2.  Install `Microsoft Visual Studio 2008 Express`_ with the web installer.
    Or `download a full iso with the installer`_ .
    You must use Visual Studio 2008 Express, **not** Visual Studio 2010 Express.

3.  Install `Python 2.7.x`_

4.  Add c:\\Python27 to your system path

5.  Install the Microsoft Visuall C++ 2008 SP1 Redistributable, `vcredist_x86`_. 

6.  Install `Win32OpenSSL-1_0_0e.exe`_
    
    #.  Choose first option to install in Windows system directory

7.  Install `pyzmq-2.1.11.win32-py2.7.msi`_

8.  Install `pycrypto-2.3.win32-py2.7.msi`_

9.  Install `PyYAML-3.10.win32-py2.7.msi`_

10.  Install `Cython-0.15.1.win32-py2.79.exe`_

11.  Download and run `distribute_setup.py`_

.. code-block:: bash

    python distribute_setup.py

12.  Download and run `pip`_

.. code-block:: bash

        python get-pip.py

13.  Add c:\\python27\\scripts to your path

14.  Close terminal window and open a new terminal window (*cmd*)

15.  Install jinja2
        
.. code-block:: bash

        pip install jinja2

16.  Install Messagepack
        
.. code-block:: bash

        pip install msgpack-python

17.  Install Salt

.. code-block:: bash

        cd ./salt
        python setup.py install

18.  Edit c:\\etc\\salt\\minon

.. code-block:: bash

        master: ipaddress or hostname of your salt-master
        master_port: 4506
        root_dir: c:\
        pki_dir: /etc/salt/pki
        cachedir: /var/cache/salt
        renderer: yaml_jinja
        open_mode: False
        multiprocessing: False

19.  Start the salt-minion

.. code-block:: bash

        cd c:\python27\scripts
        python salt-minion

20.  On the salt-master accept the new minion's key

.. code-block:: bash

        sudo salt-key -A
        
        (This accepts all unaccepted keys. If you're concerned about security just accept the key for this specific minion)

21.  Test that your minion is responding
        
        a.  On the salt-master run:

.. code-block:: bash

        sudo salt '*' test.ping

    
        You should get the following response: {'your minion hostname': True}


.. _msysgit: http://code.google.com/p/msysgit/downloads/list?can=3
.. _Microsoft Visual Studio 2008 Express: http://www.microsoft.com/visualstudio/en-us/products/2008-editions/express 
.. _download a full iso with the installer: http://www.microsoft.com/download/en/details.aspx?id=20682
.. _Python 2.7.x: http://www.python.org
.. _vcredist_x86: http://www.microsoft.com/download/en/details.aspx?id=5582
.. _Win32OpenSSL-1_0_0e.exe: http://www.slproweb.com/products/Win32OpenSSL.html
.. _pyzmq-2.1.11.win32-py2.7.msi: https://github.com/zeromq/pyzmq/downloads
.. _pycrypto-2.3.win32-py2.7.msi: http://www.voidspace.org.uk/python/modules.shtml#pycrypto
.. _PyYAML-3.10.win32-py2.7.msi: http://pyyaml.org/wiki/PyYAML
.. _Cython-0.15.1.win32-py2.79.exe: http://www.lfd.uci.edu/~gohlke/pythonlibs/#cython
.. _distribute_setup.py: http://python-distribute.org/distribute_setup.py
.. _pip: https://raw.github.com/pypa/pip/master/contrib/get-pip.py
