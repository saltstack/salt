.. _states-tutorial:

=====================================
States tutorial, part 1 - Basic Usage
=====================================

The purpose of this tutorial is to demonstrate how quickly you can configure a
system to be managed by Salt States. For detailed information about the state
system please refer to the full :doc:`states reference </ref/states/index>`.

This tutorial will walk you through using Salt to configure a minion to run the
Apache HTTP server and to ensure the server is running.

.. include:: /_incl/requisite_incl.rst

Setting up the Salt State Tree
==============================

States are stored in text files on the master and transferred to the minions on
demand via the master's File Server. The collection of state files make up the
``State Tree``.

To start using a central state system in Salt, the Salt File Server must first
be set up. Edit the master config file (:conf_master:`file_roots`) and
uncomment the following lines:

.. code-block:: yaml

    file_roots:
      base:
        - /srv/salt

.. note::

    If you are deploying on FreeBSD via ports, the ``file_roots`` path defaults
    to ``/usr/local/etc/salt/states``.

Restart the Salt master in order to pick up this change:

.. code-block:: bash

    pkill salt-master
    salt-master -d

Preparing the Top File
======================

On the master, in the directory uncommented in the previous step,
(``/srv/salt`` by default), create a new file called
:conf_master:`top.sls <state_top>` and add the following:

.. code-block:: yaml

    base:
      '*':
        - webserver

The :ref:`top file <states-top>` is separated into environments (discussed
later). The default environment is ``base``. Under the ``base`` environment a
collection of minion matches is defined; for now simply specify all hosts
(``*``).

.. _targeting-minions:
.. admonition:: Targeting minions

    The expressions can use any of the targeting mechanisms used by Salt —
    minions can be matched by glob, PCRE regular expression, or by :doc:`grains
    </topics/targeting/grains>`. For example:

    .. code-block:: yaml

        base:
          'G@os:Fedora':
            - match: grain
            - webserver

Create an ``sls`` file
======================

In the same directory as the :ref:`top file <states-top>`, create a file
named ``webserver.sls``, containing the following:

.. code-block:: yaml

    apache:                 # ID declaration
      pkg:                  # state declaration
        - installed         # function declaration

The first line, called the :ref:`id-declaration`, is an arbitrary identifier.
In this case it defines the name of the package to be installed.

.. note::

    The package name for the Apache httpd web server may differ depending on
    OS or distro — for example, on Fedora it is ``httpd`` but on
    Debian/Ubuntu it is ``apache2``.

The second line, called the :ref:`state-declaration`, defines which of the Salt
States we are using. In this example, we are using the :mod:`pkg state
<salt.states.pkg>` to ensure that a given package is installed.

The third line, called the :ref:`function-declaration`, defines which function
in the :mod:`pkg state <salt.states.pkg>` module to call.

.. admonition:: Renderers

    States ``sls`` files can be written in many formats. Salt requires only
    a simple data structure and is not concerned with how that data structure
    is built. Templating languages and `DSLs`_ are a dime-a-dozen and everyone
    has a favorite.

    Building the expected data structure is the job of Salt :doc:`renderers
    </ref/renderers/index>` and they are dead-simple to write.

    In this tutorial we will be using YAML in Jinja2 templates, which is the
    default format. The default can be changed by editing
    :conf_master:`renderer` in the master configuration file.

.. _`DSLs`: http://en.wikipedia.org/wiki/Domain-specific_language

.. _running-highstate:

Install the package
===================

Next, let's run the state we created. Open a terminal on the master and run:

.. code-block:: bash

    salt '*' state.apply

Our master is instructing all targeted minions to run :func:`state.apply
<salt.modules.state.apply>`. When this function is executied without any SLS
targets, a minion will download the :ref:`top file <states-top>` and attempt to
match the expressions within it. When the minion does match an expression the
modules listed for it will be downloaded, compiled, and executed.

.. note::
    This action is referred to as a "highstate", and can be run using the
    :py:func:`state.highstate <salt.modules.state.highstate>` function.
    However, to make the usage easier to understand ("highstate" is not
    necessarily an intuitive name), a :py:func:`state.apply
    <salt.modules.state.apply_>` function was added in version 2015.5.0, which
    when invoked without any SLS names will trigger a highstate.
    :py:func:`state.highstate <salt.modules.state.highstate>` still exists and
    can be used, but the documentation (as can be seen above) has been updated
    to reference :py:func:`state.apply <salt.modules.state.apply_>`, so keep
    the following in mind as you read the documentation:

    - :py:func:`state.apply <salt.modules.state.apply_>` invoked without any
      SLS names will run :py:func:`state.highstate
      <salt.modules.state.highstate>`
    - :py:func:`state.apply <salt.modules.state.apply_>` invoked with SLS names
      will run :py:func:`state.sls <salt.modules.state.sls>`

Once completed, the minion will report back with a summary of all actions taken
and all changes made.

.. warning::

    If you have created :ref:`custom grain modules <writing-grains>`, they will
    not be available in the top file until after the first :ref:`highstate
    <running-highstate>`. To make custom grains available on a minion's first
    :ref:`highstate <running-highstate>`, it is recommended to use :ref:`this
    example <minion-start-reactor>` to ensure that the custom grains are synced
    when the minion starts.

.. _sls-file-namespace:
.. admonition:: SLS File Namespace

    Note that in the :ref:`example <targeting-minions>` above, the SLS file
    ``webserver.sls`` was referred to simply as ``webserver``. The namespace
    for SLS files when referenced in :conf_master:`top.sls <state_top>` or an :ref:`include-declaration`
    follows a few simple rules:

    1. The ``.sls`` is discarded (i.e. ``webserver.sls`` becomes
       ``webserver``).
    2. Subdirectories can be used for better organization.
        a. Each subdirectory can be represented with a dot (following the python
           import model) or a slash.  ``webserver/dev.sls`` can also be referred to
           as ``webserver.dev``
        b. Because slashes can be represented as dots, SLS files can not contain
           dots in the name besides the dot for the SLS suffix.  The SLS file
           webserver_1.0.sls can not be matched, and webserver_1.0 would match
           the directory/file webserver_1/0.sls

    3. A file called ``init.sls`` in a subdirectory is referred to by the path
       of the directory. So, ``webserver/init.sls`` is referred to as
       ``webserver``.
    4. If both ``webserver.sls`` and ``webserver/init.sls`` happen to exist,
       ``webserver/init.sls`` will be ignored and ``webserver.sls`` will be the
       file referred to as ``webserver``.

.. admonition:: Troubleshooting Salt

    If the expected output isn't seen, the following tips can help to
    narrow down the problem.

    Turn up logging
        Salt can be quite chatty when you change the logging setting to
        ``debug``:

        .. code-block:: bash

            salt-minion -l debug

    Run the minion in the foreground
        By not starting the minion in daemon mode (:option:`-d <salt-minion -d>`)
        one can view any output from the minion as it works:

        .. code-block:: bash

            salt-minion

    Increase the default timeout value when running :command:`salt`. For
    example, to change the default timeout to 60 seconds:

    .. code-block:: bash

        salt -t 60

    For best results, combine all three:

    .. code-block:: bash

        salt-minion -l debug        # On the minion
        salt '*' state.apply -t 60  # On the master

Next steps
==========

This tutorial focused on getting a simple Salt States configuration working.
:doc:`Part 2 <states_pt2>` will build on this example to cover more advanced
``sls`` syntax and will explore more of the states that ship with Salt.
