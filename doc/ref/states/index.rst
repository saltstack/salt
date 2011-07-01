=================
State Enforcement
=================

Salt offers an optional interface to manage the configuration or "state" of the
salt minions. This interface is a fully capable mechanism used to enforce the
state of systems from a central manager.

The Salt state system is made to be accurate, simple, and fast. And like the
rest of the Salt system, Salt states are highly modular.

Understanding the Salt State System Components
==============================================

The Salt state system is comprised of a number of components, as a user, an
understanding of the sls and renderer systems are needed. But as a developer,
an understanding of salt states, as well as understanding salt states and how
to write the states used by salt.

Salt SLS System
---------------

The primary system used by the Salt state system is the SLS system. SLS stands
for SaLt State.

The Salt States are files which contain the information about how to configure
salt minions. The states are laid out in a directory tree and can be written in
many different formats.

The contents of the files and they way they are laid out is intended to be as
simple as possible while allowing for maximum flexibility. The files are laid
out in states and contains information about how the minion needs to be 
configured.

SLS File Layout
```````````````

SLS files are laid out in the Salt file server. A simple layout can look like
this:

.. code-block:: yaml

    top.sls
    ssh.sls
    sshd_config
    users/init.sls
    users/admin.sls
    salt/init.sls
    salt/master.sls

This example shows the core concepts of file layout. The top file is a key
component and is used with salt matchers to match SLS states with minions.
The ``.sls`` files are states. The rest of the files are seen by the salt
master as just files that can be downloaded.

The states are translated into dot notation, so the ``ssh.sls`` file is
seen as the ssh state, the ``users/admin.sls`` file is seen as the
users.admin states.

The init.sls files are translated to be the state name of the parent
directory, so the ``salt/init.sls`` file translates to the salt state.

The plain files are visible to the minions, as well as the state files, in
salt, everything is a file, there is not "magic translation" of files and file
types. This means that a state file can be distributed to minions just like a
plain text or binary file.

SLS Files
`````````

The Salt state files are simple sets of data. Since the SLS files are just data
they can be represented in a number of different ways. The default format is
yaml generated from a jinja template. This allows for the states files to have
all the language constructs of Python, and the simplicity of yaml. State files
can then be complicated jinja templates the translate down to yaml, or just
plain and simple yaml files!

The State files are constructed data structures in a simple format. The format
allows for many real activates to be expressed in very little text, while
maintaining the utmost in readability and usability.

Here is an example of a Salt State:

.. code-block:: yaml

    vim:
        pkg:
            - installed

    salt:
        pkg:
            - latest
        service:
            - running
            - require:
                - file: /etc/salt/minion
                - pkg: salt
            - names:
                - salt-master
                - salt-minion
            - watch:
                - file: /etc/salt/minion
                
    /etc/salt/minion:
        file:
            - managed
            - source: salt://salt/minion
            - user: root
            - group: root
            - mode: 644
            - require:
                - pkg: salt

This short stanza will ensure that vim is installed, salt is installed and up
to date, the salt-master and salt-minion daemons are running and the Salt
minion configuration file is in place. It will also ensure everything is
deployed in the right order and that the Salt services are restarted when the
watched file updated.

The Top File
````````````

The top file is the mapping for the state system. The top file specifies which
minions should have which modules applied and which environments they should
draw the states from.

The top file works by specifying the environment, containing matchers with 
lists of Salt states sent to the matching minions:

.. code-block:: yaml

    base:
        '*':
            - salt
            - users
            - users.admin
        'saltmaster.*':
            - match: pcre
            - salt.master

This simple example uses the base environment, which is built into the default
salt setup, and then all minions will have the modules salt, users and
users.admin since '*' will match all minions. Then the regular expression
matcher will match all minions' with an id matching saltmaster.* and add the
salt.master state.
