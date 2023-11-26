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

    :ref:`Pillar System <pillar>`
        Contains: description of Salt's Pillar system.

    :ref:`Highstate data structure <states-highstate>`
        Contains: a dry vocabulary and technical representation of the
        configuration format that states represent.

    :ref:`Writing states <state-modules>`
        Contains: a guide on how to write Salt state modules, easily extending
        Salt to directly manage more software.

.. note::

    Salt execution modules are different from state modules and cannot be
    called as a state in an SLS file. In other words, this will not work:

    .. code-block:: yaml

        moe:
          user.rename:
            - new_name: larry
            - onlyif: id moe

    You must use the :mod:`module <salt.states.module>` states to call
    execution modules directly. Here's an example:

    .. code-block:: yaml

       rename_moe:
         module.run:
           - name: user.rename
           - m_name: moe
           - new_name: larry
           - onlyif: id moe

**Renderers**
    Renderers use state configuration files written in a variety of languages,
    templating engines, or files. Salt's configuration management system is,
    under the hood, language agnostic.

    :ref:`Full list of renderers <all-salt.renderers>`
        Contains: a list of renderers.
        YAML is one choice, but many systems are available, from
        alternative templating engines to the PyDSL language for rendering
        sls formulas.

    :ref:`Renderers <renderers>`
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
