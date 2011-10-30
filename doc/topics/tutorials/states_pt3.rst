=======================
States tutorial, part 3
=======================

* Split state file into multiple files and match on differing grains info
* Switch host3 into a development (?) server with a slightly different configuration (how?)
* Using Jinja2 templating.

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

