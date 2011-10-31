=======================
States tutorial, part 1
=======================

The purpose of this tutorial is to demonstrate how quickly you can configure a
system to be managed by Salt States. For detailed information about the state
system please refer to the full :doc:`states reference </ref/states/index>`.

This tutorial will walk you through using Salt to configure a single system to
run the Apache HTTP server and to ensure the server is running.

.. include:: requisite_incl.rst

Create an ``sls`` file
======================

Start by creating an empty :term:`sls file` named ``webserver.sls``. Type the
following and save the file:

.. code-block:: yaml
    :linenos:

    apache2:                # ID declaration
      pkg:                  # state declaration
        - installed         # function

The first line, called the :term:`ID declaration`, is an arbitrary identifier.
In this case it defines the name of the package to be installed. (The exact
package name for the Apache httpd web server may differ on your OS or distro.)

The second line, called the :term:`state declaration`, defines which of the
Salt States we are using. In this example, we are using the :mod:`pkg state
<salt.states.pkg>` to ensure that a given package is installed.

The third line, called the :term:`function` defines which function in the
:mod:`pkg state <salt.states.pkg>` module to call.

.. admonition:: Renderers

    States :term:`sls` files can be written in many formats. Salt requires only
    a simple data structure and is not concerned with how that data structure
    is built. Building the expected structure is the job of Salt
    :doc:`renderers </ref/renderers/index>`.

    In this tutorial we will be using yaml in Jinja2 templates which is the
    default format. You can change the default by changing
    :conf_master:`renderer` in the master configuration file.

Install the package
===================

Next, let's run that state. Open a terminal and run:

.. code-block:: bash

    % salt '*' state.template /path/to/your/helloworld.sls

:func:`state.template <salt.modules.state.template>` is the simplest way to use
Salt states. It takes the path to a template as an argument and executes it on
the minion.

You should see a bunch of output as Salt installs Apache.

Ensure a service is running
===========================

Let's make a quick modification to also start Apache if it is not running:

.. code-block:: yaml
    :linenos:
    :emphasize-lines: 4,5

    apache2:
        pkg:
            - installed
        service:
            - running

Run ``state.template`` once again and observe the output.

Next steps
==========

This tutorial focused on using Salt States only on the local system. :doc:`Part
2 <states_pt2>` of the will build on this example to cover using Salt States on
a remote host.
