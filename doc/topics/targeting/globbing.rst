==========================
Matching the ``minion id``
==========================

.. glossary::

    minion id
        A unique identifier for a given minion. By default the minion id is the
        FQDN of that host but this can be overridden.

Each minion needs a unique identifier. By default when a minion starts for the
first time it chooses its :abbr:`FQDN (fully qualified domain name)` as that
identifier. The minion id can be overridden via the minion's :conf_minion:`id`
configuration setting.

.. tip:: minion id and minion keys

    The :term:`minion id` is used to generate the minion's public/private keys
    and if it ever changes the master must then accept the new key as though
    the minion was a new host.

Globbing
========

The default matching that Salt utilizes is `shell-style globbing`_ around the
:term:`minion id`. This also works for states in the :term:`top file`.

.. note::

    You must wrap :command:`salt` calls that use globbing in single-quotes to
    prevent the shell from expanding the globs before Salt is invoked.

Match all minions::

    salt '*' test.ping

Match all minions in the example.net domain or any of the example domains::

    salt '*.example.net' test.ping
    salt '*.example.*' test.ping

Match all the ``webN`` minions in the example.net domain
(``web1.example.net``, ``web2.example.net`` … ``webN.example.net``)::

    salt 'web?.example.net test.ping

Match the ``web1`` through ``web5`` minions::

    salt 'web[1-5]' test.ping

Match the ``web-x``, ``web-y``, and ``web-z`` minions::

    salt 'web-[x-z]' test.ping
    
.. _`shell-style globbing`: http://docs.python.org/library/fnmatch.html

Regular Expressions
===================

Minions can be matched using Perl-compatible `regular expressions`_ (which is
globbing on steroids and a ton of caffeine).

Match both ``web1-prod`` and ``web1-devel`` minions::

    salt -E 'web1-(prod|devel)' test.ping

When using regular expressions in a State's :term:`top file`, you must specify
the matcher as the first option. The following example executes the contents of
``webserver.sls`` on the above-mentioned minions.

.. code-block:: yaml

    base:
      'web1-(prod|devel)':
      - match: pcre
      - webserver
      
.. _`regular expressions`: http://docs.python.org/library/re.html#module-re

Lists
=====

At the most basic level, you can specify a flat list of minion IDs::

    salt -L 'web1,web2,web3' test.ping
