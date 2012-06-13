=========
Targeting
=========

.. glossary::

    Targeting
        Specifying which minions should run a command or execute a state by
        matching against hostnames, or system information, or defined groups,
        or even combinations thereof.

For example the command ``salt web1 apache.signal restart`` to restart the
Apache httpd server specifies the machine ``web1`` as the target and the
command will only be run on that one minion.

Similarly when using States, the following :term:`top file` specifies that only
the ``web1`` minion should execute the contents of ``webserver.sls``:

.. code-block:: yaml

    base:
      'web1':
        - webserver

There are many ways to target individual minions or groups of minions in Salt:

.. toctree::
    :maxdepth: 2

    globbing
    grains
    nodegroups
    compound
    batch
