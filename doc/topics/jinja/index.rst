.. _jinja:

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
this case, using :ref:`pillars<pillar>`, or using a previously
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

The filter_by function can also be used to set variables based on grains:

.. code-block:: yaml

   {% set auditd = salt['grains.filter_by']({
   'RedHat': { 'package': 'audit' },
   'Debian': { 'package': 'auditd' },
   }) %}

.. _`for loop`: http://jinja.pocoo.org/docs/templates/#for

Include and Import
==================

Includes and imports_ can be used to share common, reusable state configuration
between state files and between files.

.. code-block:: yaml

    {% from 'lib.sls' import test %}

This would import the ``test`` template variable or macro, not the ``test``
state element, from the file ``lib.sls``. In the case that the included file
performs checks against grains, or something else that requires context, passing
the context into the included file is required:

.. code-block:: yaml

    {% from 'lib.sls' import test with context %}

Including Context During Include/Import
---------------------------------------

By adding ``with context`` to the include/import directive, the
current context can be passed to an included/imported template.

.. code-block:: yaml

    {% import 'openssl/vars.sls' as ssl with context %}


.. _imports: http://jinja.pocoo.org/docs/templates/#import

Macros
======

Macros_ are helpful for eliminating redundant code. Macros are most useful as
mini-templates to repeat blocks of strings with a few parameterized variables.
Be aware that stripping whitespace from the template block, as well as
contained blocks, may be necessary to emulate a variable return from the macro.

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

Saltstack extends `builtin filters`_ with these custom filters:

strftime
  Converts any time related object into a time based string. It requires a
  valid :ref:`strftime directives <python2:strftime-strptime-behavior>`. An
  :ref:`exhaustive list <python2:strftime-strptime-behavior>` can be found in
  the official Python documentation.

  .. code-block:: yaml

      {% set curtime = None | strftime() %}

  Fuzzy dates require the `timelib`_ Python module is installed.

  .. code-block:: yaml

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

  .. code-block:: yaml

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

  .. code-block:: yaml

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

to_bool
  Returns the logical value of an element. Example:

  .. code-block:: jinja

      {{ 'yes' | to_bool }}
      {{ 'true' | to_bool }}
      {{ 1 | to_bool }}
      {{ 'no' | to_bool }}

  Will be rendered as:

  .. code-block:: python

    True
    True
    True
    False

quote
  Wraps a text around quoutes.

regex_search
  Scan through string looking for a location where this regular expression
  produces a match. Returns ``None`` in case there were no matches found

  Example:

  .. code-block:: jinja

    {{ 'abcdefabcdef' | regex_search('BC(.*)', ignorecase=True) }}

  Returns:

  .. code-block:: python

    ('defabcdef',)

regex_match
  If zero or more characters at the beginning of string match this regular
  expression, otherwise returns ``None``.

  Example:

  .. code-block:: jinja

    {{ 'abcdefabcdef' | regex_match('BC(.*)', ignorecase=True) }}

  Returns:

  .. code-block:: python

    None

uuid
  Return a UUID.

  Example:

  .. code-block:: jinja

    {{ 'random' | uuid }}

  Returns:

  .. code-block:: python

    3652b285-26ad-588e-a5dc-c2ee65edc804

min
  Return the minim value from a list.

max
  Returns the maximum value from a list.

avg
  Returns the average value of the elements of a list

union
  Return the union of two lists. Example:

  .. code-block:: jinja

    {{ 1, 2, 3] | union([2, 3, 4]) | join(', ') }}

intersect
  Return the intersection of two lists. Example:

  .. code-block:: jinja

    {{ [1, 2, 3] | intersect([2, 3, 4]) }}

difference
  Return the difference of two lists. Example:

  .. code-block:: jinja

    {%- my_list = [1, 2, 3] -%}
    {{ my_list | difference([2, 3, 4]) }}

symmetric_difference
  Return the symmetric difference of two lists. Example:

  .. code-block:: jinja

    {%- my_list = [1, 2, 3] -%}
    {{ my_list | symmetric_difference([2, 3, 4]) }}

md5
  Return the md5 digest of a string.

  .. code-block:: jinja

    {{ 'random' | md5 }}

sha256
  Return the sha256 digest of a string.

  .. code-block:: jinja

    {{ 'random' | sha256 }}

sha512
  Return the sha512 digest of a string.

  .. code-block:: jinja

    {{ 'random' | sha512 }}

base64_encode
  Encode a string as base64.

  .. code-block:: jinja

    {{ 'random' | base64_encode }}

base64_decode
  Decode a base64-encoded string.

  .. code-block:: jinja

    {{ 'random' | base64_decode }}

hmac
  Verify a challenging hmac signature against a string / shared-secret. Returns
  a boolean value.

  .. code-block:: jinja

    {{ 'random' | hmac('secret', 'eBWf9bstXg+NiP5AMPzEM9W5YMm/AmQ=') }}

http_query
  Return the HTTP reply object from a URL.

  .. code-block:: jinja

    {{ 'http://www.google.com' | http_query }}

.. _`builtin filters`: http://jinja.pocoo.org/docs/templates/#builtin-filters
.. _`timelib`: https://github.com/pediapress/timelib/

Networking Filters
==================

The following networking-related filters are supported:

is_ip
  Return if a string is a valid IP Address.

  .. code-block:: jinja

    {{ '192.168.0.1' | is_ip }}

  Additionally accepts the following options:

  - global
  - link-local
  - loopback
  - multicast
  - private
  - public
  - reserved
  - site-local
  - unspecified

  Example - test if a string is a valid loopback IP address.

  .. code-block:: jinja

    {{ '192.168.0.1' | is_ip(options='loopback') }}

is_ipv4
  Returns if a string is a valid IPv4 address. Supports the same options
  as ``is_ip``.

  .. code-block:: jinja

    {{ '192.168.0.1' | is_ipv4 }}

is_ip6
  Returns if a string is a valid IPv6 address. Supports the same options
  as ``is_ip``.

  .. code-block:: jinja

    {{ 'fe80::' | is_ipv6 }}

ipaddr
  From a list, returns only valid IP entries. Supports the same options
  as ``is_ip``. The list can contains also IP interfaces/networks.

  Example:

  .. code-block:: jinja

    {{ ['192.168.0.1', 'foo', 'bar', 'fe80::'] | ipaddr }}

  Returns:

  .. code-block:: python

    ['192.168.0.1', 'fe80::']

ipv4
  From a list, returns only valid IPv4 entries. Supports the same options
  as ``is_ip``. The list can contains also IP interfaces/networks.

  Example:

  .. code-block:: jinja

    {{ ['192.168.0.1', 'foo', 'bar', 'fe80::'] | ipv4 }}

  Returns:

  .. code-block:: python

    ['192.168.0.1']

ipv6
  From a list, returns only valid IPv6 entries. Supports the same options
  as ``is_ip``. The list can contains also IP interfaces/networks.

  Example:

  .. code-block:: jinja

    {{ ['192.168.0.1', 'foo', 'bar', 'fe80::'] | ipv4 }}

  Returns:

  .. code-block:: python

    ['fe80::']

network_hosts
  Return the list of hosts within a networks.

  Example:

  .. code-block:: jinja

    {{ '192.168.0.1/30' | network_hosts }}

  Returns:

  .. code-block:: python

    ['192.168.0.1', '192.168.0.2']

network_size
  Return the size of the network.

  Example:

  .. code-block:: jinja

    {{ '192.168.0.1/8' | network_size }}

  Returns:

  .. code-block:: python

    16777216

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

Escaping Jinja
==============

Occasionally, it may be necessary to escape Jinja syntax. There are two ways
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

.. code-block:: yaml

    # The following two function calls are equivalent.
    {{ salt['cmd.run']('whoami') }}
    {{ salt.cmd.run('whoami') }}

Debugging
=========

The ``show_full_context`` function can be used to output all variables present
in the current Jinja context.

.. versionadded:: 2014.7.0

.. code-block:: yaml

    Context is: {{ show_full_context() }}

Custom Execution Modules
========================

Custom execution modules can be used to supplement or replace complex Jinja. Many
tasks that require complex looping and logic are trivial when using Python
in a Salt execution module. Salt execution modules are easy to write and
distribute to Salt minions.

Functions in custom execution modules are available in the Salt execution
module dictionary just like the built-in execution modules:

.. code-block:: yaml

    {{ salt['my_custom_module.my_custom_function']() }}

- :ref:`How to Convert Jinja Logic to an Execution Module <tutorial-jinja_to_execution-module>`
- :ref:`Writing Execution Modules <writing-execution-modules>`

