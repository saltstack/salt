.. _targeting-compound:

=================
Compound matchers
=================

Compound matchers allow very granular minion targeting using any of Salt's
matchers. The default matcher is a :mod:`glob <python2:fnmatch>` match, just as
with CLI and :term:`top file` matching. To match using anything other than a
glob, prefix the match string with the appropriate letter from the table below,
followed by an ``@`` sign.

====== ========= ==================== ==============================================================
Letter Delimiter Match Type           Example
====== ========= ==================== ==============================================================
G      x         Grains glob          ``G@os:Ubuntu``
E                PCRE Minion ID       ``E@web\d+\.(dev|qa|prod)\.loc``
P      x         Grains PCRE          ``P@os:(RedHat|Fedora|CentOS)``
L                List of minions      ``L@minion1.example.com,minion3.domain.com or bl*.domain.com``
I      x         Pillar glob          ``I@pdata:foobar``
J      x         Pillar PCRE          ``J@pdata:^(foo|bar)$``
S                Subnet/IP address    ``S@192.168.1.0/24`` or ``S@192.168.1.100``
R                Range cluster        ``R@%foo.bar``
====== ========= ==================== ==============================================================


Matchers can be joined using boolean ``and``, ``or``, and ``not`` operators.

For example, the following string matches all Debian minions with a hostname
that begins with ``webserv``, as well as any minions that have a hostname which
matches the :mod:`regular expression <python2:re>` ``web-dc1-srv.*``:

.. code-block:: bash

    salt -C 'webserv* and G@os:Debian or E@web-dc1-srv.*' test.ping

That same example expressed in a :term:`top file` looks like the following:

.. code-block:: yaml

    base:
      'webserv* and G@os:Debian or E@web-dc1-srv.*':
        - match: compound
        - webserver

.. versionadded:: Beryllium

Excluding a minion based on its ID is also possible:

.. code-block:: bash

    salt -C 'not web-dc1-srv' test.ping

Versions prior to Beryllium a leading ``not`` was not supported in compound
matches. Instead, something like the following was required:

.. code-block:: bash

    salt -C '* and not G@kernel:Darwin' test.ping

Excluding a minion based on its ID was also possible:

.. code-block:: bash

    salt -C '* and not web-dc1-srv' test.ping

Precedence Matching
-------------------

Matches can be grouped together with parentheses to explicitly declare precedence amongst groups.

.. code-block:: bash

    salt -C '( ms-1 or G@id:ms-3 ) and G@id:ms-3' test.ping

.. note::

    Be certain to note that spaces are required between the parentheses and targets. Failing to obey this
    rule may result in incorrect targeting!

Alternate Delimiters
--------------------

.. versionadded:: Beryllium

Some matchers allow an optional delimiter character specified between the
leading matcher character and the ``@`` pattern separator character.  This
can be essential when the globbing or PCRE pattern may use the default
delimiter character ``:``.  This avoids incorrect interpretation of the
pattern as part of the grain or pillar data structure traversal.

.. code-block:: bash

    salt -C 'J|@foo|bar|^foo:bar$ or J!@gitrepo!https://github.com:example/project.git' test.ping
