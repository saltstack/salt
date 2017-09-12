.. _virtual-kernelpkg:

======================
salt.modules.kernelpkg
======================

.. py:module:: salt.modules.kernelpkg
    :synopsis: A virtual module for managing kernel packages

``kernelpkg`` is a virtual module that is fulfilled by one of the following modules:

============================================ ========================================
Execution Module                             Used for
============================================ ========================================
:py:mod:`~salt.modules.kernelpkg_linux_apt`  Debian/Ubuntu-based distros which use
                                             ``apt-get`` for package management
:py:mod:`~salt.modules.kernelpkg_linux_yum`  RedHat-based distros and derivatives
                                             using ``yum`` or ``dnf``
============================================ ========================================
