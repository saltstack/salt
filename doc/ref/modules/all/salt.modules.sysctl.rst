.. _virtual-sysctl:

===================
salt.modules.sysctl
===================

.. py:module:: salt.modules.sysctl
    :synopsis: A virtual module for managing sysctl parameters

``sysctl`` is a virtual module that is fulfilled by one of the following modules:

============================================ ========================================
Execution Module                             Used for
============================================ ========================================
:py:mod:`~salt.modules.freebsd_sysctl`       FreeBSD
:py:mod:`~salt.modules.linux_sysctl`         Linux
:py:mod:`~salt.modules.mac_sysctl`           macOS
:py:mod:`~salt.modules.netbsd_sysctl`        NetBSD
:py:mod:`~salt.modules.openbsd_sysctl`       OpenBSD
============================================ ========================================
