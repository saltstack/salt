.. _understanding-jinja:

===================
Understanding Jinja
===================

`Jinja <http://jinja.pocoo.org/docs/>`_ is the default templating language
in SLS files.

Jinja in States
===============

.. _Jinja: http://jinja.pocoo.org/docs/templates/

Jinja is evaluated before YAML, which means it is evaluated before the States
are run.

The most basic usage of Jinja in state files is using control structures to
wrap conditional or redundant state elements:

.. code-block:: jinja

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
this case, using :ref:`pillars<pillar>`, or using a previously
defined variable might be easier:

.. code-block:: jinja

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

The filter_by function can also be used to set variables based on grains:

.. code-block:: jinja

   {% set auditd = salt['grains.filter_by']({
   'RedHat': { 'package': 'audit' },
   'Debian': { 'package': 'auditd' },
   }) %}

.. _`for loop`: http://jinja.pocoo.org/docs/templates/#for

Include and Import
==================

Includes and imports_ can be used to share common, reusable state configuration
between state files and between files.

.. code-block:: jinja

    {% from 'lib.sls' import test %}

This would import the ``test`` template variable or macro, not the ``test``
state element, from the file ``lib.sls``. In the case that the included file
performs checks again grains, or something else that requires context, passing
the context into the included file is required:

.. code-block:: jinja

    {% from 'lib.sls' import test with context %}

Including Context During Include/Import
---------------------------------------

By adding ``with context`` to the include/import directive, the
current context can be passed to an included/imported template.

.. code-block:: jinja

    {% import 'openssl/vars.sls' as ssl with context %}


.. _imports: http://jinja.pocoo.org/docs/templates/#import

Macros
======

Macros_ are helpful for eliminating redundant code. Macros are most useful as
mini-templates to repeat blocks of strings with a few parameterized variables.
Be aware that stripping whitespace from the template block, as well as
contained blocks, may be necessary to emulate a variable return from the macro.

.. code-block:: jinja

    # init.sls
    {% from 'lib.sls' import pythonpkg with context %}

    python-virtualenv:
      pkg.installed:
        - name: {{ pythonpkg('virtualenv') }}

    python-fabric:
      pkg.installed:
        - name: {{ pythonpkg('fabric') }}

.. code-block:: jinja

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

Saltstack extends `builtin filters`_ with these custom filters:

strftime
  Converts any time related object into a time based string. It requires a
  valid :ref:`strftime directives <python2:strftime-strptime-behavior>`. An
  :ref:`exhaustive list <python2:strftime-strptime-behavior>` can be found in
  the official Python documentation.

  .. code-block:: jinja

      {% set curtime = None | strftime() %}

  Fuzzy dates require the `timelib`_ Python module is installed.

  .. code-block:: jinja

      {{ "2002/12/25"|strftime("%y") }}
      {{ "1040814000"|strftime("%Y-%m-%d") }}
      {{ datetime|strftime("%u") }}
      {{ "tomorrow"|strftime }}

sequence
  Ensure that parsed data is a sequence.

yaml_encode
  Serializes a single object into a YAML scalar with any necessary
  handling for escaping special characters.  This will work for any
  scalar YAML data type: ints, floats, timestamps, booleans, strings,
  unicode.  It will *not* work for multi-objects such as sequences or
  maps.

  .. code-block:: jinja

      {%- set bar = 7 %}
      {%- set baz = none %}
      {%- set zip = true %}
      {%- set zap = 'The word of the day is "salty"' %}

      {%- load_yaml as foo %}
      bar: {{ bar|yaml_encode }}
      baz: {{ baz|yaml_encode }}
      baz: {{ zip|yaml_encode }}
      baz: {{ zap|yaml_encode }}
      {%- endload %}

  In the above case ``{{ bar }}`` and ``{{ foo.bar }}`` should be
  identical and ``{{ baz }}`` and ``{{ foo.baz }}`` should be
  identical.

yaml_dquote
  Serializes a string into a properly-escaped YAML double-quoted
  string.  This is useful when the contents of a string are unknown
  and may contain quotes or unicode that needs to be preserved.  The
  resulting string will be emitted with opening and closing double
  quotes.

  .. code-block:: jinja

      {%- set bar = '"The quick brown fox . . ."' %}
      {%- set baz = 'The word of the day is "salty".' %}

      {%- load_yaml as foo %}
      bar: {{ bar|yaml_dquote }}
      baz: {{ baz|yaml_dquote }}
      {%- endload %}

  In the above case ``{{ bar }}`` and ``{{ foo.bar }}`` should be
  identical and ``{{ baz }}`` and ``{{ foo.baz }}`` should be
  identical.  If variable contents are not guaranteed to be a string
  then it is better to use ``yaml_encode`` which handles all YAML
  scalar types.

yaml_squote
   Similar to the ``yaml_dquote`` filter but with single quotes.  Note
   that YAML only allows special escapes inside double quotes so
   ``yaml_squote`` is not nearly as useful (viz. you likely want to
   use ``yaml_encode`` or ``yaml_dquote``).

.. _`builtin filters`: http://jinja.pocoo.org/docs/templates/#builtin-filters
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

.. code-block:: jinja

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

Escaping Jinja
==============

Occasionally, it may be necessary to escape Jinja syntax. There are two ways to
to do this in Jinja. One is escaping individual variables or strings and the
other is to escape entire blocks.

To escape a string commonly used in Jinja syntax such as ``{{``, you can use the
following syntax:

.. code-block:: jinja

    {{ '{{' }}

For larger blocks that contain Jinja syntax that needs to be escaped, you can use
raw blocks:

.. code-block:: jinja

    {% raw %}
        some text that contains jinja characters that need to be escaped
    {% endraw %}

See the `Escaping`_ section of Jinja's documentation to learn more.

A real-word example of needing to use raw tags to escape a larger block of code
is when using ``file.managed`` with the ``contents_pillar`` option to manage
files that contain something like consul-template, which shares a syntax subset
with Jinja. Raw blocks are necessary here because the Jinja in the pillar would
be rendered before the file.managed is ever called, so the Jinja syntax must be
escaped:

.. code-block:: jinja

    {% raw %}
    - contents_pillar: |
        job "example-job" {
          <snipped>
          task "example" {
              driver = "docker"

              config {
                  image = "docker-registry.service.consul:5000/example-job:{{key "nomad/jobs/example-job/version"}}"
          <snipped>
    {% endraw %}

.. _`Escaping`: http://jinja.pocoo.org/docs/dev/templates/#escaping

Calling Salt Functions
======================

The Jinja renderer provides a shorthand lookup syntax for the ``salt``
dictionary of :term:`execution function <Execution Function>`.

.. versionadded:: 2014.7.0

.. code-block:: jinja

    # The following two function calls are equivalent.
    {{ salt['cmd.run']('whoami') }}
    {{ salt.cmd.run('whoami') }}

Debugging
=========

The ``show_full_context`` function can be used to output all variables present
in the current Jinja context.

.. versionadded:: 2014.7.0

.. code-block:: jinja

    Context is: {{ show_full_context() }}

Custom Execution Modules
========================

Custom execution modules can be used to supplement or replace complex Jinja. Many
tasks that require complex looping and logic are trivial when using Python
in a Salt execution module. Salt execution modules are easy to write and
distribute to Salt minions.

Functions in custom execution modules are available in the Salt execution
module dictionary just like the built-in execution modules:

.. code-block:: jinja

    {{ salt['my_custom_module.my_custom_function']() }}

- :ref:`How to Convert Jinja Logic to an Execution Module <tutorial-jinja_to_execution-module>`
- :ref:`Writing Execution Modules <writing-execution-modules>`

