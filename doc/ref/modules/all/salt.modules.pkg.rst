.. _virtual-pkg:

================
salt.modules.pkg
================

.. py:module:: salt.modules.pkg
    :synopsis: A virtual module for installing software packages

``pkg`` is a virtual module that is fulfilled by one of the following modules:

====================================== ========================================
Execution Module                       Used for
====================================== ========================================
:py:mod:`~salt.modules.aptpkg`         Debian/Ubuntu-based distros which use
                                       ``apt-get(8)`` for package management
:py:mod:`~salt.modules.brew`           Mac OS software management using
                                       `Homebrew`_
:py:mod:`~salt.modules.ebuild`         Gentoo-based systems (utilizes the
                                       ``portage`` python module as well as
                                       ``emerge(1)``)
:py:mod:`~salt.modules.freebsdpkg`     FreeBSD-based OSes using ``pkg_add(1)``
:py:mod:`~salt.modules.openbsdpkg`     OpenBSD-based OSes using ``pkg_add(1)``
:py:mod:`~salt.modules.pacman`         Arch Linux-based distros using
                                       ``pacman(8)``
:py:mod:`~salt.modules.pkgin`          NetBSD-based OSes using ``pkgin(1)``
:py:mod:`~salt.modules.pkgng`          FreeBSD-based OSes using ``pkg(8)``
:py:mod:`~salt.modules.pkgutil`        Solaris-based OSes using `OpenCSW`_'s
                                       ``pkgutil(1)``
:py:mod:`~salt.modules.solarispkg`     Solaris-based OSes using ``pkgadd(1M)``
:py:mod:`~salt.modules.solarisips`     Solaris-based OSes using IPS ``pkg(1)``
:py:mod:`~salt.modules.win_pkg`        Salt's :ref:`Windows Package Manager
                                       <windows-package-manager`
:py:mod:`~salt.modules.yumpkg`         RedHat-based distros and derivatives
                                       using ``yum(8)`` or ``dnf(8)``
:py:mod:`~salt.modules.zypper`         SUSE-based distros using ``zypper(8)``
====================================== ========================================

.. _Homebrew: http://brew.sh/
.. _OpenCSW: http://www.opencsw.org/

