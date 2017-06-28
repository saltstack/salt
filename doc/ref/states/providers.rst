.. _state-providers:

===============
State Providers
===============

.. versionadded:: 0.9.8

Salt predetermines what modules should be mapped to what uses based on the
properties of a system. These determinations are generally made for modules
that provide things like package and service management.

Sometimes in states, it may be necessary to use an alternative module to
provide the needed functionality. For instance, an very old Arch Linux system
may not be running systemd, so instead of using the systemd service module, you
can revert to the default service module:

.. code-block:: yaml

    httpd:
      service.running:
        - enable: True
        - provider: service

In this instance, the basic :py:mod:`~salt.modules.service` module (which
manages :program:`sysvinit`-based services) will replace the
:py:mod:`~salt.modules.systemd` module which is used by default on Arch Linux.

This change only affects this one state though. If it is necessary to make this
override for most or every service, it is better to just override the provider
in the minion config file, as described :ref:`here <module-provider-override>`.

Also, keep in mind that this only works for states with an identically-named
virtual module (:py:mod:`~salt.states.pkg`, :py:mod:`~salt.states.service`,
etc.).

Arbitrary Module Redirects
==========================

The provider statement can also be used for more powerful means, instead of
overwriting or extending the module used for the named service an arbitrary
module can be used to provide certain functionality.

.. code-block:: yaml

    emacs:
      pkg.installed:
        - provider:
          - cmd: customcmd

In this example, the state is being instructed to use a custom module to invoke
commands.

Arbitrary module redirects can be used to dramatically change the behavior of a
given state.
