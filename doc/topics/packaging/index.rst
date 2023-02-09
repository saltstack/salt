.. _pkging-introduction:

================
Onedir Packaging
================

Relenv onedir packaging
=======================

Starting in 3006, only onedir packaging will be available. The 3006 onedir packages
are built with the `relenv <https://github.com/saltstack/relative-environment-for-python>`_ tool.

How to build rpm packages
=========================

You only need to run rpmbuild in the Salt repo:

.. code-block:: bash

    # rpmbuild -bb --define="_salt_src $(pwd)" $(pwd)/pkg/rpm/salt.spec


How to build deb packages
=========================

You only need to add a symlink and run debuild in the Salt repo:

.. code-block:: bash

    # ln -s pkg/deb/debian debian
    # debuild -uc -us


How to access python binary
===========================

The python library is available in the install directory of the onedir package. For example
on linux the default location would be ``/opt/saltstack/salt/bin/python3``.
