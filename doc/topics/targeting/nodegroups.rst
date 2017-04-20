.. _targeting-nodegroups:

===========
Node groups
===========

Nodegroups are declared using a compound target specification. The compound
target documentation can be found :ref:`here <targeting-compound>`.

The :conf_master:`nodegroups` master config file parameter is used to define
nodegroups. Here's an example nodegroup configuration within
``/etc/salt/master``:

.. code-block:: yaml

    nodegroups:
      group1: 'L@foo.domain.com,bar.domain.com,baz.domain.com or bl*.domain.com'
      group2: 'G@os:Debian and foo.domain.com'
      group3: 'G@os:Debian and N@group1'
      group4:
        - 'G@foo:bar'
        - 'or'
        - 'G@foo:baz'

.. note::

    The ``L`` within group1 is matching a list of minions, while the ``G`` in
    group2 is matching specific grains. See the :ref:`compound matchers
    <targeting-compound>` documentation for more details.

    As of the Nitrogen release of Salt, group names can also be prepended with
    a dash. This brings the usage in line with many other areas of Salt. For
    example:

    .. code-block:: yaml

        nodegroups:
          - group1: 'L@foo.domain.com,bar.domain.com,baz.domain.com or bl*.domain.com'

.. versionadded:: 2015.8.0

.. note::

    Nodegroups can reference other nodegroups as seen in ``group3``.  Ensure
    that you do not have circular references.  Circular references will be
    detected and cause partial expansion with a logged error message.

.. versionadded:: 2015.8.0

Compound nodegroups can be either string values or lists of string values.
When the nodegroup is A string value will be tokenized by splitting on
whitespace.  This may be a problem if whitespace is necessary as part of a
pattern.  When a nodegroup is a list of strings then tokenization will
happen for each list element as a whole.

To match a nodegroup on the CLI, use the ``-N`` command-line option:

.. code-block:: bash

    salt -N group1 test.ping

.. note::

    The ``N@`` classifier cannot be used in compound matches within the CLI or
    :term:`top file`, it is only recognized in the :conf_master:`nodegroups`
    master config file parameter.

To match a nodegroup in your :term:`top file`, make sure to put ``- match:
nodegroup`` on the line directly following the nodegroup name.

.. code-block:: yaml

    base:
      group1:
        - match: nodegroup
        - webserver

.. note::

    When adding or modifying nodegroups to a master configuration file, the
    master must be restarted for those changes to be fully recognized.

    A limited amount of functionality, such as targeting with -N from the
    command-line may be available without a restart.

Defining Nodegroups as Lists of Minion IDs
==========================================

A simple list of minion IDs would traditionally be defined like this:

.. code-block:: yaml

    nodegroups:
      group1: L@host1,host2,host3

They can now also be defined as a YAML list, like this:

.. code-block:: yaml

    nodegroups:
      group1:
        - host1
        - host2
        - host3

.. versionadded:: 2016.11.0
