======================================
Automatic Updates / Frozen Deployments
======================================

.. versionadded:: 0.10.3.d

Salt has support for the
`Esky <https://github.com/cloudmatrix/esky>`_ application freezing and update
tool. This tool allows one to build a complete zipfile out of the salt scripts
and all their dependencies - including shared objects / DLLs.

Getting Started
===============

To build frozen applications, you'll need a suitable build environment for each
of your platforms. You should probably set up a virtualenv in order to limit
the scope of Q/A.

This process does work on Windows. Follow the directions at
`<https://github.com/saltstack/salt-windows-install>`_ for details on
installing Salt in Windows. Only the 32-bit Python and dependencies have been
tested, but they have been tested on 64-bit Windows.

You will need to install ``esky`` and ``bbfreeze`` from Pypi in order to enable
the ``bdist_esky`` command in ``setup.py``.

Building and Freezing
=====================

Once you have your tools installed and the environment configured, you can then
``python setup.py bdist`` to get the eggs prepared. After that is done, run
``python setup.py bdist_esky`` to have Esky traverse the module tree and pack
all the scripts up into a redistributable. There will be an appropriately
versioned ``salt-VERSION.zip`` in ``dist/`` if everything went smoothly.

Windows
-------
You will need to add ``C:\Python27\lib\site-packages\zmq`` to your PATH
variable. This helps bbfreeze find the zmq dll so it can pack it up.

Using the Frozen Build
======================

Unpack the zip file in your desired install location. Scripts like
``salt-minion`` and ``salt-call`` will be in the root of the zip file. The
associated libraries and bootstrapping will be in the directories at the same
level. (Check the `Esky <https://github.com/cloudmatrix/esky>`_ documentation
for more information)

To support updating your minions in the wild, put your builds on a web server
that your minions can reach. :py:func:`salt.modules.saltutil.update` will
trigger an update and (optionally) a restart of the minion service under the
new version.

Gotchas
=======

My Windows minion isn't responding
----------------------------------
The process dispatch on Windows is slower than it is on \*nix. You may need to
add '-t 15' to your salt calls to give them plenty of time to return.

Windows and the Visual Studio Redist
------------------------------------
You will need to install the Visual C++ 2008 32-bit redistributable on all
Windows minions. Esky has an option to pack the library into the zipfile,
but OpenSSL does not seem to acknowledge the new location. If you get a
``no OPENSSL_Applink`` error on the console when trying to start your
frozen minion, you have forgotten to install the redistributable.

Mixed Linux environments and Yum
--------------------------------
The Yum Python module doesn't appear to be available on any of the standard
Python package mirrors. If you need to support RHEL/CentOS systems, you
should build on that platform to support all your Linux nodes. Also remember
to build your virtualenv with ``--system-site-packages`` so that the
``yum`` module is included.

Automatic (Python) module discovery
-----------------------------------
Automatic (Python) module discovery does not work with the late-loaded scheme that
Salt uses for (Salt) modules. You will need to explicitly add any
misbehaving modules to the ``freezer_includes`` in Salt's ``setup.py``.
Always check the zipped application to make sure that the necessary modules
were included.
