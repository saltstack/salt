.. _virtual-group:

==================
salt.modules.group
==================

.. py:module:: salt.modules.group
    :synopsis: A virtual module for group management

``group`` is a virtual module that is fulfilled by one of the following
modules:

====================================== ========================================
Execution Module                       Used for
====================================== ========================================
:py:mod:`~salt.modules.groupadd`       Linux, NetBSD, and OpenBSD systems using
                                       ``groupadd(8)``, ``groupdel(8)``, and
                                       ``groupmod(8)``
:py:mod:`~salt.modules.pw_group`       FreeBSD-based OSes using ``pw(8)``
:py:mod:`~salt.modules.solaris_group`  Solaris-based OSes using
                                       ``groupadd(1M)``, ``groupdel(1M)``, and
                                       ``groupmod(1M)``
:py:mod:`~salt.modules.win_groupadd`   Windows
====================================== ========================================
