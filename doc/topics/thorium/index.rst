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

.. code-block:: yaml

    engines:
      - thorium: {}

Writing Thorium Formulas
========================

To start with Thorium create the Thorium state tree, the state tree for Thorium
looks exactly like the Salt Configuration Management state tree, it is just
located in the `thorium_roots_dir` instead of the `file_roots_dir`. The default
location for the `thorium_roots_dir` is `/srv/thorium`.

This example uses thorium to detect when a minion has disappeared and then
deletes the key from the master when the minion has been gone for 60 seconds:


.. code-block:: yaml

    startreg:
      status.reg

    keydel:
      key.timeout:
        - require:
          - status: statreg
        - delete: 60

Remember to set up a top file so Thorium knows which sls files to use!!

.. code-block:: yaml

    base:
      '*':
        - key_clean

Thorium Links to Beacons
========================

The above example was added in the Carbon release of Salt and makes use of the
`status` beacon also added in the Carbon release. For the above Thorium state
to function properly you will also need to enable the `status` beacon:

.. code-block:: yaml

    beacons:
      status:
        interval: 10
