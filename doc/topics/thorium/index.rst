.. _thorium-reactor:

=======================
Thorium Complex Reactor
=======================

.. note::

    Thorium is a provisional feature of Salt and is subject to change
    and removal if the feature proves to not be a viable solution.

.. note::

    Thorium was added to Salt as an experimental feature in the 2016.3.0
    release, as of 2016.3.0 this feature is considered experimental, no
    guarantees are made for support of any kind yet.


The original Salt Reactor is based on the idea of listening for a specific
event and then reacting to it. This model comes with many logical limitations,
for instance it is very difficult (and hacky) to fire a reaction based on
aggregate data or based on multiple events.

The Thorium reactor is intended to alleviate this problem in a very elegant way.
Instead of using extensive jinja routines or complex python sls files the
aggregation of data and the determination of what should run becomes isolated
to the sls data logic, makes the definitions much cleaner.


Starting the Thorium Engine
===========================

To enable the thorium engine add the following configuration to the engines
section of your Salt Master or Minion configuration file and restart the daemon:

.. code_block:: yaml

    engines:
      - thorium: {}

Writing Thorium Formulas
========================

To start with Thorium create the Thorium state tree, the state tree for Thorium
looks exactly like the Salt Configuration Management state tree, it is just
located in the `thorium_roots_dir` instead of the `file_roots_dir`. The default
location for the `thorium_roots_dir` is `/srv/thorium`.

This VERY simple example maintains a file on the master with all minion logins:


.. code_block:: yaml

    failed_logins:
      reg.list:
        - add:
            - user
            - id
        - match: /salt/beacon/\*/btmp*

    save_reg:
      file.save:
        - reg: failed_logins
