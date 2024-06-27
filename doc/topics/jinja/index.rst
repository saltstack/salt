.. _understanding-jinja:

===================
Understanding Jinja
===================

`Jinja`_ is the default templating language in SLS files.

.. _Jinja: https://jinja.palletsprojects.com/en/2.11.x/templates/

.. include:: ../../_incl/jinja_security.rst

Jinja in States
===============

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

In this example, the first **if** block will only be evaluated on minions that
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

.. _`for loop`: https://jinja.palletsprojects.com/en/2.11.x/templates/#for

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

Includes must use full paths, like so:

.. code-block:: jinja
   :caption: spam/eggs.jinja

    {% include 'spam/foobar.jinja' %}

Including Context During Include/Import
---------------------------------------

By adding ``with context`` to the include/import directive, the
current context can be passed to an included/imported template.

.. code-block:: jinja

    {% import 'openssl/vars.sls' as ssl with context %}


.. _imports: https://jinja.palletsprojects.com/en/2.11.x/templates/#import

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

.. _`Template inheritance`: https://jinja.palletsprojects.com/en/2.11.x/templates/#template-inheritance
.. _`Macros`: https://jinja.palletsprojects.com/en/2.11.x/templates/#macros
.. _`macro`: https://jinja.palletsprojects.com/en/2.11.x/templates/#macros
.. _`Whitespace control`: https://jinja.palletsprojects.com/en/2.11.x/templates/#whitespace-control

Errors
======

Saltstack allows raising custom errors using the ``raise`` Jinja function.

.. code-block:: jinja

    {{ raise('Custom Error') }}

When rendering the template containing the above statement, a ``TemplateError``
exception is raised, causing the rendering to fail with the following message:

.. code-block:: text

    TemplateError: Custom Error

Filters
=======

Saltstack extends `builtin filters`_ with these custom filters:

.. jinja_ref:: strftime

``strftime``
------------

Converts any time related object into a time based string. It requires valid
strftime directives. An exhaustive list can be found :ref:`here
<python:strftime-strptime-behavior>` in the Python documentation.

.. code-block:: jinja

    {% set curtime = None | strftime() %}

Fuzzy dates require the `timelib`_ Python module is installed.

.. code-block:: jinja

    {{ "2002/12/25"|strftime("%y") }}
    {{ "1040814000"|strftime("%Y-%m-%d") }}
    {{ datetime|strftime("%u") }}
    {{ "tomorrow"|strftime }}


.. jinja_ref:: sequence

``sequence``
------------

Ensure that parsed data is a sequence.


.. jinja_ref:: yaml_encode

``yaml_encode``
---------------

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
    zip: {{ zip|yaml_encode }}
    zap: {{ zap|yaml_encode }}
    {%- endload %}

In the above case ``{{ bar }}`` and ``{{ foo.bar }}`` should be
identical and ``{{ baz }}`` and ``{{ foo.baz }}`` should be
identical.


.. jinja_ref:: yaml_dquote

``yaml_dquote``
---------------

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


.. jinja_ref:: yaml_squote

``yaml_squote``
---------------

Similar to the ``yaml_dquote`` filter but with single quotes.  Note
that YAML only allows special escapes inside double quotes so
``yaml_squote`` is not nearly as useful (viz. you likely want to
use ``yaml_encode`` or ``yaml_dquote``).


.. jinja_ref:: dict_to_sls_yaml_params

``dict_to_sls_yaml_params``
---------------------------

.. versionadded:: 3005

Renders a formatted multi-line YAML string from a Python dictionary. Each
key/value pair in the dictionary will be added as a single-key dictionary
to a list that will then be sent to the YAML formatter.

Example:

.. code-block:: jinja

    {% set thing_params = {
        "name": "thing",
        "changes": True,
        "warnings": "OMG! Stuff is happening!"
       }
    %}

    thing:
      test.configurable_test_state:
        {{ thing_params | dict_to_sls_yaml_params | indent }}

Returns:

.. code-block:: yaml

    thing:
      test.configurable_test_state:
        - name: thing
        - changes: true
        - warnings: OMG! Stuff is happening!


.. jinja_ref:: to_bool

``to_bool``
-----------

.. versionadded:: 2017.7.0

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


.. jinja_ref:: exactly_n_true

``exactly_n_true``
------------------

.. versionadded:: 2017.7.0

Tests that exactly N items in an iterable are "truthy" (neither None, False, nor 0).

Example:

.. code-block:: jinja

  {{ ['yes', 0, False, 'True'] | exactly_n_true(2) }}

Returns:

.. code-block:: python

  True


.. jinja_ref:: exactly_one_true

``exactly_one_true``
--------------------

.. versionadded:: 2017.7.0

Tests that exactly one item in an iterable is "truthy" (neither None, False, nor 0).

Example:

.. code-block:: jinja

  {{ ['yes', False, 0, None] | exactly_one_true }}

Returns:

.. code-block:: python

  True


.. jinja_ref:: quote

``quote``
---------

.. versionadded:: 2017.7.0

This text will be wrapped in quotes.


.. jinja_ref:: regex_search

``regex_search``
----------------

.. versionadded:: 2017.7.0

Scan through string looking for a location where this regular expression
produces a match. Returns ``None`` in case there were no matches found

Example:

.. code-block:: jinja

  {{ 'abcdefabcdef' | regex_search('BC(.*)', ignorecase=True) }}

Returns:

.. code-block:: python

  ("defabcdef",)


.. jinja_ref:: regex_match

``regex_match``
---------------

.. versionadded:: 2017.7.0

If zero or more characters at the beginning of string match this regular
expression, otherwise returns ``None``.

Example:

.. code-block:: jinja

  {{ 'abcdefabcdef' | regex_match('BC(.*)', ignorecase=True) }}

Returns:

.. code-block:: text

  None


.. jinja_ref:: regex_replace

``regex_replace``
-----------------

.. versionadded:: 2017.7.0

Searches for a pattern and replaces with a sequence of characters.

Example:

.. code-block:: jinja

    {% set my_text = 'yes, this is a TEST' %}
    {{ my_text | regex_replace(' ([a-z])', '__\\1', ignorecase=True) }}

Returns:

.. code-block:: text

    yes,__this__is__a__TEST


.. jinja_ref:: uuid

``uuid``
--------

.. versionadded:: 2017.7.0

Return a UUID.

Example:

.. code-block:: jinja

  {{ 'random' | uuid }}

Returns:

.. code-block:: text

  3652b285-26ad-588e-a5dc-c2ee65edc804


.. jinja_ref:: is_list

``is_list``
-----------

.. versionadded:: 2017.7.0

Return if an object is list.

Example:

.. code-block:: jinja

  {{ [1, 2, 3] | is_list }}

Returns:

.. code-block:: python

  True


.. jinja_ref:: is_iter

``is_iter``
-----------

.. versionadded:: 2017.7.0

Return if an object is iterable.

Example:

.. code-block:: jinja

  {{ [1, 2, 3] | is_iter }}

Returns:

.. code-block:: python

  True


.. jinja_ref:: min

``min``
-------

.. versionadded:: 2017.7.0

Return the minimum value from a list.

Example:

.. code-block:: jinja

  {{ [1, 2, 3] | min }}

Returns:

.. code-block:: text

  1


.. jinja_ref:: max

``max``
-------

.. versionadded:: 2017.7.0

Returns the maximum value from a list.

Example:

.. code-block:: jinja

  {{ [1, 2, 3] | max }}

Returns:

.. code-block:: text

  3


.. jinja_ref:: avg

``avg``
-------

.. versionadded:: 2017.7.0

Returns the average value of the elements of a list

Example:

.. code-block:: jinja

  {{ [1, 2, 3] | avg }}

Returns:

.. code-block:: text

  2


.. jinja_ref:: union

``union``
---------

.. versionadded:: 2017.7.0

Return the union of two lists.

Example:

.. code-block:: jinja

  {{ [1, 2, 3] | union([2, 3, 4]) | join(', ') }}

Returns:

.. code-block:: text

  1, 2, 3, 4


.. jinja_ref:: intersect

``intersect``
-------------

.. versionadded:: 2017.7.0

Return the intersection of two lists.

Example:

.. code-block:: jinja

  {{ [1, 2, 3] | intersect([2, 3, 4]) | join(', ') }}

Returns:

.. code-block:: text

  2, 3


.. jinja_ref:: difference

``difference``
--------------

.. versionadded:: 2017.7.0

Return the difference of two lists.

Example:

.. code-block:: jinja

  {{ [1, 2, 3] | difference([2, 3, 4]) | join(', ') }}

Returns:

.. code-block:: text

  1



.. jinja_ref:: symmetric_difference

``symmetric_difference``
------------------------

.. versionadded:: 2017.7.0

Return the symmetric difference of two lists.

Example:

.. code-block:: jinja

  {{ [1, 2, 3] | symmetric_difference([2, 3, 4]) | join(', ') }}

Returns:

.. code-block:: text

  1, 4


.. jinja_ref:: flatten

``flatten``
-----------

.. versionadded:: 3005

Flatten a list.

.. code-block:: jinja

    {{ [3, [4, 2] ] | flatten }}
    # => [3, 4, 2]

Flatten only the first level of a list:

.. code-block:: jinja

    {{ [3, [4, [2]] ] | flatten(levels=1) }}
    # => [3, 4, [2]]

Preserve nulls in a list, by default ``flatten`` removes them.

.. code-block:: jinja

    {{ [3, None, [4, [2]] ] | flatten(levels=1, preserve_nulls=True) }}
    # => [3, None, 4, [2]]


.. jinja_ref:: combinations

``combinations``
----------------

.. versionadded:: 3005

Invokes the ``combinations`` function from the ``itertools`` library.

See the `itertools documentation`_ for more information.

.. code-block:: jinja

    {% for one, two in "ABCD" | combinations(2) %}{{ one~two }} {% endfor %}
    # => AB AC AD BC BD CD


.. jinja_ref:: combinations_with_replacement

``combinations_with_replacement``
---------------------------------

.. versionadded:: 3005

Invokes the ``combinations_with_replacement`` function from the ``itertools`` library.

See the `itertools documentation`_ for more information.

.. code-block:: jinja

    {% for one, two in "ABC" | combinations_with_replacement(2) %}{{ one~two }} {% endfor %}
    # => AA AB AC BB BC CC


.. jinja_ref:: compress

``compress``
------------

.. versionadded:: 3005

Invokes the ``compress`` function from the ``itertools`` library.

See the `itertools documentation`_ for more information.

.. code-block:: jinja

    {% for val in "ABCDEF" | compress([1,0,1,0,1,1]) %}{{ val }} {% endfor %}
    # => A C E F


.. jinja_ref:: permutations

``permutations``
----------------

.. versionadded:: 3005

Invokes the ``permutations`` function from the ``itertools`` library.

See the `itertools documentation`_ for more information.

.. code-block:: jinja

    {% for one, two in "ABCD" | permutations(2) %}{{ one~two }} {% endfor %}
    # => AB AC AD BA BC BD CA CB CD DA DB DC


.. jinja_ref:: product

``product``
-----------

.. versionadded:: 3005

Invokes the ``product`` function from the ``itertools`` library.

See the `itertools documentation`_ for more information.

.. code-block:: jinja

    {% for one, two in "ABCD" | product("xy") %}{{ one~two }} {% endfor %}
    # => Ax Ay Bx By Cx Cy Dx Dy


.. jinja_ref:: zip

``zip``
-------

.. versionadded:: 3005

Invokes the native Python ``zip`` function.

The ``zip`` function returns a zip object, which is an iterator of tuples where
the first item in each passed iterator is paired together, and then the second
item in each passed iterator are paired together etc.

If the passed iterators have different lengths, the iterator with the least
items decides the length of the new iterator.

.. code-block:: jinja

    {% for one, two in "ABCD" | zip("xy") %}{{ one~two }} {% endfor %}
    # => Ax By


.. jinja_ref:: zip_longest

``zip_longest``
---------------

.. versionadded:: 3005

Invokes the ``zip_longest`` function from the ``itertools`` library.

See the `itertools documentation`_ for more information.

.. _itertools documentation: https://docs.python.org/3/library/itertools.html#itertools.zip_longest

.. code-block:: jinja

    {% for one, two in "ABCD" | zip_longest("xy", fillvalue="-") %}{{ one~two }} {% endfor %}
    # => Ax By C- D-


.. jinja_ref:: method_call

``method_call``
---------------

.. versionadded:: 3001

Returns a result of object's method call.

Example #1:

.. code-block:: jinja

  {{ [1, 2, 1, 3, 4] | method_call('index', 1, 1, 3) }}

Returns:

.. code-block:: text

  2

This filter can be used with the `map filter`_ to apply object methods without
using loop constructs or temporary variables.

Example #2:

.. code-block:: jinja

  {% set host_list = ['web01.example.com', 'db01.example.com'] %}
  {% set host_list_split = [] %}
  {% for item in host_list %}
    {% do host_list_split.append(item.split('.', 1)) %}
  {% endfor %}
  {{ host_list_split }}

Example #3:

.. code-block:: jinja

  {{ host_list|map('method_call', 'split', '.', 1)|list }}

Return of examples #2 and #3:

.. code-block:: text

  [[web01, example.com], [db01, example.com]]

.. _`map filter`: https://jinja.palletsprojects.com/en/2.11.x/templates/#map


.. jinja_ref:: is_sorted

``is_sorted``
-------------

.. versionadded:: 2017.7.0

Return ``True`` if an iterable object is already sorted.

Example:

.. code-block:: jinja

  {{ [1, 2, 3] | is_sorted }}

Returns:

.. code-block:: python

  True


.. jinja_ref:: compare_lists

``compare_lists``
-----------------

.. versionadded:: 2017.7.0

Compare two lists and return a dictionary with the changes.

Example:

.. code-block:: jinja

  {{ [1, 2, 3] | compare_lists([1, 2, 4]) }}

Returns:

.. code-block:: python

  {"new": [4], "old": [3]}


.. jinja_ref:: compare_dicts

``compare_dicts``
-----------------

.. versionadded:: 2017.7.0

Compare two dictionaries and return a dictionary with the changes.

Example:

.. code-block:: jinja

  {{ {'a': 'b'} | compare_dicts({'a': 'c'}) }}

Returns:

.. code-block:: python

  {"a": {"new": "c", "old": "b"}}


.. jinja_ref:: is_hex

``is_hex``
----------

.. versionadded:: 2017.7.0

Return ``True`` if the value is hexadecimal.

Example:

.. code-block:: jinja

  {{ '0xabcd' | is_hex }}
  {{ 'xyzt' | is_hex }}

Returns:

.. code-block:: python

  True
  False


.. jinja_ref:: contains_whitespace

``contains_whitespace``
-----------------------

.. versionadded:: 2017.7.0

Return ``True`` if a text contains whitespaces.

Example:

.. code-block:: jinja

  {{ 'abcd' | contains_whitespace }}
  {{ 'ab cd' | contains_whitespace }}

Returns:

.. code-block:: python

  False
  True


.. jinja_ref:: substring_in_list

``substring_in_list``
---------------------

.. versionadded:: 2017.7.0

Return ``True`` if a substring is found in a list of string values.

Example:

.. code-block:: jinja

  {{ 'abcd' | substring_in_list(['this', 'is', 'an abcd example']) }}

Returns:

.. code-block:: python

  True


.. jinja_ref:: check_whitelist_blacklist

``check_whitelist_blacklist``
-----------------------------

.. versionadded:: 2017.7.0

Check a whitelist and/or blacklist to see if the value matches it.

This filter can be used with either a whitelist or a blacklist individually,
or a whitelist and a blacklist can be passed simultaneously.

If whitelist is used alone, value membership is checked against the
whitelist only. If the value is found, the function returns ``True``.
Otherwise, it returns ``False``.

If blacklist is used alone, value membership is checked against the
blacklist only. If the value is found, the function returns ``False``.
Otherwise, it returns ``True``.

If both a whitelist and a blacklist are provided, value membership in the
blacklist will be examined first. If the value is not found in the blacklist,
then the whitelist is checked. If the value isn't found in the whitelist,
the function returns ``False``.

Whitelist Example:

.. code-block:: jinja

    {{ 5 | check_whitelist_blacklist(whitelist=[5, 6, 7]) }}

Returns:

.. code-block:: python

    True

Blacklist Example:

.. code-block:: jinja

    {{ 5 | check_whitelist_blacklist(blacklist=[5, 6, 7]) }}

.. code-block:: python

    False

.. jinja_ref:: date_format

``date_format``
---------------

.. versionadded:: 2017.7.0

Converts unix timestamp into human-readable string.

Example:

.. code-block:: jinja

  {{ 1457456400 | date_format }}
  {{ 1457456400 | date_format('%d.%m.%Y %H:%M') }}

Returns:

.. code-block:: text

  2017-03-08
  08.03.2017 17:00


.. jinja_ref:: to_num

``to_num``
----------

.. versionadded:: 2017.7.0
.. versionadded:: 2018.3.0
    Renamed from ``str_to_num`` to ``to_num``.

Converts a string to its numerical value.

Example:

.. code-block:: jinja

  {{ '5' | to_num }}

Returns:

.. code-block:: python

  5


.. jinja_ref:: to_bytes

``to_bytes``
------------

.. versionadded:: 2017.7.0

Converts string-type object to bytes.

Example:

.. code-block:: jinja

  {{ 'wall of text' | to_bytes }}

.. note::

    This option may have adverse effects when using the default renderer,
    ``jinja|yaml``. This is due to the fact that YAML requires proper handling
    in regard to special characters. Please see the section on :ref:`YAML ASCII
    support <yaml_plain_ascii>` in the :ref:`YAML Idiosyncrasies
    <yaml-idiosyncrasies>` documentation for more information.

.. jinja_ref:: json_decode_list
.. jinja_ref:: json_encode_list

``json_encode_list``
--------------------

.. versionadded:: 2017.7.0
.. versionadded:: 2018.3.0
    Renamed from ``json_decode_list`` to ``json_encode_list``. When you encode
    something you get bytes, and when you decode, you get your locale's
    encoding (usually a ``unicode`` type). This filter was incorrectly-named
    when it was added. ``json_decode_list`` will be supported until the 3003
    release.
.. deprecated:: 2018.3.3,2019.2.0
    The :jinja_ref:`tojson` filter accomplishes what this filter was designed
    to do, making this filter redundant.


Recursively encodes all string elements of the list to bytes.

Example:

.. code-block:: jinja

  {{ [1, 2, 3] | json_encode_list }}

Returns:

.. code-block:: python

  [1, 2, 3]


.. jinja_ref:: json_decode_dict
.. jinja_ref:: json_encode_dict

``json_encode_dict``
--------------------

.. versionadded:: 2017.7.0
.. versionadded:: 2018.3.0
    Renamed from ``json_decode_dict`` to ``json_encode_dict``. When you encode
    something you get bytes, and when you decode, you get your locale's
    encoding (usually a ``unicode`` type). This filter was incorrectly-named
    when it was added. ``json_decode_dict`` will be supported until the 3003
    release.
.. deprecated:: 2018.3.3,2019.2.0
    The :jinja_ref:`tojson` filter accomplishes what this filter was designed
    to do, making this filter redundant.

Recursively encodes all string items in the dictionary to bytes.

Example:

Assuming that ``pillar['foo']`` contains ``{u'a': u'\u0414'}``, and your locale
is ``en_US.UTF-8``:

.. code-block:: jinja

  {{ pillar['foo'] | json_encode_dict }}

Returns:

.. code-block:: python

  {"a": "\xd0\x94"}


.. jinja_ref:: tojson

``tojson``
----------

.. versionadded:: 2018.3.3,2019.2.0

Dumps a data structure to JSON.

This filter was added to provide this functionality to hosts which have a
Jinja release older than version 2.9 installed. If Jinja 2.9 or newer is
installed, then the upstream version of the filter will be used. See the
`upstream docs`__ for more information.

.. __: https://jinja.palletsprojects.com/en/2.11.x/templates/#tojson

.. jinja_ref:: random_hash

``random_hash``
---------------

.. versionadded:: 2017.7.0
.. versionadded:: 2018.3.0
    Renamed from ``rand_str`` to ``random_hash`` to more accurately describe
    what the filter does. ``rand_str`` will be supported to ensure backwards
    compatibility but please use the preferred ``random_hash``.

Generates a random number between 1 and the number passed to the filter, and
then hashes it. The default hash type is the one specified by the minion's
:conf_minion:`hash_type` config option, but an alternate hash type can be
passed to the filter as an argument.

Example:

.. code-block:: jinja

  {% set num_range = 99999999 %}
  {{ num_range | random_hash }}
  {{ num_range | random_hash('sha512') }}

Returns:

.. code-block:: text

  43ec517d68b6edd3015b3edc9a11367b
  d94a45acd81f8e3107d237dbc0d5d195f6a52a0d188bc0284c0763ece1eac9f9496fb6a531a296074c87b3540398dace1222b42e150e67c9301383fde3d66ae5


.. jinja_ref:: random_sample

``random_sample``
-----------------

.. versionadded:: 3005

Returns a given sample size from a list. The ``seed`` parameter can be used to
return a predictable outcome.

Example:

.. code-block:: jinja

  {% set my_list = ["one", "two", "three", "four"] %}
  {{ my_list | random_sample(2) }}

Returns:

.. code-block:: text

  ["four", "one"]


.. jinja_ref:: random_shuffle

``random_shuffle``
------------------

.. versionadded:: 3005

Returns a shuffled copy of an input list. The ``seed`` parameter can be used to
return a predictable outcome.

Example:

.. code-block:: jinja

  {% set my_list = ["one", "two", "three", "four"] %}
  {{ my_list | random_shuffle }}

Returns:

.. code-block:: text

  ["four", "three", "one", "two"]


.. jinja_ref:: set_dict_key_value

``set_dict_key_value``
----------------------

.. versionadded:: 3000

Allows you to set a value in a nested dictionary without having to worry if all the nested keys actually exist.
Missing keys will be automatically created if they do not exist.
The default delimiter for the keys is ':', however, with the `delimiter`-parameter, a different delimiter can be specified.

Examples:

.. code-block:: jinja

Example 1:
  {%- set foo = {} %}
  {{ foo | set_dict_key_value('bar:baz', 42) }}

Example 2:
  {{ {} | set_dict_key_value('bar.baz.qux', 42, delimiter='.') }}

Returns:

.. code-block:: text

Example 1:
  {'bar': {'baz': 42}}

Example 2:
  {'bar': {'baz': {'qux': 42}}}


.. jinja_ref:: append_dict_key_value

``append_dict_key_value``
-------------------------

.. versionadded:: 3000

Allows you to append to a list nested (deep) in a dictionary without having to worry if all the nested keys (or the list itself) actually exist.
Missing keys will automatically be created if they do not exist.
The default delimiter for the keys is ':', however, with the `delimiter`-parameter, a different delimiter can be specified.

Examples:

.. code-block:: jinja

Example 1:
  {%- set foo = {'bar': {'baz': [1, 2]}} %}
  {{ foo | append_dict_key_value('bar:baz', 42) }}

Example 2:
  {%- set foo = {} %}
  {{ foo | append_dict_key_value('bar:baz:qux', 42) }}

Returns:

.. code-block:: text

Example 1:
  {'bar': {'baz': [1, 2, 42]}}

Example 2:
  {'bar': {'baz': {'qux': [42]}}}


.. jinja_ref:: extend_dict_key_value

``extend_dict_key_value``
-------------------------

.. versionadded:: 3000

Allows you to extend a list nested (deep) in a dictionary without having to worry if all the nested keys (or the list itself) actually exist.
Missing keys will automatically be created if they do not exist.
The default delimiter for the keys is ':', however, with the `delimiter`-parameter, a different delimiter can be specified.

Examples:

.. code-block:: jinja

Example 1:
  {%- set foo = {'bar': {'baz': [1, 2]}} %}
  {{ foo | extend_dict_key_value('bar:baz', [42, 42]) }}

Example 2:
  {{ {} | extend_dict_key_value('bar:baz:qux', [42]) }}

Returns:

.. code-block:: text

Example 1:
  {'bar': {'baz': [1, 2, 42, 42]}}

Example 2:
  {'bar': {'baz': {'qux': [42]}}}


.. jinja_ref:: update_dict_key_value

``update_dict_key_value``
-------------------------

.. versionadded:: 3000

Allows you to update a dictionary nested (deep) in another dictionary without having to worry if all the nested keys actually exist.
Missing keys will automatically be created if they do not exist.
The default delimiter for the keys is ':', however, with the `delimiter`-parameter, a different delimiter can be specified.

Examples:

.. code-block:: jinja

Example 1:
  {%- set foo = {'bar': {'baz': {'qux': 1}}} %}
  {{ foo | update_dict_key_value('bar:baz', {'quux': 3}) }}

Example 2:
  {{ {} | update_dict_key_value('bar:baz:qux', {'quux': 3}) }}

.. code-block:: text

Example 1:
  {'bar': {'baz': {'qux': 1, 'quux': 3}}}

Example 2:
  {'bar': {'baz': {'qux': {'quux': 3}}}}


.. jinja_ref:: md5

``md5``
-------

.. versionadded:: 2017.7.0

Return the md5 digest of a string.

Example:

.. code-block:: jinja

  {{ 'random' | md5 }}

Returns:

.. code-block:: text

  7ddf32e17a6ac5ce04a8ecbf782ca509


.. jinja_ref:: sha256

``sha256``
----------

.. versionadded:: 2017.7.0

Return the sha256 digest of a string.

Example:

.. code-block:: jinja

  {{ 'random' | sha256 }}

Returns:

.. code-block:: text

  a441b15fe9a3cf56661190a0b93b9dec7d04127288cc87250967cf3b52894d11


.. jinja_ref:: sha512

``sha512``
----------

.. versionadded:: 2017.7.0

Return the sha512 digest of a string.

Example:

.. code-block:: jinja

  {{ 'random' | sha512 }}

Returns:

.. code-block:: text

  811a90e1c8e86c7b4c0eef5b2c0bf0ec1b19c4b1b5a242e6455be93787cb473cb7bc9b0fdeb960d00d5c6881c2094dd63c5c900ce9057255e2a4e271fc25fef1


.. jinja_ref:: base64_encode

``base64_encode``
-----------------

.. versionadded:: 2017.7.0

Encode a string as base64.

Example:

.. code-block:: jinja

  {{ 'random' | base64_encode }}

Returns:

.. code-block:: text

  cmFuZG9t


.. jinja_ref:: base64_decode

``base64_decode``
-----------------

.. versionadded:: 2017.7.0

Decode a base64-encoded string.

.. code-block:: jinja

  {{ 'Z2V0IHNhbHRlZA==' | base64_decode }}

Returns:

.. code-block:: text

  get salted


.. jinja_ref:: hmac

``hmac``
--------

.. versionadded:: 2017.7.0

Verify a challenging hmac signature against a string / shared-secret. Returns
a boolean value.

Example:

.. code-block:: jinja

  {{ 'get salted' | hmac('shared secret', 'eBWf9bstXg+NiP5AOwppB5HMvZiYMPzEM9W5YMm/AmQ=') }}

Returns:

.. code-block:: python

  True


.. jinja_ref:: http_query

``http_query``
--------------

.. versionadded:: 2017.7.0

Return the HTTP reply object from a URL.

Example:

.. code-block:: jinja

  {{ 'http://jsonplaceholder.typicode.com/posts/1' | http_query }}

Returns:

.. code-block:: pycon

  {
    'body': '{
      "userId": 1,
      "id": 1,
      "title": "sunt aut facere repellat provident occaecati excepturi option reprehenderit",
      "body": "quia et suscipit\\nsuscipit recusandae consequuntur expedita et cum\\nreprehenderit molestiae ut ut quas totam\\nnostrum rerum est autem sunt rem eveniet architecto"
    }'
  }


.. jinja_ref:: traverse

``traverse``
------------

.. versionadded:: 2018.3.3

Traverse a dict or list using a colon-delimited target string.
The target 'foo:bar:0' will return data['foo']['bar'][0] if this value exists,
and will otherwise return the provided default value.

Example:

.. code-block:: jinja

  {{ {'a1': {'b1': {'c1': 'foo'}}, 'a2': 'bar'} | traverse('a1:b1', 'default') }}

Returns:

.. code-block:: python

  {"c1": "foo"}

.. code-block:: jinja

  {{ {'a1': {'b1': {'c1': 'foo'}}, 'a2': 'bar'} | traverse('a2:b2', 'default') }}

Returns:

.. code-block:: python

  "default"


.. jinja_ref:: json_query

``json_query``
--------------

.. versionadded:: 3000

A port of Ansible ``json_query`` Jinja filter to make queries against JSON data using `JMESPath language`_.
Could be used to filter ``pillar`` data, ``yaml`` maps, and together with :jinja_ref:`http_query`.
Depends on the `jmespath`_ Python module.

Examples:

.. code-block:: jinja

  Example 1: {{ [1, 2, 3, 4, [5, 6]] | json_query('[]') }}

  Example 2: {{
  {"machines": [
    {"name": "a", "state": "running"},
    {"name": "b", "state": "stopped"},
    {"name": "c", "state": "running"}
  ]} | json_query("machines[?state=='running'].name") }}

  Example 3: {{
  {"services": [
    {"name": "http", "host": "1.2.3.4", "port": 80},
    {"name": "smtp", "host": "1.2.3.5", "port": 25},
    {"name": "ssh",  "host": "1.2.3.6", "port": 22},
  ]} | json_query("services[].port") }}

Returns:

.. code-block:: text

  Example 1: [1, 2, 3, 4, 5, 6]

  Example 2: ['a', 'c']

  Example 3: [80, 25, 22]

.. _`builtin filters`: https://jinja.palletsprojects.com/en/2.11.x/templates/#builtin-filters
.. _`timelib`: https://github.com/pediapress/timelib/
.. _`JMESPath language`: https://jmespath.org/
.. _`jmespath`: https://github.com/jmespath/jmespath.py


.. jinja_ref:: to_entries

``to_entries``
--------------

.. versionadded:: 3007.0

A port of the ``to_entries`` function from ``jq``. This function converts between an object and an array of key-value
pairs. If ``to_entries`` is passed an object, then for each ``k: v`` entry in the input, the output array includes
``{"key": k, "value": v}``. The ``from_entries`` function performs the opposite conversion. ``from_entries`` accepts
"key", "Key", "name", "Name", "value", and "Value" as keys.

Example:

.. code-block:: jinja

  {{ {"a": 1, "b": 2} | to_entries }}

Returns:

.. code-block:: text

  [{"key":"a", "value":1}, {"key":"b", "value":2}]


.. jinja_ref:: from_entries

``from_entries``
----------------

.. versionadded:: 3007.0

A port of the ``from_entries`` function from ``jq``. This function converts between an array of key-value pairs and an
object. If ``from_entries`` is passed an object, then the input is expected to be an array of dictionaries in the format
of ``{"key": k, "value": v}``. The output will be be key-value pairs ``k: v``. ``from_entries`` accepts "key", "Key",
"name", "Name", "value", and "Value" as keys.

Example:

.. code-block:: jinja

  {{ [{"key":"a", "value":1}, {"key":"b", "value":2}] | from_entries }}

Returns:

.. code-block:: text

  {"a": 1, "b": 2}


.. jinja_ref:: to_snake_case

``to_snake_case``
-----------------

.. versionadded:: 3000

Converts a string from camelCase (or CamelCase) to snake_case.

.. code-block:: jinja

  Example: {{ camelsWillLoveThis | to_snake_case }}

Returns:

.. code-block:: text

  Example: camels_will_love_this


.. jinja_ref:: to_camelcase

``to_camelcase``
----------------

.. versionadded:: 3000

Converts a string from snake_case to camelCase (or UpperCamelCase if so indicated).

.. code-block:: jinja

  Example 1: {{ snake_case_for_the_win | to_camelcase }}

  Example 2: {{ snake_case_for_the_win | to_camelcase(uppercamel=True) }}

Returns:

.. code-block:: text

  Example 1: snakeCaseForTheWin
  Example 2: SnakeCaseForTheWin


.. jinja_ref:: human_to_bytes

``human_to_bytes``
------------------

.. versionadded:: 3005

Given a human-readable byte string (e.g. 2G, 30MB, 64KiB), return the number of bytes.
Will return 0 if the argument has unexpected form.

.. code-block:: jinja

  Example 1: {{ "32GB" | human_to_bytes }}

  Example 2: {{ "32GB" | human_to_bytes(handle_metric=True) }}

  Example 3: {{ "32" | human_to_bytes(default_unit="GiB") }}

Returns:

.. code-block:: text

  Example 1: 34359738368
  Example 2: 32000000000
  Example 3: 34359738368

Networking Filters
------------------

The following networking-related filters are supported:


.. jinja_ref:: is_ip

``is_ip``
---------

.. versionadded:: 2017.7.0

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



.. jinja_ref:: is_ipv4

``is_ipv4``
-----------

.. versionadded:: 2017.7.0

Returns if a string is a valid IPv4 address. Supports the same options
as ``is_ip``.

.. code-block:: jinja

  {{ '192.168.0.1' | is_ipv4 }}


.. jinja_ref:: is_ipv6

``is_ipv6``
-----------

.. versionadded:: 2017.7.0

Returns if a string is a valid IPv6 address. Supports the same options
as ``is_ip``.

.. code-block:: jinja

  {{ 'fe80::' | is_ipv6 }}


.. jinja_ref:: ipaddr

``ipaddr``
----------

.. versionadded:: 2017.7.0

From a list, returns only valid IP entries. Supports the same options
as ``is_ip``. The list can contains also IP interfaces/networks.

Example:

.. code-block:: jinja

  {{ ['192.168.0.1', 'foo', 'bar', 'fe80::'] | ipaddr }}

Returns:

.. code-block:: python

  ["192.168.0.1", "fe80::"]


.. jinja_ref:: ipv4

``ipv4``
--------

.. versionadded:: 2017.7.0

From a list, returns only valid IPv4 entries. Supports the same options
as ``is_ip``. The list can contains also IP interfaces/networks.

Example:

.. code-block:: jinja

  {{ ['192.168.0.1', 'foo', 'bar', 'fe80::'] | ipv4 }}

Returns:

.. code-block:: python

  ["192.168.0.1"]


.. jinja_ref:: ipv6

``ipv6``
--------

.. versionadded:: 2017.7.0

From a list, returns only valid IPv6 entries. Supports the same options
as ``is_ip``. The list can contains also IP interfaces/networks.

Example:

.. code-block:: jinja

  {{ ['192.168.0.1', 'foo', 'bar', 'fe80::'] | ipv6 }}

Returns:

.. code-block:: python

  ["fe80::"]


.. jinja_ref:: ipwrap

``ipwrap``
----------

.. versionadded:: 3006.0

From a string, list, or tuple, returns any IPv6 addresses wrapped in square brackets([])

Example:

.. code-block:: jinja

  {{ ['192.0.2.1', 'foo', 'bar', 'fe80::', '2001:db8::1/64'] | ipwrap }}

Returns:

.. code-block:: python

  ["192.0.2.1", "foo", "bar", "[fe80::]", "[2001:db8::1]/64"]


.. jinja_ref:: network_hosts

``network_hosts``
-----------------

.. versionadded:: 2017.7.0

Return the list of hosts within a networks. This utility works for both IPv4 and IPv6.

.. note::

    When running this command with a large IPv6 network, the command will
    take a long time to gather all of the hosts.

Example:

.. code-block:: jinja

  {{ '192.168.0.1/30' | network_hosts }}

Returns:

.. code-block:: python

  ["192.168.0.1", "192.168.0.2"]


.. jinja_ref:: network_size

``network_size``
----------------

.. versionadded:: 2017.7.0

Return the size of the network. This utility works for both IPv4 and IPv6.

Example:

.. code-block:: jinja

  {{ '192.168.0.1/8' | network_size }}

Returns:

.. code-block:: python

  16777216


.. jinja_ref:: gen_mac

``gen_mac``
-----------

.. versionadded:: 2017.7.0

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


.. jinja_ref:: mac_str_to_bytes

``mac_str_to_bytes``
--------------------

.. versionadded:: 2017.7.0

Converts a string representing a valid MAC address to bytes.

Example:

.. code-block:: jinja

  {{ '00:11:22:33:44:55' | mac_str_to_bytes }}

.. note::

    This option may have adverse effects when using the default renderer,
    ``jinja|yaml``. This is due to the fact that YAML requires proper handling
    in regard to special characters. Please see the section on :ref:`YAML ASCII
    support <yaml_plain_ascii>` in the :ref:`YAML Idiosyncrasies
    <yaml-idiosyncrasies>` documentation for more information.

.. jinja_ref:: dns_check

``dns_check``
-------------

.. versionadded:: 2017.7.0

Return the ip resolved by dns, but do not exit on failure, only raise an
exception. Obeys system preference for IPv4/6 address resolution.

Example:

.. code-block:: jinja

  {{ 'www.google.com' | dns_check(port=443) }}

Returns:

.. code-block:: text

  '172.217.3.196'

File filters
------------

.. jinja_ref:: is_text_file

``is_text_file``
----------------

.. versionadded:: 2017.7.0

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


.. jinja_ref:: is_binary_file

``is_binary_file``
------------------

.. versionadded:: 2017.7.0

Return if a file is binary.

Detects if the file is a binary, returns bool. Returns True if the file is
a bin, False if the file is not and None if the file is not available.

Example:

.. code-block:: jinja

  {{ '/etc/salt/master' | is_binary_file }}

Returns:

.. code-block:: python

  False


.. jinja_ref:: is_empty_file

``is_empty_file``
-----------------

.. versionadded:: 2017.7.0

Return if a file is empty.

Example:

.. code-block:: jinja

  {{ '/etc/salt/master' | is_empty_file }}

Returns:

.. code-block:: python

  False


.. jinja_ref:: file_hashsum

``file_hashsum``
----------------

.. versionadded:: 2017.7.0

Return the hashsum of a file.

Example:

.. code-block:: jinja

  {{ '/etc/salt/master' | file_hashsum }}

Returns:

.. code-block:: text

  02d4ef135514934759634f10079653252c7ad594ea97bd385480c532bca0fdda


.. jinja_ref:: list_files

``list_files``
--------------

.. versionadded:: 2017.7.0

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


.. jinja_ref:: path_join

``path_join``
-------------

.. versionadded:: 2017.7.0

Joins absolute paths.

Example:

.. code-block:: jinja

  {{ '/etc/salt/' | path_join('pillar', 'device1.sls') }}

Returns:

.. code-block:: text

  /etc/salt/pillar/device1.sls


.. jinja_ref:: which

``which``
---------

.. versionadded:: 2017.7.0

Python clone of /usr/bin/which.

Example:

.. code-block:: jinja

  {{ 'salt-master' | which }}

Returns:

.. code-block:: text

  /usr/local/salt/virtualenv/bin/salt-master


Tests
=====

Saltstack extends `builtin tests`_ with these custom tests:

.. _`builtin tests`: https://jinja.palletsprojects.com/en/2.11.x/templates/#builtin-tests

.. jinja_ref:: equalto

``equalto``
-----------

Tests the equality between two values.

Can be used in an ``if`` statement directly:

.. code-block:: jinja

    {% if 1 is equalto(1) %}
        < statements >
    {% endif %}

If clause evaluates to ``True``

or with the ``selectattr`` filter:

.. code-block:: jinja

    {{ [{'value': 1}, {'value': 2} , {'value': 3}] | selectattr('value', 'equalto', 3) | list }}

Returns:

.. code-block:: python

    [{"value": 3}]

.. jinja_ref:: match

``match``
---------

Tests that a string matches the regex passed as an argument.

Can be used in a ``if`` statement directly:

.. code-block:: jinja

    {% if 'a' is match('[a-b]') %}
        < statements >
    {% endif %}

If clause evaluates to ``True``

or with the ``selectattr`` filter:

.. code-block:: jinja

    {{ [{'value': 'a'}, {'value': 'b'}, {'value': 'c'}] | selectattr('value', 'match', '[b-e]') | list }}

Returns:

.. code-block:: python

    [{"value": "b"}, {"value": "c"}]


Test supports additional optional arguments: ``ignorecase``, ``multiline``


Escape filters
--------------

.. jinja_ref:: regex_escape

``regex_escape``
----------------

.. versionadded:: 2017.7.0

Allows escaping of strings so they can be interpreted literally by another function.

Example:

.. code-block:: jinja

  regex_escape = {{ 'https://example.com?foo=bar%20baz' | regex_escape }}

will be rendered as:

.. code-block:: text

  regex_escape = https\:\/\/example\.com\?foo\=bar\%20baz

Set Theory Filters
------------------

.. jinja_ref:: unique

``unique``
----------

.. versionadded:: 2017.7.0

Performs set math using Jinja filters.

Example:

.. code-block:: jinja

  unique = {{ ['foo', 'foo', 'bar'] | unique }}

will be rendered as:

.. code-block:: text

  unique = ['foo', 'bar']

Global Functions
================

Salt Project extends `builtin global functions`_ with these custom global functions:

.. jinja_ref:: ifelse

``ifelse``
----------

Evaluate each pair of arguments up to the last one as a (matcher, value)
tuple, returning ``value`` if matched.  If none match, returns the last
argument.

The ``ifelse`` function is like a multi-level if-else statement. It was
inspired by CFEngine's ``ifelse`` function which in turn was inspired by
Oracle's ``DECODE`` function. It must have an odd number of arguments (from
1 to N). The last argument is the default value, like the ``else`` clause in
standard programming languages. Every pair of arguments before the last one
are evaluated as a pair. If the first one evaluates true then the second one
is returned, as if you had used the first one in a compound match
expression. Boolean values can also be used as the first item in a pair, as it
will be translated to a match that will always match ("*") or never match
("SALT_IFELSE_MATCH_NOTHING") a target system.

This is essentially another way to express the ``match.filter_by`` functionality
in way that's familiar to CFEngine or Oracle users. Consider using
``match.filter_by`` unless this function fits your workflow.

.. code-block:: jinja

    {{ ifelse('foo*', 'fooval', 'bar*', 'barval', 'defaultval', minion_id='bar03') }}

.. _`builtin global functions`: https://jinja.palletsprojects.com/en/2.11.x/templates/#builtin-globals

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

    Macros and variables can be shared across templates. They should not start
    with one or more underscores, and should be managed by one of the
    following tags: `macro`, `set`, `load_yaml`, `load_json`, `import_yaml` and
    `import_json`.

.. jinja_ref:: escaping-jinja

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

.. _`Escaping`: https://jinja.palletsprojects.com/en/2.11.x/templates/#escaping

.. jinja_ref:: calling-salt-functions

Calling Salt Functions
======================

The Jinja renderer provides a shorthand lookup syntax for the ``salt``
dictionary of :term:`execution function <Execution Function>`.

.. versionadded:: 2014.7.0

.. code-block:: jinja

    # The following two function calls are mostly equivalent,
    # but the first style should be preferred to avoid edge cases.
    {{ salt['cmd.run']('whoami') }}
    {{ salt.cmd.run('whoami') }}

.. jinja_ref:: debugging

Debugging
=========

The ``show_full_context`` function can be used to output all variables present
in the current Jinja context.

.. versionadded:: 2014.7.0

.. code-block:: jinja

    Context is: {{ show_full_context()|yaml(False) }}

.. jinja_ref:: logs

Logs
----

.. versionadded:: 2017.7.0

Yes, in Salt, one is able to debug a complex Jinja template using the logs.
For example, making the call:

.. code-block:: jinja

    {%- do salt['log.error']('testing jinja logging') -%}

Will insert the following message in the minion logs:

.. code-block:: text

    2017-02-01 01:24:40,728 [salt.module.logmod][ERROR   ][3779] testing jinja logging

.. jinja_ref:: custom-execution-modules

Profiling
=========

.. versionadded:: 3002

When working with a very large codebase, it becomes increasingly imperative to
trace inefficiencies with state and pillar render times. The `profile` Jinja
block enables the user to get finely detailed information on the most expensive
areas in the codebase.

Profiling blocks
----------------

Any block of Jinja code can be wrapped in a ``profile`` block.  The syntax for
a profile block is ``{% profile as '<name>' %}<jinja code>{% endprofile %}``,
where ``<name>`` can be any string.  The ``<name>`` token will appear in the
log at the ``profile`` level along with the render time of the block.

.. code-block:: sls

    # /srv/salt/example.sls
    {%- profile as 'local data' %}
      {%- set local_data = {'counter': 0} %}
      {%- for i in range(313377) %}
        {%- do local_data.update({'counter': i}) %}
      {%- endfor %}
    {%- endprofile %}

    test:
      cmd.run:
        - name: |-
            printf 'data: %s' '{{ local_data['counter'] }}'

The ``profile`` block in the ``example.sls`` state will emit the following log
statement:

.. code-block:: console

    # salt-call --local -l profile state.apply example
    [...]
    [PROFILE ] Time (in seconds) to render profile block 'local data': 0.9385035037994385
    [...]

Profiling imports
-----------------

Using the same logic as the ``profile`` block, the ``import_yaml``,
``import_json``, and ``import_text`` blocks will emit similar statements at the
``profile`` log level.

.. code-block:: sls

    # /srv/salt/data.sls
    {%- set values = {'counter': 0} %}
    {%- for i in range(524288) %}
      {%- do values.update({'counter': i}) %}
    {%- endfor %}

    data: {{ values['counter'] }}

.. code-block:: sls

    # /srv/salt/example.sls
    {%- import_yaml 'data.sls' as imported %}

    test:
      cmd.run:
        - name: |-
            printf 'data: %s' '{{ imported['data'] }}'

For ``import_*`` blocks, the ``profile`` log statement has the following form:

.. code-block:: console

    # salt-call --local -l profile state.apply example
    [...]
    [PROFILE ] Time (in seconds) to render import_yaml 'data.sls': 1.5500736236572266
    [...]

Python Methods
==============

A powerful feature of Jinja that is only hinted at in the official Jinja
documentation is that you can use the native Python methods of the
variable type. Here is the Python documentation for `string methods`_.

.. code-block:: jinja

  {% set hostname, domain = grains.id.partition('.')[::2] %}{{ hostname }}

.. code-block:: jinja

  {% set strings = grains.id.split('-') %}{{ strings[0] }}

.. _`string methods`: https://docs.python.org/3/library/stdtypes.html#string-methods

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

.. jinja_ref:: custom-jinja-filters

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

    {{ salt['my_filters.my_jinja_filter'](my_variable) }}

The greatest benefit is that you are able to access thousands of existing functions, e.g.:

- get the DNS AAAA records for a specific address using the :mod:`dnsutil <salt.modules.dnsutil>`:

  .. code-block:: jinja

    {{ salt['dnsutil.AAAA']('www.google.com') }}

- retrieve a specific field value from a :mod:`Redis <salt.modules.modredis>` hash:

  .. code-block:: jinja

    {{ salt['redis.hget']('foo_hash', 'bar_field') }}

- get the routes to ``0.0.0.0/0`` using the :mod:`NAPALM route <salt.modules.napalm_route>`:

  .. code-block:: jinja

    {{ salt['route.show']('0.0.0.0/0') }}
