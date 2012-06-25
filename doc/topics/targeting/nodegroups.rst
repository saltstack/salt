===========
Node groups
===========

.. glossary::

    Node group
        A predefined group of minions declared in the master configuration file
        :conf_master:`nodegroups` setting as a compound target.

For example, in the master config file :conf_master:`nodegroups` setting::

    nodegroups:
      group1: 'L@foo.domain.com,bar.domain.com,baz.domain.com and bl*.domain.com'
      group2: 'G@os:Debian and foo.domain.com'

Specify a nodegroup via the ``-N`` option at the command-line::

    salt -N group1 test.ping

Specify a nodegroup with ``- match: nodegroup`` in a :term:`top file`::

    base:
      group1:
        - match: nodegroup
        - webserver
