=======================
States tutorial, part 2
=======================

This tutorial builds on the topic covered in :doc:`part 1 <states_pt1>`. It is
recommended that you begin there.

Our goal
========

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

In the directory you specified in the previous step, create a new file called
:conf_master:`top.sls <state_top>` and add the following:

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

Move your ``webserver.sls`` file into the directory you specified above. This
defines the "webserver sls module". SLS modules are appended with the file
extension ``.sls`` and are referenced by name starting at the root of the state
tree.

.. admonition:: Directories and SLS modules

    A module can be also defined as a directory. If the directory ``python``
    exists, and a module named ``python`` is desired, than a file called
    ``init.sls`` in the ``python`` directory can be used to define the
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

We now have a working installation of Apache so let's add a virtual host to
configure our website. Include the following at the bottom of your
``webserver.sls`` file:

.. code-block:: yaml

    /etc/apache2/sites-available/helloworld.example.com:
      file:
        - managed
        - source: salt://helloworld.example.com
        - require:
          - pkg: apache2

This block uses the Salt :mod:`file state <salt.states.file>` to install the
file defined in ``source`` to the location defined in the :term:`ID
declaration`.

The ``require`` directive is refering to the :term:`ID declaration` for the
``pkg`` block that you selected part 1.

In this case, salt will not attempt to start the apache2 service unless the
package has been verifed to be installed and the vhost config is in place.

Create the virtual host file and save it as
``/srv/salt/helloworld.example.com``:

.. code-block:: apache

    <VirtualHost>
        ServerName helloworld.example.com
        DocumentRoot /var/www/helloworld.example.com
    </VirtualHost>

