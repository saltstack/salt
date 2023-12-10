.. _virtual-service:

====================
salt.modules.service
====================

.. py:module:: salt.modules.service
    :synopsis: A virtual module for service management

``service`` is a virtual module that is fulfilled by one of the following
modules:

========================================= ========================================
Execution Module                          Used for
========================================= ========================================
:py:mod:`~salt.modules.debian_service`    Debian Wheezy and earlier
:py:mod:`~salt.modules.freebsdservice`    FreeBSD-based OSes using ``service(8)``
:py:mod:`~salt.modules.gentoo_service`    Gentoo Linux using ``sysvinit`` and
                                          ``rc-update(8)``
:py:mod:`~salt.modules.mac_service`       Mac OS hosts using ``launchctl(1)``
:py:mod:`~salt.modules.netbsdservice`     NetBSD-based OSes
:py:mod:`~salt.modules.openbsdservice`    OpenBSD-based OSes
:py:mod:`~salt.modules.rh_service`        RedHat-based distros and derivatives
                                          using ``service(8)`` and
                                          ``chkconfig(8)``. Supports both pure
                                          sysvinit and mixed sysvinit/upstart
                                          systems.
:py:mod:`~salt.modules.service`           Fallback which simply wraps sysvinit
                                          scripts
:py:mod:`~salt.modules.smf_service`       Solaris-based OSes which use SMF
:py:mod:`~salt.modules.systemd_service`   Linux distros which use systemd
:py:mod:`~salt.modules.upstart_service`   Ubuntu-based distros using upstart
:py:mod:`~salt.modules.win_service`       Windows
========================================= ========================================
