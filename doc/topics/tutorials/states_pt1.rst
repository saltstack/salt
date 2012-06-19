=======================
States tutorial, part 1
=======================

The purpose of this tutorial is to demonstrate how quickly you can configure a
system to be managed by Salt States. For detailed information about the state
system please refer to the full :doc:`states reference </ref/states/index>`.

This tutorial will walk you through using Salt to configure a minion to run the
Apache HTTP server and to ensure the server is running.

.. include:: requisite_incl.rst

Setting up the Salt State Tree
==============================

States are stored in text files on the master and transfered to the minions on
demand via the master's File Server. The collection of state files make up the
:term:`State Tree`.

To start using a central state system in Salt you must first set up the Salt
File Server. Edit your master config file (:conf_master:`file_roots`) and
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

    % pkill salt-master
    % salt-master -d

Preparing the Top File
======================

On the master in the directory you uncommented in the previous step
(``/srv/salt`` by default), create a new file called
:conf_master:`top.sls <state_top>` and add the following:

.. code-block:: yaml

    base:
      '*':
        - webserver

The :term:`top file` is separated into environments (discussed later). The
default environment is ``base``. Under the ``base`` environment a collection of
minion matches is defined; for now simply specify all hosts (``*``).

.. admonition:: Targeting minions

    The expressions can use any of the targeting mechanisms used by Salt —
    minions can be matched by glob, pcre regular expression, or by :doc:`grains
    </topics/targeting/grains>`. For example::

        base:
          'os:Fedora':
            - match: grain
            - webserver

Create an ``sls`` module
========================

In the same directory as your :term:`top file`, create an empty file, called an
:term:`SLS module`, named ``webserver.sls``. Type the following and save the
file:

.. code-block:: yaml
    :linenos:

    apache:                 # ID declaration
      pkg:                  # state declaration
        - installed         # function declaration

The first line, called the :term:`ID declaration`, is an arbitrary identifier.
In this case it defines the name of the package to be installed. **NOTE:** the
package name for the Apache httpd web server may differ on your OS or distro —
for example, on Fedora it is ``httpd`` but on Debian/Ubuntu it is ``apache2``.

The second line, called the :term:`state declaration`, defines which of the
Salt States we are using. In this example, we are using the :mod:`pkg state
<salt.states.pkg>` to ensure that a given package is installed.

The third line, called the :term:`function declaration`, defines which function
in the :mod:`pkg state <salt.states.pkg>` module to call.

.. admonition:: Renderers

    States :term:`sls` files can be written in many formats. Salt requires only
    a simple data structure and is not concerned with how that data structure
    is built. Templating languages and `DSLs`_ are a dime-a-dozen and everyone
    has a favorite.

    Building the expected data structure is the job of Salt :doc:`renderers
    </ref/renderers/index>` and they are dead-simple to write.

    In this tutorial we will be using YAML in Jinja2 templates, which is the
    default format. You can change the default by changing
    :conf_master:`renderer` in the master configuration file.

.. _`DSLs`: http://en.wikipedia.org/wiki/Domain-specific_language

Install the package
===================

Next, let's run the state we created. Open a terminal on the master and run:

.. code-block:: bash

    % salt '*' state.highstate

Our master is instructing all targeted minions to run :func:`state.highstate
<salt.modules.state.highstate>`. When a minion executes a highstate call it
will download the :term:`top file` and attempt to match the expressions. When
it does match an expression the modules listed for it will be downloaded,
compiled, and executed.

Once completed, the minion will report back with a summary of all actions taken
and all changes made.

.. admonition:: Troubleshooting Salt

    In case you don't see the expected output, the following tips can help you
    narrow down the problem.

    Turn up logging
        Salt can be quite chatty when you change the logging setting to
        ``debug``::

            salt-minion -l debug

    Run the minion in the foreground
        By not starting the minion in daemon mode (:option:`-d <salt-minion
        -d>`) you can view any output from the minion as it works::

            salt-minion &

    Increase the default timeout value when running :command:`salt`. For
    example, to change the default timeout to 60 seconds::

        salt -t 60

    For best results, combine all three::

        salt-minion -l debug &          # On the minion
        salt '*' state.highstate -t 60  # On the master

Next steps
==========

This tutorial focused on getting a simple Salt States configuration working.
:doc:`Part 2 <states_pt2>` will build on this example to cover more advanced
:term:`sls` syntax and will explore more of the states that ship with Salt.
