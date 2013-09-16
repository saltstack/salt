Frequently Asked Questions
==========================

Is Salt open-core?
------------------

No. Salt is 100% committed to being open-source, including all of our APIs and
the new `'Halite' web interface`_ which will be included in version 0.17.0. It
is developed under the `Apache 2.0 license`_, allowing it to be used in both
open and proprietary projects.

.. _`'Halite' web interface`: https://github.com/saltstack/halite
.. _`Apache 2.0 license`: http://www.apache.org/licenses/LICENSE-2.0.html

What ports should I open on my firewall?
----------------------------------------

Minions need to be able to connect to the Master on TCP ports 4505 and 4506.
Minions do not need any inbound ports open. More detailed information on
firewall settings can be found :doc:`here </topics/tutorials/firewall>`.

My script runs every time I run a :mod:`state.highstate <salt.modules.state.highstate>`. Why?
---------------------------------------------------------------------------------------------

You are probably using :mod:`cmd.run <salt.states.cmd.run>` rather than
:mod:`cmd.wait <salt.states.cmd.wait>`. A :mod:`cmd.wait
<salt.states.cmd.wait>` state will only run when there has been a change in a
state that it is watching.

A :mod:`cmd.run <salt.states.cmd.run>` state will run the corresponding command
*every time* (unless it is prevented from running by the ``unless`` or ``onlyif``
arguments).

More details can be found in the docmentation for the :mod:`cmd
<salt.states.cmd>` states.

When I run :mod:`test.ping <salt.modules.test.ping>`, why do the Minions that aren't responding return anything? Returning ``False`` would be helpful.
------------------------------------------------------------------------------------------------------------------------------------------------------

The reason for this is because the Master tells Minions to run
commands/functions, and listens for the return data, printing it to the screen
when it is received. If it doesn't receive anything back, it doesn't have
anything to display for that Minion.

There are a couple options for getting information on Minions that are not
responding. One is to use the verbose (``-v``) option when you run salt
commands, as it will display "Minion did not return" for any Minions which time
out.

.. code-block:: bash

    salt -v '*' pkg.install zsh

Another option is to use the :mod:`manage.down <salt.runners.manage.down>`
runner:

.. code-block:: bash

    salt-run manage.down

How does Salt determine the Minion's id?
----------------------------------------

If the Minion id is not configured explicitly (using the :conf_minion:`id`
parameter), Salt will determine the id based on the hostname. Exactly how this
is determined varies a little between operating systems and is described in
detail :ref:`here <minion-id-generation>`.

I'm using gitfs and my custom modules/states/etc are not syncing. Why?
----------------------------------------------------------------------

In versions of Salt 0.16.3 or older, there is a bug in :doc:`gitfs
</topics/tutorials/gitfs>` which can affect the syncing of custom types.
Upgrading to 0.16.4 or newer will fix this.

Why aren't my custom modules/states/etc. available on my Minions?
-----------------------------------------------------------------

Custom modules are only synced to Minions when :mod:`state.highstate
<salt.modules.state.highstate>`, :mod:`saltutil.sync_modules
<salt.modules.saltutil.sync_modules>`, or :mod:`saltutil.sync_all
<salt.modules.saltutil.sync_all>` is run. Similarly, custom states are only
synced to Minions when :mod:`state.highstate <salt.modules.state.highstate>`,
:mod:`saltutil.sync_states <salt.modules.saltutil.sync_states>`, or
:mod:`saltutil.sync_all <salt.modules.saltutil.sync_all>` is run.

Other custom types (renderers, outputters, etc.) have similar behavior, see the
documentation for the :mod:`saltutil <salt.modules.saltutil>` module for more
information.

Module ``X`` isn't available, even though the shell command it uses is installed. Why?
--------------------------------------------------------------------------------------
This is most likely a PATH issue. Did you custom-compile the software which the
module requires? RHEL/CentOS/etc. in particular override the root user's path
in ``/etc/init.d/functions``, setting it to ``/sbin:/usr/sbin:/bin:/usr/bin``,
making software installed into ``/usr/local/bin`` unavailable to Salt when the
Minion is started using the initscript. In version 0.18.0, Salt will have a
better solution for these sort of PATH-related issues, but recompiling the
software to install it into a location within the PATH should resolve the
issue in the meantime. Alternatively, you can create a symbolic link within the
PATH using a :mod:`file.symlink <salt.states.file.symlink>` state.

.. code-block:: yaml

    /usr/bin/foo:
      file.symlink:
        - target: /usr/local/bin/foo
