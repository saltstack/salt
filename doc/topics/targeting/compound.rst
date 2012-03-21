=================
Compound matchers
=================

.. glossary::

    Compound matcher
        A combination of many target definitions that can be combined with
        boolean operators.

Compound matchers allow very granular minion targeting using any of the
previously discussed matchers. The default matcher is a glob, as usual. If
something other than a glob is used preface it with the letter denoting the
type. Matchers can be joined using boolean ``and``, ``or``, and ``not``
operators.

For example, the following command matches all minions that have a hostname
that begins with "webserv" and that are running Debian or it matches any
minions that have a hostname that matches the regular expression
``web-dc1-srv.*``::

    salt -C 'webserv* and G@os:Debian or E@web-dc1-srv.*' test.ping

That same example expressed in a :term:`top file` looks like the following::

    base:
      'webserv* and G@os:Debian or E@web-dc1-srv.*':
        - match: compound
        - webserver
