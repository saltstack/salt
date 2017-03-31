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
performs checks against grains, or something else that requires context, passing
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

to_bool
  Returns the logical value of an element.

  Example:

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

exactly_n_true
  Tests that exactly N items in an iterable are "truthy" (neither None, False, nor 0).

  Example:

  .. code-block:: jinja

    {{ ['yes', 0, False, 'True'] | exactly_n_true(2) }}

  Returns:

  .. code-block:: python

    True

exactly_one_true
  Tests that exactly one item in an iterable is "truthy" (neither None, False, nor 0).

  Example:

  .. code-block:: jinja

    {{ ['yes', False, 0, None] | exactly_one_true }}

  Returns:

  .. code-block:: python

    True

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

  .. code-block:: text

    None

uuid
  Return a UUID.

  Example:

  .. code-block:: jinja

    {{ 'random' | uuid }}

  Returns:

  .. code-block:: text

    3652b285-26ad-588e-a5dc-c2ee65edc804

is_list
  Return if an object is list.

  Example:

  .. code-block:: jinja

    {{ [1, 2, 3] | is_list }}

  Returns:

  .. code-block:: python

    True

is_iter
  Return if an object is iterable.

  Example:

  .. code-block:: jinja

    {{ [1, 2, 3] | is_iter }}

  Returns:

  .. code-block:: python

    True

min
  Return the minimum value from a list.

  Example:

  .. code-block:: jinja

    {{ [1, 2, 3] | min }}

  Returns:

  .. code-block:: text

    1

max
  Returns the maximum value from a list.

  Example:

  .. code-block:: jinja

    {{ [1, 2, 3] | max }}

  Returns:

  .. code-block:: text

    3

avg
  Returns the average value of the elements of a list

  Example:

  .. code-block:: jinja

    {{ [1, 2, 3] | avg }}

  Returns:

  .. code-block:: text

    2

union
  Return the union of two lists.

  Example:

  .. code-block:: jinja

    {{ [1, 2, 3] | union([2, 3, 4]) | join(', ') }}

  Returns:

  .. code-block:: text

    1, 2, 3, 4

intersect
  Return the intersection of two lists.

  Example:

  .. code-block:: jinja

    {{ [1, 2, 3] | intersect([2, 3, 4]) | join(', ') }}

  Returns:

  .. code-block:: text

    2, 3

difference
  Return the difference of two lists.

  Example:

  .. code-block:: jinja

    {{ [1, 2, 3] | difference([2, 3, 4]) | join(', ') }}

  Returns:

  .. code-block:: text

    1

symmetric_difference
  Return the symmetric difference of two lists.

  Example:

  .. code-block:: jinja

    {{ [1, 2, 3] | symmetric_difference([2, 3, 4]) | join(', ') }}

  Returns:

  .. code-block:: text

    1, 4

is_sorted
  Return is an iterable object is already sorted.

  Example:

  .. code-block:: jinja

    {{ [1, 2, 3] | is_sorted }}

  Returns:

  .. code-block:: python

    True

compare_lists
  Compare two lists and return a dictionary with the changes.

  Example:

  .. code-block:: jinja

    {{ [1, 2, 3] | compare_lists([1, 2, 4]) }}

  Returns:

  .. code-block:: python

    {'new': 4, 'old': 3}

compare_dicts
  Compare two dictionaries and return a dictionary with the changes.

  Example:

  .. code-block:: jinja

    {{ {'a': 'b'} | compare_lists({'a': 'c'}) }}

  Returns:

  .. code-block:: python

    {'a': {'new': 'c', 'old': 'b'}}

is_hex
  Return True if the value is hexazecimal.

  Example:

  .. code-block:: jinja

    {{ '0xabcd' | is_hex }}
    {{ 'xyzt' | is_hex }}

  Returns:

  .. code-block:: python

    True
    False

contains_whitespace
  Return True if a text contains whitespaces.

  Example:

  .. code-block:: jinja

    {{ 'abcd' | contains_whitespace }}
    {{ 'ab cd' | contains_whitespace }}

  Returns:

  .. code-block:: python

    False
    True

substring_in_list
  Return is a substring is found in a list of string values.

  Example:

  .. code-block:: jinja

    {{ 'abcd' | substring_in_list(['this', 'is', 'an abcd example']) }}

  Returns:

  .. code-block:: python

    True

check_whitelist_blacklist
  Check a whitelist and/or blacklist to see if the value matches it.

  Example:

  .. code-block:: jinja

    {{ 5 | check_whitelist_blacklist(whitelist=[5, 6, 7]) }}
    {{ 5 | check_whitelist_blacklist(blacklist=[5, 6, 7]) }}

  Returns:

  .. code-block:: python

    True

date_format
  Converts unix timestamp into human-readable string.

  Example:

  .. code-block:: jinja

    {{ 1457456400 | date_format }}
    {{ 1457456400 | date_format('%d.%m.%Y %H:%M') }}

  Returns:

  .. code-block:: text

    2017-03-08
    08.03.2017 17:00

str_to_num
  Converts a string to its numerical value.

  Example:

  .. code-block:: jinja

    {{ '5' | str_to_num }}

  Returns:

  .. code-block:: python

    5

to_bytes
  Converts string-type object to bytes.

  Example:

  .. code-block:: jinja

    {{ 'wall of text' | to_bytes }}

json_decode_list
  JSON decodes as unicode, Jinja needs bytes.

  Example:

  .. code-block:: jinja

    {{ [1, 2, 3] | json_decode_list }}

  Returns:

  .. code-block:: python

    [1, 2, 3]

json_decode_dict
  JSON decodes as unicode, Jinja needs bytes.

  Example:

  .. code-block:: jinja

    {{ {'a': 'b'} | json_decode_dict }}

  Returns:

  .. code-block:: python

    {'a': 'b'}

rand_str
  Generate a random string and applies a hash. Default hashing: md5.

  Example:

  .. code-block:: jinja

    {% set passwd_length = 17 %}
    {{ passwd_length | rand_str }}
    {{ passwd_length | rand_str('sha512') }}

  Returns:

  .. code-block:: text

    43ec517d68b6edd3015b3edc9a11367b
    d94a45acd81f8e3107d237dbc0d5d195f6a52a0d188bc0284c0763ece1eac9f9496fb6a531a296074c87b3540398dace1222b42e150e67c9301383fde3d66ae5

md5
  Return the md5 digest of a string.

  Example:

  .. code-block:: jinja

    {{ 'random' | md5 }}

  Returns:

  .. code-block:: text

    7ddf32e17a6ac5ce04a8ecbf782ca509

sha256
  Return the sha256 digest of a string.

  Example:

  .. code-block:: jinja

    {{ 'random' | sha256 }}

  Returns:

  .. code-block:: text

    a441b15fe9a3cf56661190a0b93b9dec7d04127288cc87250967cf3b52894d11

sha512
  Return the sha512 digest of a string.

  Example:

  .. code-block:: jinja

    {{ 'random' | sha512 }}

  Returns:

  .. code-block:: text

    811a90e1c8e86c7b4c0eef5b2c0bf0ec1b19c4b1b5a242e6455be93787cb473cb7bc9b0fdeb960d00d5c6881c2094dd63c5c900ce9057255e2a4e271fc25fef1

base64_encode
  Encode a string as base64.

  Example:

  .. code-block:: jinja

    {{ 'random' | base64_encode }}

  Returns:

  .. code-block:: text

    cmFuZG9t

base64_decode
  Decode a base64-encoded string.

  .. code-block:: jinja

    {{ 'Z2V0IHNhbHRlZA==' | base64_decode }}

  Returns:

  .. code-block:: text

    get salted

hmac
  Verify a challenging hmac signature against a string / shared-secret. Returns
  a boolean value.

  Example:

  .. code-block:: jinja

    {{ 'get salted' | hmac('shared secret', 'eBWf9bstXg+NiP5AOwppB5HMvZiYMPzEM9W5YMm/AmQ=') }}

  Returns:

  .. code-block:: python

    True

http_query
  Return the HTTP reply object from a URL.

  Example:

  .. code-block:: jinja

    {{ 'http://jsonplaceholder.typicode.com/posts/1' | http_query }}

  Returns:

  .. code-block:: python

    {
      'body': '{
        "userId": 1,
        "id": 1,
        "title": "sunt aut facere repellat provident occaecati excepturi optio reprehenderit",
        "body": "quia et suscipit\\nsuscipit recusandae consequuntur expedita et cum\\nreprehenderit molestiae ut ut quas totam\\nnostrum rerum est autem sunt rem eveniet architecto"
      }'
    }

.. _`builtin filters`: http://jinja.pocoo.org/docs/templates/#builtin-filters
.. _`timelib`: https://github.com/pediapress/timelib/

Networking Filters
------------------

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

gen_mac
  Generates a MAC address with the defined OUI prefix.

  Common prefixes:

  - ``00:16:3E`` -- Xen
  - ``00:18:51`` -- OpenVZ
  - ``00:50:56`` -- VMware (manually generated)
  - ``52:54:00`` -- QEMU/KVM
  - ``AC:DE:48`` -- PRIVATE

  Example:

  .. code-block:: jinja

    {{ '00:50' | gen_mac }}

  Returns:

  .. code-block:: text

    00:50:71:52:1C

mac_str_to_bytes
  Converts a string representing a valid MAC address to bytes.

  Example:

  .. code-block:: jinja

    {{ '00:11:22:33:44:55' | mac_str_to_bytes }}

dns_check
  Return the ip resolved by dns, but do not exit on failure, only raise an
  exception. Obeys system preference for IPv4/6 address resolution.

  Example:

  .. code-block:: jinja

    {{ 'www.google.com' | dns_check }}

  Returns:

  .. code-block:: text

    '172.217.3.196'

File filters
------------

is_text_file
  Return if a file is text.

  Uses heuristics to guess whether the given file is text or binary,
  by reading a single block of bytes from the file.
  If more than 30% of the chars in the block are non-text, or there
  are NUL ('\x00') bytes in the block, assume this is a binary file.

  Example:

  .. code-block:: jinja

    {{ '/etc/salt/master' | is_text_file }}

  Returns:

  .. code-block:: python

    True

is_binary_file
  Return if a file is binary.

  Detects if the file is a binary, returns bool. Returns True if the file is
  a bin, False if the file is not and None if the file is not available.

  Example:

  .. code-block:: jinja

    {{ '/etc/salt/master' | is_binary_file }}

  Returns:

  .. code-block:: python

    False

is_empty_file
  Return if a file is empty.

  Example:

  .. code-block:: jinja

    {{ '/etc/salt/master' | is_empty_file }}

  Returns:

  .. code-block:: python

    False

file_hashsum
  Return the hashsum of a file.

  Example:

  .. code-block:: jinja

    {{ '/etc/salt/master' | file_hashsum }}

  Returns:

  .. code-block:: text

    02d4ef135514934759634f10079653252c7ad594ea97bd385480c532bca0fdda

list_files
  Return a recursive list of files under a specific path.

  Example:

  .. code-block:: jinja

    {{ '/etc/salt/' | list_files | join('\n') }}

  Returns:

  .. code-block:: text

    /etc/salt/master
    /etc/salt/proxy
    /etc/salt/minion
    /etc/salt/pillar/top.sls
    /etc/salt/pillar/device1.sls

path_join
  Joins absolute paths.

  Example:

  .. code-block:: jinja

    {{ '/etc/salt/' | path_join('pillar', 'device1.sls') }}

  Returns:

  .. code-block:: text

    /etc/salt/pillar/device1.sls

which
  Python clone of /usr/bin/which.

  Example:

  .. code-block:: jinja

    {{ 'salt-master' | which }}

  Returns:

  .. code-block:: text

    /usr/local/salt/virtualenv/bin/salt-master

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

Logs
----

.. versionadded:: Nitrogen

Yes, in Salt, one is able to debug a complex Jinja template using the logs.
For example, making the call:

.. code-block:: yaml

    {%- do salt.log.error('testing jinja logging') -%}

Will insert the following message in the minion logs:

.. code-block:: text

    2017-02-01 01:24:40,728 [salt.module.logmod][ERROR   ][3779] testing jinja logging

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

Custom Jinja filters
====================

Given that all execution modules are available in the Jinja template,
one can easily define a custom module as in the previous paragraph
and use it as a Jinja filter.
However, please note that it will not be accessible through the pipe.

For example, instead of:

.. code-block:: jinja

    {{ my_variable | my_jinja_filter }}

The user will need to define ``my_jinja_filter`` function under an extension
module, say ``my_filters`` and use as:

.. code-block:: jinja

    {{ salt.my_filters.my_jinja_filter(my_variable) }}

The greatest benefit is that you are able to access thousands of existing functions, e.g.:

- get the DNS AAAA records for a specific address using the :mod:`dnsutil <salt.modules.dnsutil>`:

  .. code-block:: jinja

    {{ salt.dnsutil.AAAA('www.google.com') }}

- retrieve a specific field value from a :mod:`Redis <salt.modules.modredis>` hash:

  .. code-block:: jinja

    {{ salt.redis.hget('foo_hash', 'bar_field') }}

- get the routes to ``0.0.0.0/0`` using the :mod:`NAPALM route <salt.modules.napalm_route>`:

  .. code-block:: jinja

    {{ salt.route.show('0.0.0.0/0') }}
