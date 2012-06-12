=================
Compound matchers
=================

.. glossary::

    Compound matcher
        A combination of many target definitions that can be combined with
        boolean operators.

Compound matchers allow very granular minion targeting using any of the
previously discussed matchers. The default matcher is a `glob`_, as usual. For
matching via anything other than glob, preface it with the letter denoting
the match type. The currently implemented "letters" are:

====== ==================== ===============================================================
Letter Meaning              Example
====== ==================== ===============================================================
G      Grains glob match    ``G@os:Ubuntu``
E      PCRE Minion id match ``E@web\d+\.(dev|qa|prod)\.loc``
P      Grains PCRE match    ``P@os:(RedHat|Fedora|CentOS)``
L      List of minions      ``L@minion1.example.com,minion3.domain.com and bl*.domain.com``
I      Pillar glob match    ``I@pdata:foobar``
====== ==================== ===============================================================

Matchers can be joined using boolean ``and``, ``or``, and ``not`` operators.

For example, the following command matches all minions that have a hostname
that begins with "webserv" and that are running Debian or it matches any
minions that have a hostname that matches the `regular expression`_
``web-dc1-srv.*``::

    salt -C 'webserv* and G@os:Debian or E@web-dc1-srv.*' test.ping

That same example expressed in a :term:`top file` looks like the following::

    base:
      'webserv* and G@os:Debian or E@web-dc1-srv.*':
        - match: compound
        - webserver

.. _`glob`: http://docs.python.org/library/fnmatch.html
.. _`regular expression`: http://docs.python.org/library/re.html#module-re
