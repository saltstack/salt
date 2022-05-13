.. _tutorial-esky:

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

To build frozen applications, suitable build environment will be needed for
each platform. You should probably set up a virtualenv in order to limit the
scope of Q/A.

This process does work on Windows. Directions are available at
`<https://github.com/saltstack/salt-windows-install>`_ for details on
installing Salt in Windows. Only the 32-bit Python and dependencies have been
tested, but they have been tested on 64-bit Windows.

Install ``bbfreeze``, and then ``esky`` from PyPI in order to enable the
``bdist_esky`` command in ``setup.py``. Salt itself must also be installed, in
addition to its dependencies.

Building and Freezing
=====================

Once you have your tools installed and the environment configured, use
``setup.py`` to prepare the distribution files.

.. code-block:: bash

    python setup.py sdist
    python setup.py bdist

Once the distribution files are in place, Esky can be used traverse the module
tree and pack all the scripts up into a redistributable.

.. code-block:: bash

    python setup.py bdist_esky

There will be an appropriately versioned ``salt-VERSION.zip`` in ``dist/`` if
everything went smoothly.

Windows
-------
``C:\Python27\lib\site-packages\zmq`` will need to be added to the PATH
variable. This helps bbfreeze find the zmq DLL so it can pack it up.

Using the Frozen Build
======================

Unpack the zip file in the desired install location. Scripts like
``salt-minion`` and ``salt-call`` will be in the root of the zip file. The
associated libraries and bootstrapping will be in the directories at the same
level. (Check the `Esky <https://github.com/cloudmatrix/esky>`_ documentation
for more information)

To support updating your minions in the wild, put the builds on a web server
that the minions can reach. :py:func:`salt.modules.saltutil.update` will
trigger an update and (optionally) a restart of the minion service under the
new version.

Troubleshooting
===============

A Windows minion isn't responding
---------------------------------
The process dispatch on Windows is slower than it is on \*nix. It may be
necessary to add '-t 15' to salt commands to give minions plenty of time to
return.

Windows and the Visual Studio Redist
------------------------------------
The Visual C++ 2008 32-bit redistributable will need to be installed on all
Windows minions. Esky has an option to pack the library into the zipfile,
but OpenSSL does not seem to acknowledge the new location. If a
``no OPENSSL_Applink`` error appears on the console when trying to start a
frozen minion, the redistributable is not installed.

Mixed Linux environments and Yum
--------------------------------
The Yum Python module doesn't appear to be available on any of the standard
Python package mirrors. If RHEL/CentOS systems need to be supported, the frozen
build should created on that platform to support all the Linux nodes. Remember
to build the virtualenv with ``--system-site-packages`` so that the ``yum``
module is included.

Automatic (Python) module discovery
-----------------------------------
Automatic (Python) module discovery does not work with the late-loaded scheme
that Salt uses for (Salt) modules. Any misbehaving modules will need to be
explicitly added to the ``freezer_includes`` in Salt's ``setup.py``.  Always
check the zipped application to make sure that the necessary modules were
included.