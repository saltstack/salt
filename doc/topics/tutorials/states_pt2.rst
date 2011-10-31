=======================
States tutorial, part 2
=======================

This tutorial builds on the topic covered in :doc:`part 1 <states_pt1>`. It is
recommended that you begin there.

In the last Salt States tutorial we ran everything locally and did not take
advantage of Salt's tremendous ability to run on multiple hosts. In this
tutorial, we will modify ``webserver.sls`` to run from the :term:`Salt master
<master>` and transfer configuration and files to the :term:`Salt minions
<minion>`.

Setting up the Salt State Tree
==============================

Groups of states are defined on the Salt master inside of the master's file
server and are expressed in a :term:`State Tree`. To start using a central
state system in Salt you must first set up the Salt File Server. Edit your
master config file (``/etc/salt/master``) and uncomment the following lines:

.. code-block:: yaml

    file_roots:
      base:
        - /srv/salt

Restart the Salt master in order to pick up this change:

.. code-block:: bash

    % pkill salt-master
    % salt-master -d

Preparing the Top File
======================

On the master in the directory you specified in the previous step, create a new
file called :conf_master:`top.sls <state_top>` and add the following:

.. code-block:: yaml

    base:
      '*':
        - webserver

The :term:`top file` is separated into environments (discussed later). The
default environment is ``base``. Under the ``base`` environment a collection of
minion matches is defined; for now simply specify all hosts (``*``).

.. admonition:: Matching minions

    The expressions can use any or the matching mechanisms used by Salt, so
    minions can be matched by glob, pcre regular expression, or by grains. When
    a minion executes a state call it will download the :term:`top file` and
    attempt to match the expressions, when it does match an expression the
    modules listed for it will be downloaded, compiled, and executed.

Define an SLS module
====================

Move your ``webserver.sls`` file into the same directory as ``top.sls``. This
defines the "webserver sls module".

SLS modules are appended with the file extension ``.sls`` and are referenced by
name starting at the root of the state tree.

.. admonition:: Directories and SLS modules

    An SLS module can be also defined as a directory. If the directory
    ``python`` exists, and a module named ``python`` is desired, than a file
    called ``init.sls`` in the ``python`` directory can be used to define the
    ``python`` module. For example::

        |- top.sls
        |- python
        |  |- init.sls
        |  `- django.sls
        |- haproxy
        |  `- init.sls
        `- core.sls

    In the example above the ``django.sls`` module would be referenced as
    ``python.django``.

Add a dependency
================

We now have a working installation of Apache so let's add an HTML file to
customize our website. Include the following at the bottom of your
``webserver.sls`` file:

.. code-block:: yaml
    :linenos:

    /var/www/index.html:                # ID declaration
      file:                             # state declaration
        - managed                       # function
        - source: salt://index.html     # function arg
        - require:                      # requisite declaration
          - pkg: apache2                # requisite reference

Again in **line 1** is the :term:`ID declaration`. In this example it is the
location we want to install our custom HTML file. (The default location that
Apache serves may differ from the above on your OS or distro. ``/srv/www``
could also be a likely place to look.)

**Line 2** the :term:`state declaration`. This example uses the Salt :mod:`file
state <salt.states.file>`.

**Line 3** is the :term:`function declaration`. The :func:`managed function
<salt.states.file.managed>` will download a file from the master and install it
in the location specified.

**Line 4** is a :term:`function arg declaration` which, in this example, passes
the ``source`` argument to the :func:`managed function
<salt.states.file.managed>`. 

**Line 5** is a :term:`requisite declaration`.

**Line 6** is a :term:`requisite reference` which refers to a state and an ID.
In this example, it is referring to the ``ID declaration`` from our example in
:doc:`part 1 <states_pt1>`. This declaration tells Salt not to install the HTML
file until Apache is installed.

Call the highstate
==================

Create the ``index.html`` file and save it in the same directory as ``top.sls``
and ``webserver.sls``:

.. code-block:: html

    <html>
        <head><title>Salt rocks</title></head>
        <body>
            <h1>This file brought to you by Salt</h1>
        </body>
    </html>

Last, call :func:`state.highstate <salt.modules.state.highstate>` which
instructs the minion to fetch and execute the highstate from the Salt master::

    salt '*' salt.highstate

Verify that Apache is now serving your custom HTML.

In :doc:`part 3 <states_pt3>` we will discuss how to use templating in the
``sls`` files.
