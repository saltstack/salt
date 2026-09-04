.. _resources-tutorial:

========================================
Salt Resources: a 10-minute walk-through
========================================

.. versionadded:: 3008.0

This tutorial takes the bundled ``dummy`` resource type from "what is
this thing?" to a working ``state.apply`` against three dummy
resources, using nothing but a single masterless minion config. By
the end you'll have exercised every part of the framework: pillar
declaration, registration, targeting, per-resource execution, and
merge-mode state apply.


Why the dummy type?
===================

The dummy resource is a self-contained, filesystem-backed
implementation that lives in :py:mod:`salt.resources.dummy`. It needs
no external services, no SSH targets, no API tokens. It is the
resource analogue of the ``salt.proxy.dummy`` proxy module — built so
you can exercise the framework end-to-end without managing anything
real.


Setup
=====

We'll run the whole thing with ``salt-call --local`` (masterless). One
config file, one pillar file. Adjust paths to taste.

``/etc/salt/minion.d/tutorial.conf``:

.. code-block:: yaml

    file_client: local
    file_roots:
      base:
        - /srv/salt
    pillar_roots:
      base:
        - /srv/pillar

``/srv/pillar/top.sls``:

.. code-block:: yaml

    base:
      '*':
        - resources

``/srv/pillar/resources.sls``:

.. code-block:: yaml

    resources:
      dummy:
        resource_ids:
          - dummy-01
          - dummy-02
          - dummy-03

Confirm pillar reads correctly:

.. code-block:: bash

    salt-call --local pillar.get resources unmask=True
    # {'dummy': {'resource_ids': ['dummy-01', 'dummy-02', 'dummy-03']}}

(The ``unmask=True`` is required in 3008.0+: pillar values are masked
by default at the CLI. SLS files render with masking disabled.)


Step 1 — confirm discovery
==========================

The managing minion discovers resource types from the pillar on every
pillar refresh. The first run after editing pillar will pick them up:

.. code-block:: bash

    salt-call --local saltutil.refresh_pillar

In masterless mode there's no registry to populate, but the minion
caches its own view. You can confirm:

.. code-block:: bash

    salt-call -r --tgt '*' test.ping

If you see something like::

    local:
        ----------
        <managing-minion-id>: True
        dummy-01: True
        dummy-02: True
        dummy-03: True

…the framework loaded the dummy resource type, called ``ping()``
against each declared id, and folded the results. If you only see the
managing minion, double-check pillar.


Step 2 — per-resource targeting
===============================

Every targeting form Salt offers against minions works against
resources too. Try a few:

.. code-block:: bash

    # All dummy resources by type
    salt-call -r --tgt 'T@dummy' --tgt-type compound test.ping

    # One specific resource
    salt-call -r --tgt 'dummy-02' test.ping

    # By per-resource grain
    salt-call -r --tgt 'dummy_grain_1:one' --tgt-type grain test.ping

The dummy resource publishes a small fixed grain dict
(``dummy_grain_1``, ``dummy_grain_2``, ``dummy_grain_3``, plus
``resource_id``). All four match the same set of three resources here.


Step 3 — inspect grains
=======================

``grains.items`` works per-resource. Without ``-r`` you'd see the
managing minion's grains; with ``-r`` and a resource target you see
the resource's:

.. code-block:: bash

    salt-call -r --tgt dummy-01 grains.items

    # local:
    #     ----------
    #     dummy-01:
    #         ----------
    #         dummy_grain_1: one
    #         dummy_grain_2: two
    #         dummy_grain_3: three
    #         resource_id:   dummy-01


Step 4 — exercise a state
=========================

The dummy type ships an execution function ``test_from_state()``. We
can wrap it in a tiny state:

``/srv/salt/dummy/test.sls``:

.. code-block:: yaml

    say_hello:
      cmd.run:
        - name: echo "dummy resource state running"

    do_the_thing:
      module.run:
        - dummy.test_from_state: []

Apply it against all dummy resources at once:

.. code-block:: bash

    salt-call -r --tgt 'T@dummy' --tgt-type compound state.apply dummy.test

This exercises merge-mode ``state.apply``: the managing minion runs
the apply for each of the three resources inline and produces one
combined output. Look at the keys — each state ID is prefixed with
the resource id so provenance is visible:

.. code-block:: text

    cmd_|-dummy-01 say_hello_|-dummy-01 echo "..."_|-run
    cmd_|-dummy-02 say_hello_|-dummy-02 echo "..."_|-run
    cmd_|-dummy-03 say_hello_|-dummy-03 echo "..."_|-run
    module_|-dummy-01 do_the_thing_|-dummy-01 dummy.test_from_state_|-run
    module_|-dummy-02 do_the_thing_|-dummy-02 dummy.test_from_state_|-run
    module_|-dummy-03 do_the_thing_|-dummy-03 dummy.test_from_state_|-run

One ``Summary`` line at the bottom shows the rolled-up pass/fail. See
:ref:`resources-state-authoring` for the prefixing rules.


Step 5 — write your own
=======================

You've used a resource type — now write one. The dummy module under
:py:mod:`salt.resources.dummy` is ~300 lines and covers every hook the
framework expects. Mirror its shape under
``saltext/<yourext>/resources/<yourtype>/`` to ship a type in an
extension; see :ref:`resources-authoring` for the interface contract
and :ref:`resources-authoring-packaging` for the entry-point wiring.


What's next
===========

* :ref:`resources-architecture` — what's actually going on behind the
  ``-r --tgt`` flag.
* :ref:`resources-authoring` — write your own resource type.
* :ref:`resources-operations` — operator commands for inspecting,
  refreshing, and debugging.
* :ref:`resources-configuration` — every ``resource_*`` option.
