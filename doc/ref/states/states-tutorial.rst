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
the state of a system can be easily defined and then enforced. These system
states are defined in a generic data strucutre, here is a simple example:

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
file and the sls files which define enforcable states can be prepared.

Preparing the Top File
``````````````````````

What servrs are to recieve what states is defined in the ``Top File``. The
``Top File`` is placed in the root of the file server and is named ``top.sls``
(the name of the top file can be changed in the salt master configuration file
with the state_top option). Certian modules are linked to Salt matches in the
``Top File``. A simple top file will look like this:

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

State Tree Layout
`````````````````

The layout of a state tree is fairly simple. When working with the state system
remember that everything is read as a file, there are no "magic directories" and
only a very few special conventions.

Defining SLS Modules
~~~~~~~~~~~~~~~~~~~~

The primary file for a state tree will be the top file, this file must be placed
in the root of the State Tree and be named ``top.sls``. After this the sls
modules need to be defined. The sls modules are appended with the file extension
``.sls`` and are referenced by name. Therefore a file in the root of state tree
directory called ``apache.sls`` will provide the apache sls module.

Directories and SLS Modules
~~~~~~~~~~~~~~~~~~~~~~~~~~~

A directory structure can also be used to define sls modules. This is hos a
module named ``apache.server`` could be dinfined. therefore if a module is
crated in the apache subdirectory under the state tree root in a file named
``server.sls``, then said module is referenced as ``apache.server``.

A module can also be defined as a directory name. If the directory apache
exists, and a module named apache is desired, than a file called ``init.sls``
in the apache directory can be used to define the ``apache`` module. Therefore
the modules defined in the top file example above could be laid out like this:

top.sls
apache/init.sls
python/init.sls
python.django.sls
haproxy/init.sls
core.sls
archfix.sls

Setting Up SLS Modules
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

Templating SLS Modules
~~~~~~~~~~~~~~~~~~~~~~

SLS Modules may require programming logic or inline excutions. This is
acomplished with module templating. The default module templating system used
is Jinja2 (add web addr for jinja). All states are passed through a templating
system when they are initially read, so all that is required to make use of
the templating system is to add some templating code. An example of an sls
module with templating may look like this:

.. code-block:: yaml

    {% for usr in 'moe','larry','currly' %}
    {{ usr }}:
      user:
        - present
    {% endfor %}

This templated sls file, wonce generated will look like this:

.. code-block:: yaml

    moe:
      user:
        - present
    larry:
      user:
        - present
    currly:
      user:
        - present

Getting Grains in SLS Modules
`````````````````````````````

Often times a state will need to behave differently on different systems. so
the salt grains sysetm (link to grains system) can be used from within sls
modules. This is done via the templating system, an object called ``grains``
is made available in the templating system.

This means that the grains dictonairy can be used within the templating system.
Using a grain from within the templating system looks like this:

.. code-block:: yaml

    apache:
      pkg:
        {% if grains['os'] == 'RedHat' %}
        - name: httpd
        {% endif %}
        - installed

Here the ``os`` grain is checked as part of an if statement in some Jinja code.

Calling Salt Execution Modules in Templates
```````````````````````````````````````````

All of the Salt modules loaded by the minion ave available within the
templating system. This allows data to be gathered in real time, on the target
system. It also allows for shell commands to be run easily from within the sls
modules.

The Salt module functions are also made available via a dictonairy called
``salt`` and can be called in this manner:

.. code-block:: yaml

    {% for usr in 'moe','larry','currly' %}
    {{ usr }}:
      group:
        - present
      user:
        - present
        - gid: {{ salt['file.group_to_gid'](usr) }}
        - require:
          - group: {{ usr }}
    {% endfor %}

This line is used to call the salt function file.group_to_gid and passes it the
variable usr.

Similarly to call an arbitrairy command the term
``salt['cmd.run']('ifconfig eth0 | grep HWaddr | cut -d" " -f10')`` could be
used to grab the mac addr for eth0.

How SLS Data Is Rendered
------------------------

All Salt cares about when running a state is the data structure that is crated
by the sls module. How that data structure is generated is arbitrairy to the
data contained in the data structure. This means the way the data structure is
expressed is also arbitrairy. to render data structures the yaml expressed here
is not required, JSON or other serialization mediums can also be used, and
Jinja does not need to be the templating engine used. To make the State Tree
render with a renderer other than the default ``yaml_jinja`` renderer change
the ``renderer`` option in the master configuration file to one of the
available alternatives, such as ``yaml_mako`` or ``json_jinja``. For a complete
list of available renderers please see (link to renderer dir on github).
