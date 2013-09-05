Frequently Asked Questions
==========================

This page contains a list of frequently asked questions, as well as some common
pitfalls to avoid.


Should I use :mod:`cmd.run <salt.states.cmd.run>` or :mod:`cmd.wait <salt.states.cmd.wait>`?
----------------------------------------------------------------------------------------------------

These two states are often confused. The important thing to remember about them
is that :mod:`cmd.run <salt.states.cmd.run>` states are run each time the SLS
file that contains them is applied. If it is more desirable to have a command
that only runs after some other state changes, then :mod:`cmd.wait
<salt.states.cmd.wait>` does just that. :mod:`cmd.wait <salt.states.cmd.wait>`
is designed to be :doc:`watched </ref/states/requisites>` by other states, and
executed when the state watching it changes. Example:

.. code-block:: yaml

    /usr/local/bin/postinstall.sh:
      cmd:
        - wait
      file:
        - managed
        - source: salt://utils/scripts/postinstall.sh

    mycustompkg:
      pkg:
        - installed
        - watch:
          - cmd: /usr/local/bin/postinstall.sh
        - require:
          - file: /usr/local/bin/postinstall.sh


How does Salt guess the Minion's hostname?
------------------------------------------

This process is explained in detail :ref:`here <minion-id-generation>`.


Why aren't my custom modules/states/etc. syncing to my Minions?
---------------------------------------------------------------

In versions 0.16.3 and older, when using the :doc:`git fileserver backend
</topics/tutorials/gitfs>`, certain versions of GitPython may generate errors
when fetching, which Salt fails to catch. While not fatal to the fetch process,
these interrupt the fileserver update that takes place before custom types are
synced, and thus interrupt the sync itself. Try disabling the git fileserver
backend in the master config, restarting the master, and attempting the sync
again.

This issue will be worked around in Salt 0.16.4 and newer.
