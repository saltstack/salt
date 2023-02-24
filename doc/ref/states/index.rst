.. _state-system-reference:

======================
State System Reference
======================

Salt offers an interface to manage the configuration or "state" of the
Salt minions. This interface is a fully capable mechanism used to enforce the
state of systems from a central manager.


.. toctree::
    :glob:

    *

State Management
================

State management, also frequently called Software Configuration Management
(SCM), is a program that puts and keeps a system into a predetermined state. It
installs software packages, starts or restarts services or puts configuration
files in place and watches them for changes.

Having a state management system in place allows one to easily and reliably
configure and manage a few servers or a few thousand servers. It allows
configurations to be kept under version control.

Salt States is an extension of the Salt Modules that we discussed in the
previous :ref:`remote execution <tutorial-remote-execution-modules>` tutorial. Instead
of calling one-off executions the state of a system can be easily defined and
then enforced.

Understanding the Salt State System Components
==============================================

The Salt state system is comprised of a number of components. As a user, an
understanding of the SLS and renderer systems are needed. But as a developer,
an understanding of Salt states and how to write the states is needed as well.

.. note::

    States are compiled and executed only on minions that have been targeted.
    To execute functions directly on masters, see :ref:`runners <runners>`.

Salt SLS System
---------------

The primary system used by the Salt state system is the SLS system. SLS stands
for **S**\ a\ **L**\ t **S**\ tate.

The Salt States are files which contain the information about how to configure
Salt minions. The states are laid out in a directory tree and can be written in
many different formats.

The contents of the files and the way they are laid out is intended to be as
simple as possible while allowing for maximum flexibility. The files are laid
out in states and contains information about how the minion needs to be
configured.

SLS File Layout
```````````````

SLS files are laid out in the Salt file server.

A simple layout can look like this:

.. code-block:: yaml

    top.sls
    ssh.sls
    sshd_config
    users/init.sls
    users/admin.sls
    salt/master.sls
    web/init.sls

The ``top.sls`` file is a key component. The ``top.sls`` files
is used to determine which SLS files should be applied to which minions.

The rest of the files with the ``.sls`` extension in the above example are
state files.

Files without a ``.sls`` extensions are seen by the Salt master as
files that can be downloaded to a Salt minion.

States are translated into dot notation. For example, the ``ssh.sls`` file is
seen as the ssh state and the ``users/admin.sls`` file is seen as the
users.admin state.

Files named ``init.sls`` are translated to be the state name of the parent
directory, so the ``web/init.sls`` file translates to the ``web`` state.

In Salt, everything is a file; there is no "magic translation" of files and file
types. This means that a state file can be distributed to minions just like a
plain text or binary file.

SLS Files
`````````

The Salt state files are simple sets of data. Since SLS files are just data
they can be represented in a number of different ways.

The default format is YAML generated from a Jinja template. This allows for the
states files to have all the language constructs of Python and the simplicity of YAML.

State files can then be complicated Jinja templates that translate down to YAML, or just
plain and simple YAML files.

The State files are simply common data structures such as dictionaries and lists, constructed
using a templating language such as YAML.

Here is an example of a Salt State:

.. code-block:: yaml

    vim:
      pkg.installed: []

    salt:
      pkg.latest:
        - name: salt
      service.running:
        - names:
          - salt-master
          - salt-minion
        - require:
          - pkg: salt
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

The top file controls the mapping between minions and the states which should
be applied to them.

The top file specifies which minions should have which SLS files applied and
which environments they should draw those SLS files from.

The top file works by specifying environments on the top-level.

Each environment contains :ref:`target expressions <targeting>` to match
minions. Finally, each target expression contains a list of Salt states to
apply to matching minions:

.. code-block:: yaml

    base:
      '*':
        - salt
        - users
        - users.admin
      'saltmaster.*':
        - match: pcre
        - salt.master

This above example uses the base environment which is built into the default
Salt setup.

The base environment has target expressions. The first one matches all minions,
and the SLS files below it apply to all minions.

The second expression is a regular expression that will match all minions
with an ID matching ``saltmaster.*`` and specifies that for those minions, the
salt.master state should be applied.

.. important::
    Since version 2014.7.0, the default matcher (when one is not explicitly
    defined as in the second expression in the above example) is the
    :ref:`compound <targeting-compound>` matcher. Since this matcher parses
    individual words in the expression, minion IDs containing spaces will not
    match properly using this matcher. Therefore, if your target expression is
    designed to match a minion ID containing spaces, it will be necessary to
    specify a different match type (such as ``glob``). For example:

    .. code-block:: yaml

        base:
          'test minion':
            - match: glob
            - foo
            - bar
            - baz

A full table of match types available in the top file can be found :ref:`here
<top-file-match-types>`.

.. _reloading-modules:

Reloading Modules
-----------------

Some Salt states require that specific packages be installed in order for the
module to load. As an example the :mod:`pip <salt.states.pip_state>` state
module requires the `pip`_ package for proper name and version parsing.

In most of the common cases, Salt is clever enough to transparently reload the
modules. For example, if you install a package, Salt reloads modules because
some other module or state might require just that package which was installed.

On some edge-cases salt might need to be told to reload the modules. Consider
the following state file which we'll call ``pep8.sls``:

.. code-block:: yaml

    python-pip:
      cmd.run:
        - name: |
            easy_install --script-dir=/usr/bin -U pip
        - cwd: /

    pep8:
      pip.installed:
        - require:
          - cmd: python-pip


The above example installs `pip`_ using ``easy_install`` from `setuptools`_ and
installs `pep8`_ using :mod:`pip <salt.states.pip_state>`, which, as told
earlier, requires `pip`_ to be installed system-wide. Let's execute this state:

.. code-block:: bash

    salt-call state.apply pep8

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


Since we installed `pip`_ using :mod:`cmd <salt.states.cmd>`, Salt has no way
to know that a system-wide package was installed.

On the second execution, since the required `pip`_ package was installed, the
state executed correctly.

.. note::
    Salt does not reload modules on every state run because doing so would greatly
    slow down state execution.

So how do we solve this *edge-case*? ``reload_modules``!

``reload_modules`` is a boolean option recognized by salt on **all** available
states which forces salt to reload its modules once a given state finishes.

The modified state file would now be:

.. code-block:: yaml

    python-pip:
      cmd.run:
        - name: |
            easy_install --script-dir=/usr/bin -U pip
        - cwd: /
        - reload_modules: true

    pep8:
      pip.installed:
        - require:
          - cmd: python-pip


Let's run it, once:

.. code-block:: bash

    salt-call state.apply pep8

The output is:

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


.. _`pip`: https://pypi.org/project/pip/
.. _`pep8`: https://pypi.org/project/pep8/
.. _`setuptools`: https://pypi.org/project/setuptools/
.. _`runners`: /ref/runners
