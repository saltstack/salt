.. _configuration-management:

========================
Configuration Management
========================

Salt contains a robust and flexible configuration management framework, which
is built on the remote execution core. This framework executes on the minions,
allowing effortless, simultaneous configuration of tens of thousands of hosts,
by rendering language specific state files. The following links provide
resources to learn more about state and renderers.

**States**
    Express the state of a host using small, easy to read, easy to
    understand configuration files. *No programming required*.

    :ref:`Full list of states <all-salt.states>`
        Contains: list of install packages, create users, transfer files, start
        services, and so on.

    :doc:`Pillar System <../pillar/index>`
        Contains: description of Salt's Pillar system.

    :doc:`Highstate data structure <../../ref/states/highstate>`
        Contains: a dry vocabulary and technical representation of the
        configuration format that states represent.

    :doc:`Writing states <../../ref/states/writing>`
        Contains: a guide on how to write Salt state modules, easily extending
        Salt to directly manage more software.

.. note::

    Salt execution modules are different from state modules and cannot be
    called directly within state files.  You must use the :mod:`module <salt.states.module>`
    state module to call execution modules within state runs.

**Renderers**
    Renderers use state configuration files written in a variety of languages,
    templating engines, or files. Salt's configuration management system is,
    under the hood, language agnostic.

    :doc:`Full list of renderers <../../ref/renderers/all/index>`
        Contains: a list of renderers.
        YAML is one choice, but many systems are available, from
        alternative templating engines to the PyDSL language for rendering
        sls formulas.

    :doc:`Renderers <../../ref/renderers/index>`
        Contains: more information about renderers. Salt states are only
        concerned with the ultimate highstate data structure, not how the
        data structure was created.


.. toctree::
    :maxdepth: 1

    ../tutorials/starting_states
    ../tutorials/states_pt1
    ../tutorials/states_pt2
    ../tutorials/states_pt3
    ../tutorials/states_pt4
    ../../ref/states/index

