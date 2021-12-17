.. _targeting-glob:

==========================
Matching the ``minion id``
==========================

Each minion needs a unique identifier. By default when a minion starts for the
first time it chooses its :abbr:`FQDN (fully qualified domain name)` as that
identifier. The minion id can be overridden via the minion's :conf_minion:`id`
configuration setting.

.. tip:: minion id and minion keys

    The :term:`minion id <Minion ID>` is used to generate the minion's public/private keys
    and if it ever changes the master must then accept the new key as though
    the minion was a new host.

Globbing
========

The default matching that Salt utilizes is :py:mod:`shell-style globbing
<python2:fnmatch>` around the :term:`minion id <Minion ID>`. This also works for states
in the :term:`top file <Top File>`.

.. note::

    You must wrap :command:`salt` calls that use globbing in single-quotes to
    prevent the shell from expanding the globs before Salt is invoked.

Match all minions:

.. code-block:: bash

    salt '*' test.version

Match all minions in the example.net domain or any of the example domains:

.. code-block:: bash

    salt '*.example.net' test.version
    salt '*.example.*' test.version

Match all the ``webN`` minions in the example.net domain (``web1.example.net``,
``web2.example.net`` … ``webN.example.net``):

.. code-block:: bash

    salt 'web?.example.net' test.version

Match the ``web1`` through ``web5`` minions:

.. code-block:: bash

    salt 'web[1-5]' test.version

Match the ``web1`` and ``web3`` minions:

.. code-block:: bash

    salt 'web[1,3]' test.version

Match the ``web-x``, ``web-y``, and ``web-z`` minions:

.. code-block:: bash

    salt 'web-[x-z]' test.version

.. note::

    For additional targeting methods please review the
    :ref:`compound matchers <targeting-compound>` documentation.


Regular Expressions
===================

Minions can be matched using Perl-compatible :py:mod:`regular expressions
<python2:re>` (which is globbing on steroids and a ton of caffeine).

Match both ``web1-prod`` and ``web1-devel`` minions:

.. code-block:: bash

    salt -E 'web1-(prod|devel)' test.version

When using regular expressions in a State's :term:`top file <Top File>`, you must specify
the matcher as the first option. The following example executes the contents of
``webserver.sls`` on the above-mentioned minions.

.. code-block:: yaml

    base:
      'web1-(prod|devel)':
      - match: pcre
      - webserver


Lists
=====

At the most basic level, you can specify a flat list of minion IDs:

.. code-block:: bash

    salt -L 'web1,web2,web3' test.version
