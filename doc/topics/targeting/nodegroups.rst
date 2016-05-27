.. _targeting-nodegroups:

===========
Node groups
===========

Nodegroups are declared using a compound target specification. The compound
target documentation can be found :doc:`here <compound>`.

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
    group2 is matching specific grains. See the :doc:`compound matchers
    <compound>` documentation for more details.

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

    The ``N@`` classifier cannot be used in compound mathes within the CLI or
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

    When adding or modifying nodegroups to a master configuration file, the master must be restarted
    for those changes to be fully recognized.

    A limited amount of functionality, such as targeting with -N from the command-line may be
    available without a restart.

Using Nodegroups in SLS files
=============================

To use Nodegroups in Jinja logic for SLS files, the :conf_master:`pillar_opts` option in
``/etc/salt/master`` must be set to "True". This will pass the master's configuration as
Pillar data to each minion.

.. note::

    If the master's configuration contains any sensitive data, this will be passed to each minion.
    Do not enable this option if you have any configuration data that you do not want to get
    on your minions.

    Also, if you make changes to your nodegroups, you might need to run
    ``salt '*' saltutil.refresh_pillar`` after restarting the master.

Once pillar_opts is enabled, you can find the nodegroups under the "master" pillar.
To make sure that only the correct minions are targeted,
you should use each matcher for the nodegroup definition.
For example, to check if a minion is in the 'webserver' nodegroup:

.. code-block:: yaml

    nodegroups:
      webserver: 'G@os:Debian and L@minion1,minion2'

.. code-block:: yaml

    {% if grains.id in salt['pillar.get']('master:nodegroups:webserver', [])
    and grains.os in salt['pillar.get']('master:nodegroups:webserver', []) %}
    ...
    {% endif %}

.. note::

    If you do not include all of the matchers used to define a nodegroup,
    Salt might incorrectly target minions that meet some of the nodegroup
    requirements, but not all of them.
