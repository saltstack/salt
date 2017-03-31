.. _faq:

Frequently Asked Questions
==========================

.. contents:: FAQ

Is Salt open-core?
------------------

No. Salt is 100% committed to being open-source, including all of our APIs. It
is developed under the `Apache 2.0 license`_, allowing it to be used in both
open and proprietary projects.

To expand on this a little:

There is much argument over the actual definition of "open core".  From our standpoint, Salt is open source because

1. It is a standalone product that anyone is free to use.
2. It is developed in the open with contributions accepted from the community for the good of the project.
3. There are no features of Salt itself that are restricted to separate proprietary products distributed by SaltStack, Inc.
4. Because of our Apache 2.0 license, Salt can be used as the foundation for a project or even a proprietary tool.
5. Our APIs are open and documented (any lack of documentation is an oversight as opposed to an intentional decision by SaltStack the company) and available for use by anyone.

SaltStack the company does make proprietary products which use Salt and its libraries, like company is free to do, but we do so via the APIs, NOT by forking Salt and creating a different, closed-source version of it for paying customers.


.. _`Apache 2.0 license`: http://www.apache.org/licenses/LICENSE-2.0.html

I think I found a bug! What should I do?
----------------------------------------

The salt-users mailing list as well as the salt IRC channel can both be helpful
resources to confirm if others are seeing the issue and to assist with
immediate debugging.

To report a bug to the Salt project, please follow the instructions in
:ref:`reporting a bug <reporting-bugs>`.


What ports should I open on my firewall?
----------------------------------------

Minions need to be able to connect to the Master on TCP ports 4505 and 4506.
Minions do not need any inbound ports open. More detailed information on
firewall settings can be found :ref:`here <firewall>`.

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

Custom modules are synced to Minions when
:mod:`saltutil.sync_modules <salt.modules.saltutil.sync_modules>`,
or :mod:`saltutil.sync_all <salt.modules.saltutil.sync_all>` is run.
Custom modules are also synced by :mod:`state.apply` when run without
any arguments.


Similarly, custom states are synced to Minions
when :mod:`state.apply <salt.modules.state.apply_>`,
:mod:`saltutil.sync_states <salt.modules.saltutil.sync_states>`, or
:mod:`saltutil.sync_all <salt.modules.saltutil.sync_all>` is run.

Custom states are also synced by :mod:`state.apply<salt.modules.state.apply_>`
when run without any arguments.

Other custom types (renderers, outputters, etc.) have similar behavior, see the
documentation for the :mod:`saltutil <salt.modules.saltutil>` module for more
information.

:ref:`This reactor example <minion-start-reactor>` can be used to automatically
sync custom types when the minion connects to the master, to help with this
chicken-and-egg issue.


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
allow you to back up files via :ref:`backup_mode <file-state-backups>`,
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

What is the best way to restart a Salt Minion daemon using Salt after upgrade?
------------------------------------------------------------------------------

Updating the ``salt-minion`` package requires a restart of the ``salt-minion``
service. But restarting the service while in the middle of a state run
interrupts the process of the Minion running states and sending results back to
the Master. A common way to workaround that is to schedule restarting of the
Minion service using :ref:`masterless mode <masterless-quickstart>` after all
other states have been applied. This allows to keep Minion to Master connection
alive for the Minion to report the final results to the Master, while the
service is restarting in the background.

Upgrade without automatic restart
*********************************

Doing the Minion upgrade seems to be a simplest state in your SLS file at
first. But the operating systems such as Debian GNU/Linux, Ubuntu and their
derivatives start the service after the package installation by default.
To prevent this, we need to create policy layer which will prevent the Minion
service to restart right after the upgrade:

.. code-block:: jinja

    {%- if grains['os_family'] == 'Debian' %}

    Disable starting services:
      file.managed:
        - name: /usr/sbin/policy-rc.d
        - user: root
        - group: root
        - mode: 0755
        - contents:
          - '#!/bin/sh'
          - exit 101
        # do not touch if already exists
        - replace: False
        - prereq:
          - pkg: Upgrade Salt Minion

    {%- endif %}

    Upgrade Salt Minion:
      pkg.installed:
        - name: salt-minion
        - version: 2016.11.3{% if grains['os_family'] == 'Debian' %}+ds-1{% endif %}
        - order: last

    Enable Salt Minion:
      service.enabled:
        - name: salt-minion
        - require:
          - pkg: Upgrade Salt Minion

    {%- if grains['os_family'] == 'Debian' %}

    Enable starting services:
      file.absent:
        - name: /usr/sbin/policy-rc.d
        - onchanges:
          - pkg: Upgrade Salt Minion

    {%- endif %}

Restart using states
********************

Now we can apply the workaround to restart the Minion in reliable way.
The following example works on both UNIX-like and Windows operating systems:

.. code-block:: jinja

    Restart Salt Minion:
      cmd.run:
    {%- if grains['kernel'] == 'Windows' %}
        - name: 'C:\salt\salt-call.bat --local service.restart salt-minion'
    {%- else %}
        - name: 'salt-call --local service.restart salt-minion'
    {%- endif %}
        - bg: True
        - onchanges:
          - pkg: Upgrade Salt Minion

However, it requires more advanced tricks to upgrade from legacy version of
Salt (before ``2016.3.0``), where executing commands in the background is not
supported:

.. code-block:: jinja

    Restart Salt Minion:
      cmd.run:
    {%- if grains['kernel'] == 'Windows' %}
        - name: 'start powershell "Restart-Service -Name salt-minion"'
    {%- else %}
        # fork and disown the process
        - name: |-
            exec 0>&- # close stdin
            exec 1>&- # close stdout
            exec 2>&- # close stderr
            nohup salt-call --local service.restart salt-minion &
    {%- endif %}

Restart using remote executions
*******************************

Restart the Minion from the command line:

.. code-block:: bash

    salt -G kernel:Windows cmd.run_bg 'C:\salt\salt-call.bat --local service.restart salt-minion'
    salt -C 'not G@kernel:Windows' cmd.run_bg 'salt-call --local service.restart salt-minion'

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

The only grain which can be safely used is ``grains['id']`` which contains the Minion ID.

When possible, you should target sensitive operations and data using the Minion
ID. If the Minion ID of a system changes, the Salt Minion's public key must be
re-accepted by an administrator on the Salt Master, making it less vulnerable
to impersonation attacks.

Why Did the Value for a Grain Change on Its Own?
------------------------------------------------

This is usually the result of an upstream change in an OS distribution that
replaces or removes something that Salt was using to detect the grain.
Fortunately, when this occurs, you can use Salt to fix it with a command
similar to the following:

.. code-block:: bash

    salt -G 'grain:ChangedValue' grains.setvals "{'grain': 'OldValue'}"

(Replacing *grain*, *ChangedValue*, and *OldValue* with
the grain and values that you want to change / set.)

You should also `file an issue <https://github.com/saltstack/salt/issues>`_
describing the change so it can be fixed in Salt.

