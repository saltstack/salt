.. _faq:

Frequently Asked Questions
==========================

.. contents:: FAQ

Is Salt open-core?
------------------

No. Salt is 100% committed to being open-source, including all of our APIs. It
is developed under the `Apache 2.0 license`_, allowing it to be used in both
open and proprietary projects.

.. _`Apache 2.0 license`: http://www.apache.org/licenses/LICENSE-2.0.html

I think I found a bug! What should I do?
-----------------------------------------

The salt-users mailing list as well as the salt IRC channel can both be helpful
resources to confirm if others are seeing the issue and to assist with
immediate debugging.

To report a bug to the Salt project, please follow the instructions in
:doc:`reporting a bug </topics/development/reporting_bugs>`.


What ports should I open on my firewall?
----------------------------------------

Minions need to be able to connect to the Master on TCP ports 4505 and 4506.
Minions do not need any inbound ports open. More detailed information on
firewall settings can be found :doc:`here </topics/tutorials/firewall>`.

I'm seeing weird behavior (including but not limited to packages not installing their users properly)
-----------------------------------------------------------------------------------------------------

This is often caused by SELinux.  Try disabling SELinux or putting it in
permissive mode and see if the weird behavior goes away.

My script runs every time I run a *state.apply*. Why?
-----------------------------------------------------

You are probably using :mod:`cmd.run <salt.states.cmd.run>` rather than
:mod:`cmd.wait <salt.states.cmd.wait>`. A :mod:`cmd.wait
<salt.states.cmd.wait>` state will only run when there has been a change in a
state that it is watching.

A :mod:`cmd.run <salt.states.cmd.run>` state will run the corresponding command
*every time* (unless it is prevented from running by the ``unless`` or ``onlyif``
arguments).

More details can be found in the documentation for the :mod:`cmd
<salt.states.cmd>` states.

When I run *test.ping*, why don't the Minions that aren't responding return anything? Returning ``False`` would be helpful.
---------------------------------------------------------------------------------------------------------------------------

When you run *test.ping* the Master tells Minions to run commands/functions,
and listens for the return data, printing it to the screen when it is received.
If it doesn't receive anything back, it doesn't have anything to display for
that Minion.

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

Also, if the Master is under heavy load, it is possible that the CLI will exit
without displaying return data for all targeted Minions. However, this doesn't
mean that the Minions did not return; this only means that the Salt CLI timed
out waiting for a response. Minions will still send their return data back to
the Master once the job completes. If any expected Minions are missing from the
CLI output, the :mod:`jobs.list_jobs <salt.runners.jobs.list_jobs>` runner can
be used to show the job IDs of the jobs that have been run, and the
:mod:`jobs.lookup_jid <salt.runners.jobs.lookup_jid>` runner can be used to get
the return data for that job.

.. code-block:: bash

    salt-run jobs.list_jobs
    salt-run jobs.lookup_jid 20130916125524463507

If you find that you are often missing Minion return data on the CLI, only to
find it with the jobs runners, then this may be a sign that the
:conf_master:`worker_threads` value may need to be increased in the master
config file. Additionally, running your Salt CLI commands with the ``-t``
option will make Salt wait longer for the return data before the CLI command
exits. For instance, the below command will wait up to 60 seconds for the
Minions to return:

.. code-block:: bash

    salt -t 60 '*' test.ping


How does Salt determine the Minion's id?
----------------------------------------

If the Minion id is not configured explicitly (using the :conf_minion:`id`
parameter), Salt will determine the id based on the hostname. Exactly how this
is determined varies a little between operating systems and is described in
detail :ref:`here <minion-id-generation>`.

I'm trying to manage packages/services but I get an error saying that the state is not available. Why?
------------------------------------------------------------------------------------------------------

Salt detects the Minion's operating system and assigns the correct package or
service management module based on what is detected. However, for certain custom
spins and OS derivatives this detection fails. In cases like this, an issue
should be opened on our tracker_, with the following information:

1. The output of the following command:

   .. code-block:: bash

    salt <minion_id> grains.items | grep os

2. The contents of ``/etc/lsb-release``, if present on the Minion.

.. _tracker: https://github.com/saltstack/salt/issues

Why aren't my custom modules/states/etc. available on my Minions?
-----------------------------------------------------------------

Custom modules are only synced to Minions when :mod:`state.apply
<salt.modules.state.apply_>`, :mod:`saltutil.sync_modules
<salt.modules.saltutil.sync_modules>`, or :mod:`saltutil.sync_all
<salt.modules.saltutil.sync_all>` is run. Similarly, custom states are only
synced to Minions when :mod:`state.apply <salt.modules.state.apply_>`,
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
Minion is started using the initscript. In version 2014.1.0, Salt will have a
better solution for these sort of PATH-related issues, but recompiling the
software to install it into a location within the PATH should resolve the
issue in the meantime. Alternatively, you can create a symbolic link within the
PATH using a :mod:`file.symlink <salt.states.file.symlink>` state.

.. code-block:: yaml

    /usr/bin/foo:
      file.symlink:
        - target: /usr/local/bin/foo

Can I run different versions of Salt on my Master and Minion?
-------------------------------------------------------------

This depends on the versions.  In general, it is recommended that Master and
Minion versions match.

When upgrading Salt, the master(s) should always be upgraded first.  Backwards
compatibility for minions running newer versions of salt than their masters is
not guaranteed.

Whenever possible, backwards compatibility between new masters
and old minions will be preserved.  Generally, the only exception to this
policy is in case of a security vulnerability.

Recent examples of backwards compatibility breakage include the 0.17.1 release
(where all backwards compatibility was broken due to a security fix), and the
2014.1.0 release (which retained compatibility between 2014.1.0 masters and
0.17 minions, but broke compatibility for 2014.1.0 minions and older masters).

Does Salt support backing up managed files?
-------------------------------------------

Yes. Salt provides an easy to use addition to your file.managed states that
allow you to back up files via :doc:`backup_mode </ref/states/backup_mode>`,
backup_mode can be configured on a per state basis, or in the minion config
(note that if set in the minion config this would simply be the default
method to use, you still need to specify that the file should be backed up!).

Is it possible to deploy a file to a specific minion, without other minions having access to it?
------------------------------------------------------------------------------------------------

The Salt fileserver does not yet support access control, but it is still
possible to do this. As of Salt 2015.5.0, the
:mod:`file_tree <salt.pillar.file_tree>` external pillar is available, and
allows the contents of a file to be loaded as Pillar data. This external pillar
is capable of assigning Pillar values both to individual minions, and to
:ref:`nodegroups <targeting-nodegroups>`. See the :mod:`documentation
<salt.pillar.file_tree>` for details on how to set this up.

Once the external pillar has been set up, the data can be pushed to a minion
via a :py:func:`file.managed <salt.states.file.managed>` state, using the
``contents_pillar`` argument:

.. code-block:: yaml

    /etc/my_super_secret_file:
      file.managed:
        - user: secret
        - group: secret
        - mode: 600
        - contents_pillar: secret_files:my_super_secret_file

In this example, the source file would be located in a directory called
``secret_files`` underneath the file_tree path for the minion. The syntax for
specifying the pillar variable is the same one used for :py:func:`pillar.get
<salt.modules.pillar.get>`, with a colon representing a nested dictionary.

.. warning::
    Deploying binary contents using the :py:func:`file.managed
    <salt.states.file.managed>` state is only supported in Salt 2015.8.4 and
    newer.

What is the best way to restart a Salt daemon using Salt?
---------------------------------------------------------

Updating the salt-minion package requires a restart of the salt-minion service.
But restarting the service while in the middle of a state run interrupts the
process of the minion running states and sending results back to the master.
It's a tricky problem to solve, and we're working on it, but in the meantime
one way of handling this (on Linux and UNIX-based operating systems) is to use
**at** (a job scheduler which predates cron) to schedule a restart of the
service. **at** is not installed by default on most distros, and requires a
service to be running (usually called **atd**) in order to schedule jobs.
Here's an example of how to upgrade the salt-minion package at the end of a
Salt run, and schedule a service restart for one minute after the package
update completes.

Linux/Unix
**********

.. code-block:: yaml

    salt-minion:
      pkg.installed:
        - name: salt-minion
        - version: 2014.1.7-3.el6
        - order: last
      service.running:
        - name: salt-minion
        - require:
          - pkg: salt-minion
      cmd.wait:
        - name: echo service salt-minion restart | at now + 1 minute
        - watch:
          - pkg: salt-minion

To ensure that **at** is installed and **atd** is running, the following states
can be used (be sure to double-check the package name and service name for the
distro the minion is running, in case they differ from the example below.

.. code-block:: yaml

    at:
      pkg.installed:
        - name: at
      service.running:
        - name: atd
        - enable: True

An alternative to using the :program:`atd` daemon is to fork and disown the
process.

.. code-block:: yaml

    restart_minion:
      cmd.run:
        - name: |
            exec 0>&- # close stdin
            exec 1>&- # close stdout
            exec 2>&- # close stderr
            nohup /bin/sh -c 'sleep 10 && salt-call --local service.restart salt-minion' &
        - python_shell: True
        - order: last

Windows
*******

For Windows machines, restarting the minion can be accomplished using the
following state:

.. code-block:: yaml

    schedule-start:
      cmd.run:
        - name: 'start powershell "Restart-Service -Name salt-minion"'
        - order: last

or running immediately from the command line:

.. code-block:: bash

    salt -G kernel:Windows cmd.run 'start powershell "Restart-Service -Name salt-minion"'

Salting the Salt Master
-----------------------

In order to configure a master server via states, the Salt master can also be
"salted" in order to enforce state on the Salt master as well as the Salt
minions. Salting the Salt master requires a Salt minion to be installed on
the same machine as the Salt master. Once the Salt minion is installed, the
minion configuration file must be pointed to the local Salt master:

.. code-block:: yaml

    master: 127.0.0.1

Once the Salt master has been "salted" with a Salt minion, it can be targeted
just like any other minion. If the minion on the salted master is running, the
minion can be targeted via any usual ``salt`` command. Additionally, the
``salt-call`` command can execute operations to enforce state on the salted
master without requiring the minion to be running.

More information about salting the Salt master can be found in the salt-formula
for salt itself:

https://github.com/saltstack-formulas/salt-formula

.. _faq-grain-security:

Is Targeting using Grain Data Secure?
-------------------------------------

Because grains can be set by users that have access to the minion configuration
files on the local system, grains are considered less secure than other
identifiers in Salt. Use caution when targeting sensitive operations or setting
pillar values based on grain data.

When possible, you should target sensitive operations and data using the Minion
ID. If the Minion ID of a system changes, the Salt Minion's public key must be
re-accepted by an administrator on the Salt Master, making it less vulnerable
to impersonation attacks.
