=================
State Enforcement
=================

Salt offers an optional interface to manage the configuration or "state" of the
Salt minions. This interface is a fully capable mechanism used to enforce the
state of systems from a central manager.

The Salt state system is made to be accurate, simple, and fast. And like the
rest of the Salt system, Salt states are highly modular.

State management
================

State management, also frequently called software configuration management
(SCM), is a program that puts and keeps a system into a predetermined state. It
installs software packages, starts or restarts services, or puts configuration
files in place and watches them for changes.

Having a state management system in place allows you to easily and reliably
configure and manage a few servers or a few thousand servers. It allows you to
keep that configuration under version control.

Salt States is an extension of the Salt Modules that we discussed in the
previous :doc:`remote execution </topics/tutorials/modules>` tutorial. Instead
of calling one-off executions the state of a system can be easily defined and
then enforced.

Understanding the Salt State System Components
==============================================

The Salt state system is comprised of a number of components. As a user, an
understanding of the SLS and renderer systems are needed. But as a developer,
an understanding of Salt states and how to write the states is needed as well.

.. note::

    States are compiled and executed only on minions that have been targeted.
    To execute things on masters, see `runners`_.

Salt SLS System
---------------

.. glossary::

    SLS
        The primary system used by the Salt state system is the SLS system. SLS
        stands for **S**\ a\ **L**\ t **S**\ tate.

        The Salt States are files which contain the information about how to
        configure Salt minions. The states are laid out in a directory tree and
        can be written in many different formats.

        The contents of the files and they way they are laid out is intended to
        be as simple as possible while allowing for maximum flexibility. The
        files are laid out in states and contains information about how the
        minion needs to be configured.

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
component and is used with Salt matchers to match SLS states with minions.
The ``.sls`` files are states. The rest of the files are seen by the Salt
master as just files that can be downloaded.

The states are translated into dot notation, so the ``ssh.sls`` file is
seen as the ssh state, the ``users/admin.sls`` file is seen as the
users.admin states.

The init.sls files are translated to be the state name of the parent
directory, so the ``salt/init.sls`` file translates to the Salt state.

The plain files are visible to the minions, as well as the state files. In
Salt, everything is a file; there is no "magic translation" of files and file
types. This means that a state file can be distributed to minions just like a
plain text or binary file.

SLS Files
`````````

The Salt state files are simple sets of data. Since the SLS files are just data
they can be represented in a number of different ways. The default format is
yaml generated from a Jinja template. This allows for the states files to have
all the language constructs of Python and the simplicity of yaml. State files
can then be complicated Jinja templates that translate down to yaml, or just
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
      service.running:
        - require:
          - file: /etc/salt/minion
          - pkg: salt
        - names:
          - salt-master
          - salt-minion
        - watch:
          - file: /etc/salt/minion

    /etc/salt/minion:
      file.managed:
        - source: salt://salt/minion
        - user: root
        - group: root
        - mode: 644
        - require:
          - pkg: salt

This short stanza will ensure that vim is installed, Salt is installed and up
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
Salt setup, and then all minions will have the modules salt, users and
users.admin since '*' will match all minions. Then the regular expression
matcher will match all minions' with an id matching saltmaster.* and add the
salt.master state.

Renderer System
---------------

The Renderer system is a key component to the state system. SLS files are
representations of Salt "high data" structures. All Salt cares about when
reading an SLS file is the data structure that is produced from the file.

This allows Salt states to be represented by multiple types of files. The
Renderer system can be used to allow different formats to be used for SLS
files.

The available renderers can be found in the renderers directory in the Salt
source code:

:blob:`salt/renderers`

By default SLS files are rendered using Jinja as a templating engine, and yaml
as the serialization format. Since the rendering system can be extended simply
by adding a new renderer to the renderers directory, it is possible that any
structured file could be used to represent the SLS files.

In the future XML will be added, as well as many other formats.


Reloading Modules
-----------------

Some salt states require specific packages to be installed in order for the 
module to load, as an example the :mod:`pip <salt.states.pip_state>` state 
module requires the `pip`_ package for proper name and version parsing.  On 
most of the common cases, salt is clever enough to transparently reload the 
modules, for example, if you install a package, salt reloads modules because 
some other module or state might require just that package which was installed.  
On some edge-cases salt might need to be told to reload the modules. Consider 
the following state file which we'll call ``pep8.sls``:

.. code-block:: yaml

    python-pip:
      cmd:
        - run
        - cwd: /
        - name: easy_install --script-dir=/usr/bin -U pip

    pep8:
      pip.installed
      requires:
        - cmd: python-pip


The above example installs `pip`_ using ``easy_install`` from `setuptools`_ and 
installs `pep8`_ using :mod:`pip <salt.states.pip_state>`, which, as told 
earlier, requires `pip`_ to be installed system-wide. Let's execute this state:

.. code-block:: bash

    salt-call state.sls pep8

The execution output would be something like:

.. code-block:: text

    ----------
        State: - pip
        Name:      pep8
        Function:  installed
            Result:    False
            Comment:   State pip.installed found in sls pep8 is unavailable

            Changes:

    Summary
    ------------
    Succeeded: 1
    Failed:    1
    ------------
    Total:     2


If we executed the state again the output would be:

.. code-block:: text

    ----------
        State: - pip
        Name:      pep8
        Function:  installed
            Result:    True
            Comment:   Package was successfully installed
            Changes:   pep8==1.4.6: Installed

    Summary
    ------------
    Succeeded: 2
    Failed:    0
    ------------
    Total:     2


Since we installed `pip`_ using :mod:`cmd <salt.states.cmd>`, salt has no way 
to know that a system-wide package was installed. On the second execution, 
since the required `pip`_ package was installed, the state executed perfectly.

To those thinking, could not salt reload modules on every state step since it
already does for some cases?  It could, but it should not since it would 
greatly slow down state execution.

So how do we solve this *edge-case*? ``reload_modules``!

``reload_modules`` is a boolean option recognized by salt on **all** available 
states which, does exactly what it tells use, forces salt to reload it's 
modules once that specific state finishes. The fixed state file would now be:

.. code-block:: yaml

    python-pip:
      cmd:
        - run
        - cwd: /
        - name: easy_install --script-dir=/usr/bin -U pip
        - reload_modules: true

    pep8:
      pip.installed
      requires:
        - cmd: python-pip


Let's run it, once:

.. code-block:: bash

    salt-call state.sls pep8

And it's output now is:

.. code-block:: text

    ----------
        State: - pip
        Name:      pep8
        Function:  installed
            Result:    True
            Comment:   Package was successfully installed
            Changes:   pep8==1.4.6: Installed

    Summary
    ------------
    Succeeded: 2
    Failed:    0
    ------------
    Total:     2


.. _`pip`: http://pypi.python.org/pypi/pip
.. _`pep8`: https://pypi.python.org/pypi/pep8
.. _`setuptools`: https://pypi.python.org/pypi/setuptools
.. _`runners`: /ref/runners
