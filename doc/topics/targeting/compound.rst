.. _targeting-compound:

=================
Compound matchers
=================

Compound matchers allow very granular minion targeting using any of Salt's
matchers. The default matcher is a :mod:`glob <python2:fnmatch>` match, just as
with CLI and :term:`top file` matching. To match using anything other than a
glob, prefix the match string with the appropriate letter from the table below,
followed by an ``@`` sign.

====== ==================== ============================================================== =============================================
Letter Match Type           Example                                                        :ref:`Alt Delimiter? <target-alt-delimiters>`
====== ==================== ============================================================== =============================================
G      Grains glob          ``G@os:Ubuntu``                                                Yes
E      PCRE Minion ID       ``E@web\d+\.(dev|qa|prod)\.loc``                               No
P      Grains PCRE          ``P@os:(RedHat|Fedora|CentOS)``                                Yes
L      List of minions      ``L@minion1.example.com,minion3.domain.com or bl*.domain.com`` No
I      Pillar glob          ``I@pdata:foobar``                                             Yes
J      Pillar PCRE          ``J@pdata:^(foo|bar)$``                                        Yes
S      Subnet/IP address    ``S@192.168.1.0/24`` or ``S@192.168.1.100``                    No
R      Range cluster        ``R@%foo.bar``                                                 No
====== ==================== ============================================================== =============================================

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

.. versionadded:: 2015.8.0

Excluding a minion based on its ID is also possible:

.. code-block:: bash

    salt -C 'not web-dc1-srv' test.ping

Versions prior to 2015.8.0 a leading ``not`` was not supported in compound
matches. Instead, something like the following was required:

.. code-block:: bash

    salt -C '* and not G@kernel:Darwin' test.ping

Excluding a minion based on its ID was also possible:

.. code-block:: bash

    salt -C '* and not web-dc1-srv' test.ping

Precedence Matching
-------------------

Matchers can be grouped together with parentheses to explicitly declare precedence amongst groups.

.. code-block:: bash

    salt -C '( ms-1 or G@id:ms-3 ) and G@id:ms-3' test.ping

.. note::

    Be certain to note that spaces are required between the parentheses and targets. Failing to obey this
    rule may result in incorrect targeting!

.. _target-alt-delimiters:

Alternate Delimiters
--------------------

.. versionadded:: 2015.8.0

Matchers that target based on a key value pair use a colon (``:``) as
a delimiter. Matchers with a ``Yes`` in the ``Alt Delimiters`` column
in the previous table support specifying an alternate delimiter character.

This is done by specifying an alternate delimiter character between the leading
matcher character and the ``@`` pattern separator character. This avoids
incorrect interpretation of the pattern in the case that ``:`` is part of the
grain or pillar data structure traversal.

.. code-block:: bash

    salt -C 'J|@foo|bar|^foo:bar$ or J!@gitrepo!https://github.com:example/project.git' test.ping
