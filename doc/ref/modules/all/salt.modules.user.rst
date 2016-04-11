.. _virtual-user:

=================
salt.modules.user
=================

.. py:module:: salt.modules.user
    :synopsis: A virtual module for user management

``user`` is a virtual module that is fulfilled by one of the following modules:

====================================== ========================================
Execution Module                       Used for
====================================== ========================================
:py:mod:`~salt.modules.useradd`        Linux, NetBSD, and OpenBSD systems using
                                       ``useradd(8)``, ``userdel(8)``, and
                                       ``usermod(8)``
:py:mod:`~salt.modules.pw_user`        FreeBSD-based OSes using ``pw(8)``
:py:mod:`~salt.modules.solaris_user`   Solaris-based OSes using
                                       ``useradd(1M)``, ``userdel(1M)``, and
                                       ``usermod(1M)``
:py:mod:`~salt.modules.mac_user`       MacOS
:py:mod:`~salt.modules.win_useradd`    Windows
====================================== ========================================
