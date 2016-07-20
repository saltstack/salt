.. _virtual-shadow:

===================
salt.modules.shadow
===================

.. py:module:: salt.modules.shadow
    :synopsis: A virtual module for shadow file / password management

``shadow`` is a virtual module that is fulfilled by one of the following
modules:

====================================== ========================================
Execution Module                       Used for
====================================== ========================================
:py:mod:`~salt.modules.shadow`         Linux
:py:mod:`~salt.modules.bsd_shadow`     FreeBSD, OpenBSD, NetBSD
:py:mod:`~salt.modules.solaris_shadow` Solaris-based OSes
:py:mod:`~salt.modules.win_shadow`     Windows
====================================== ========================================

|

.. automodule:: salt.modules.shadow
    :members:

