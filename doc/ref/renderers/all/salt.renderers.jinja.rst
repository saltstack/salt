====================
salt.renderers.jinja
====================

Jinja in States
===============

.. _Jinja: http://jinja.pocoo.org/docs/templates/

The most basic usage of Jinja in state files is using control structures to wrap
conditional or redundant state elements:

.. code-block:: yaml

    {% if grains['os'] != 'FreeBSD' %}
    tcsh:
        pkg:
            - installed
    {% endif %}

    motd:
      file.managed:
        {% if grains['os'] == 'FreeBSD' %}
        - name: /etc/motd
        {% elif grains['os'] == 'Debian' %}
        - name: /etc/motd.tail
        {% endif %}
        - source: salt://motd

In this example, the first if block will only be evaluated on minions that
aren't running FreeBSD, and the second block changes the file name based on the
*os* grain.

Writing **if-else** blocks can lead to very redundant state files however. In
this case, using :doc:`pillars</topics/pillar/index>`, or using a previously
defined variable might be easier:

.. code-block:: yaml

    {% set motd = ['/etc/motd'] %}
    {% if grains['os'] == 'Debian' %}
      {% set motd = ['/etc/motd.tail', '/var/run/motd'] %}
    {% endif %}

    {% for motdfile in motd %}
    {{ motdfile }}:
      file.managed:
        - source: salt://motd
    {% endfor %}

Using a variable set by the template, the `for loop`_ will iterate over the
list of MOTD files to update, adding a state block for each file.

.. _`for loop`: http://jinja.pocoo.org/docs/templates/#for

Passing Variables
=================

It is also possible to pass additional variable context directly into a
template, using the ``defaults`` and ``context`` mappings of the
:doc:`file.managed</ref/states/all/salt.states.file>` state:

.. code-block:: yaml

    /etc/motd:
      file.managed:
        - source: salt://motd
        - template: jinja
        - defaults:
            message: 'Foo'
        {% if grains['os'] == 'FreeBSD' %}
        - context:
            message: 'Bar'
        {% endif %}

The template will receive a variable ``message``, which would be accessed in the
template using ``{{ message }}``. If the operating system is FreeBSD, the value
of the variable ``message`` would be *Bar*, otherwise it is the default
*Foo*

Include and Import
==================

Includes and imports_ can be used to share common, reusable state configuration
between state files and between files.

.. code-block:: yaml

    {% from 'lib.sls' import test %}

This would import the ``test`` template variable or macro, not the ``test``
state element, from the file ``lib.sls``. In the case that the included file
performs checks again grains, or something else that requires context, passing
the context into the included file is required:

.. code-block:: yaml

    {% from 'lib.sls' import test with context %}

.. _imports: http://jinja.pocoo.org/docs/templates/#import

Variable and block Serializers
==============================

Salt allows one to serialize any variable into **json** or **yaml** or
**python**. For example this variable::

    data:
      foo: True
      bar: 42
      baz:
        - 1
        - 2
        - 3
      qux: 2.0

with this template::

    yaml -> {{ data|yaml }}

    json -> {{ data|json }}

    python -> {{ data|python }}

will be rendered has::

    yaml -> {bar: 42, baz: [1, 2, 3], foo: true, qux: 2.0}

    json -> {"baz": [1, 2, 3], "foo": true, "bar": 42, "qux": 2.0}

    python -> {u'data': {u'bar': 42, u'baz': [1, 2, 3], u'foo': True, u'qux': 2.0}}

Strings and variables can be deserialized with **load_yaml** and **load_json**
tags and filters. It allows one to manipulate data directly in templates, easily:

.. code-block:: yaml

    {%- set json_var = '{"foo": "bar", "baz": "qux"}'|load_json %}
    My json_var foo is {{ json_var.foo }}

    {%- set yaml_var = "{bar: baz: qux}"|load_yaml %}
    My yaml_var bar.baz is {{ yaml_var.bar.baz }}

    {%- load_json as json_block %}
      {
        "qux": {{ yaml_var|json }},
      }
    {% endload %}
    My json_block qux.bar.baz is {{ json_block.qux.bar.baz }}

    {%- load_yaml as yaml_block %}
      bar:
        baz:
          qux
    {% endload %}
    My yaml_block bar.baz is {{ yaml2.bar.baz }}

will be rendered has::

    My json_var foo is bar

    My yaml_var bar.baz is qux

    My json_block foo is quz

    My yaml_block bar.baz is qux

Template Serializers
====================

Salt implements **import_yaml** and **import_json** tags. They work like the
`import tag`_, except that the document is also deserialized.

Imagine you have a generic state file in which you have the complete data of
your infrastucture:

.. code-block:: yaml

    # everything.sls
    users:
      foo:
        - john
      bar:
        - bob
      baz:
        - smith

But you don't want to expose everything to a minion. This state file:

.. code-block:: yaml

    # specialized.sls
    {% import_yaml "everything.sls" as all %}
    my_admins:
      my_foo: {{ all.users.foo|yaml }}

will be rendered has::

    my_admins:
      my_foo: [john]

.. _`import tag`: http://jinja.pocoo.org/docs/templates/#import

Macros
======

Macros_ are helpful for eliminating redundant code, however stripping whitespace
from the template block, as well as contained blocks, may be necessary to
emulate a variable return from the macro.

.. code-block:: yaml

    # init.sls
    {% from 'lib.sls' import pythonpkg with context %}

    python-virtualenv:
      pkg.installed:
        - name: {{ pythonpkg('virtualenv') }}

    python-fabric:
      pkg.installed:
        - name: {{ pythonpkg('fabric') }}

.. code-block:: yaml

    # lib.sls
    {% macro pythonpkg(pkg) -%}
      {%- if grains['os'] == 'FreeBSD' -%}
        py27-{{ pkg }}
      {%- elif grains['os'] == 'Debian' -%}
        python-{{ pkg }}
      {%- endif -%}
    {%- endmacro %}

This would define a macro_ that would return a string of the full package name,
depending on the packaging system's naming convention. The whitespace of the
macro was eliminated, so that the macro would return a string without line
breaks, using `whitespace control`_.

Template Inheritance
====================

`Template inheritance`_ works fine from state files and files. The search path
starts at the root of the state tree or pillar.

.. _`Template inheritance`: http://jinja.pocoo.org/docs/templates/#template-inheritance
.. _`Macros`: http://jinja.pocoo.org/docs/templates/#macros
.. _`macro`: http://jinja.pocoo.org/docs/templates/#macros
.. _`whitespace control`: http://jinja.pocoo.org/docs/templates/#whitespace-control

Filters
=======

Saltstack extends `builtin filters`_ with his custom filters:

strftime
  Converts any time related object into a time based string. It requires a
  valid :ref:`strftime directives <python2:strftime-strptime-behavior>`. An
  :ref:`exhaustive list <python2:strftime-strptime-behavior>` can be found in
  the official Python documentation. Fuzzy dates are parsed by `timelib`_ python
  module. Some examples are available on this pages.

  .. code-block:: yaml

      {{ "2002/12/25"|strftime("%y") }}
      {{ "1040814000"|strftime("%Y-%m-%d") }}
      {{ datetime|strftime("%u") }}
      {{ "now"|strftime }}

.. _`builtin filters`: http://jinja.pocoo.org/docs/templates/##builtin-filters
.. _`timelib`: https://github.com/pediapress/timelib/

Jinja in Files
==============

Jinja_ can be used in the same way in managed files:

.. code-block:: yaml

    # redis.sls
    /etc/redis/redis.conf:
        file.managed:
            - source: salt://redis.conf
            - template: jinja
            - context:
                bind: 127.0.0.1

.. code-block:: yaml

    # lib.sls
    {% set port = 6379 %}

.. code-block:: ini

    # redis.conf
    {% from 'lib.sls' import port with context %}
    port {{ port }}
    bind {{ bind }}

As an example, configuration was pulled from the file context and from an
external template file.

.. note::

    Macros and variables can be shared across templates. They should not be
    starting with one or more underscores, and should be managed by one of the
    following tags: `macro`, `set`, `load_yaml`, `load_json`, `import_yaml` and
    `import_json`.


.. automodule:: salt.renderers.jinja
    :members:
