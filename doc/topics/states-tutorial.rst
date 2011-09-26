Salt States Tutorial
====================

Salt has been created to control all aspects of systems. Before version 0.8.8
this was only accomplished through controling the flow of systems via Salt
modules, but 0.8.8 introduced the first glimpses of the Salt State system, the
technology used by Salt to also control the state of a system.

The Salt State system is an easy to use, simplisticly engineered, yet extreamly
powerful system for provisioning and enforcing the state of a system. Salt
states strive to fulfill the goals of the rest of the Salt architecture, they
are easy to use and easy to understand.

The States system is en extension of the existing modules that are called on
minions with the salt command. But instead of calling one-off executions
the state of a system can be easily defined. These system states are defined
in a generic data strucutre, here is a simple example:

.. code-block:: yaml

    httpd:
      pkg:
        - installed
      service:
        - running
        - require:
          - pkg: httpd
      
This simple chunk of YAML is used to ensure that the httpd package is installed
and the httpd service is running.

Setting up the Salt State Tree
------------------------------

Groups of states are defined on the salt master inside of the master's file
server and are expressed in a ``State Tree``. To start using a central state
system in Salt set up the Salt File Server in the master config file:

.. code-block:: yaml
    
    file_roots: 
      base:
        - /srv/salt

This setup is the default used by Salt, if a different root directory is
desired then change the path. After changing the settings for the file server
the salt master needs to be restarted.

Once the salt master is running with the new file server root then the top
file and the sls files which define the state can be prepared.

Preparing the Top File
``````````````````````

What servrs are to recieve what states is defined in the ``Top File``. The
``Top File`` is placed in the root of the file server and is named ``top.sls``
(the name of the top file can be changed in the salt master with the state_top
option). Certian modules are linked to Salt matches in the ``Top File``. A
simple top file will look like this:

.. code-block:: yaml

    base:
      'webserv*':
        - apache
        - python.django
        - core
      'haproxy.*':
        - match: pcre
        - haproxy
        - core
      'os:Arch':
        - match: grain
        - archfix

The top file is seperated into environments (more on environments later). The
default environment is ``base``. Under the ``base`` environment a collection
of minion matches are defined. The expressions can use any or the matching
mechanisms used by Salt, so minions can be matched by glob, pcre regular
expression, or by grains. When a minion executes a state call it will download
the top file and attempt to match the expressions, when it does match an
expression the modules listed for it will be downloaded, compiled, and
executed.

Setting Up sls Modules
``````````````````````

The list associated with each match is a list of ``SaLt State``, or ``sls``
modules. These modules contain the real work with how states are defined.
A closer look at the sls module defined at the begining of this tutorial
will express the core components:

.. code-block:: yaml

    httpd:
      pkg:
        - installed
      service:
        - running
        - require:
          - pkg: httpd

The first line containing the text ``httpd:`` is the name line, it defines the
name to be used for all of the types specified below. The next line defines the
first of 2 states which will be applied to the name. The ``pkg`` state is used
to manage packages to be installed or removed. The ``- installed`` line tells
salt which function to call in the pkg state. In this case ``installed`` will
verify that the package named httpd is installed. The ``service`` line defines
that a system service will be managed. The state function defined is ``running``
which will ensure that the initscript named ``httpd`` is running. The
``require`` option can be used for all state declarations and is used to ensure
that the named types will be executed before the specified type is run, and
if the named type(s) return ``False``, then the specified type will not be
called. In this case, salt will not attempt to start the httpd service unless
the package has been verifed to be installed.
