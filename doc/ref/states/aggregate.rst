=========================================
Mod Aggregate State Runtime Modifications
=========================================

.. versionadded:: Helium

The mod_aggregate system was added in the Helium release of Salt and allows for
runtime modification of the executing state data. Simply put, it allows for the
data used by Salt's state system to be changed on the fly at runtime, kind of
like a configuration management JIT compiler or a runtime import system. All in
all, it makes Salt much more dynamic.

How it Works
============

The best example is the `pkg` state. One of the major requests in Salt has long
been adding the ability to install all packages defined at the same time. The
mod_aggregate system makes this a reality. While executing Salt's state system,
when a `pkg` state is reached the ``mod_agregate`` function in the state module
is called. For `pkg` this function scans all of the other states that are slated
to run, and picks up the references to ``name`` and ``pkgs``, then adds them to
``pkgs`` in the first state. The result is calling yum/apt-get/pacman etc. just
once to install of the packages as part of the first package install.

How to Use it
=============


.. note::

    Since this option changes the basic behavior of the state runtime states
    should be executed in 

Since this behavior can dramatically change the flow of configuration
management inside of Salt it is disabled by default. But enabling it is easy.

To enable for all states just add:

.. code-block:: yaml

    state_aggregate: True

Similarly only specific states can be enabled:

.. code-block:: yaml

    state_aggregate:
      - pkg

To the master or minion config and restart the master or minion, if this option
is set in the master config it will apply to all state runs on all minions, if
set in the minion config it will only apply to said minion.
