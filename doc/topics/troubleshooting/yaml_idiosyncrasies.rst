.. _yaml-idiosyncrasies:

===================
YAML Idiosyncrasies
===================

One of Salt's strengths, the use of existing serialization systems for
representing SLS data, can also backfire. `YAML`_ is a general purpose system
and there are a number of things that would seem to make sense in an sls
file that cause YAML issues. It is wise to be aware of these issues. While
reports or running into them are generally rare they can still crop up at
unexpected times.

.. _`YAML`: http://yaml.org/spec/1.1/

Spaces vs Tabs
==============

`YAML uses spaces`_, period. Do not use tabs in your SLS files! If strange
errors are coming up in rendering SLS files, make sure to check that
no tabs have crept in! In Vim, after enabling search highlighting
with: ``:set hlsearch``,  you can check with the following key sequence in
normal mode(you can hit `ESC` twice to be sure): ``/``, `Ctrl-v`, `Tab`, then
hit `Enter`. Also, you can convert tabs to 2 spaces by these commands in Vim:
``:set tabstop=2 expandtab`` and then ``:retab``.

.. _`YAML uses spaces`: http://yaml.org/spec/1.1/#id871998

Indentation
===========
The suggested syntax for YAML files is to use 2 spaces for indentation,
but YAML will follow whatever indentation system that the individual file
uses. Indentation of two spaces works very well for SLS files given the
fact that the data is uniform and not deeply nested.

.. _nested-dict-indentation:

Nested Dictionaries
-------------------

When :ref:`dicts <python2:typesmapping>` are nested within other data
structures (particularly lists), the indentation logic sometimes changes.
Examples of where this might happen include ``context`` and ``default`` options
from the :mod:`file.managed <salt.states.file>` state:

.. code-block:: yaml

    /etc/http/conf/http.conf:
      file:
        - managed
        - source: salt://apache/http.conf
        - user: root
        - group: root
        - mode: 644
        - template: jinja
        - context:
            custom_var: "override"
        - defaults:
            custom_var: "default value"
            other_var: 123

Notice that while the indentation is two spaces per level, for the values under
the ``context`` and ``defaults`` options there is a four-space indent. If only
two spaces are used to indent, then those keys will be considered part of the
same dictionary that contains the ``context`` key, and so the data will not be
loaded correctly. If using a double indent is not desirable, then a
deeply-nested dict can be declared with curly braces:

.. code-block:: yaml

    /etc/http/conf/http.conf:
      file:
        - managed
        - source: salt://apache/http.conf
        - user: root
        - group: root
        - mode: 644
        - template: jinja
        - context: {
          custom_var: "override" }
        - defaults: {
          custom_var: "default value",
          other_var: 123 }

Here is a more concrete example of how YAML actually handles these
indentations, using the Python interpreter on the command line:

.. code-block:: python

    >>> import yaml
    >>> yaml.safe_load('''mystate:
    ...   file.managed:
    ...     - context:
    ...         some: var''')
    {'mystate': {'file.managed': [{'context': {'some': 'var'}}]}}
    >>> yaml.safe_load('''mystate:
    ...   file.managed:
    ...     - context:
    ...       some: var''')
    {'mystate': {'file.managed': [{'some': 'var', 'context': None}]}}

Note that in the second example, ``some`` is added as another key in the same
dictionary, whereas in the first example, it's the start of a new dictionary.
That's the distinction. ``context`` is a common example because it is a keyword
arg for many functions, and should contain a dictionary.


True/False, Yes/No, On/Off
==========================

PyYAML will load these values as boolean ``True`` or ``False``. Un-capitalized
versions will also be loaded as booleans (``true``, ``false``, ``yes``, ``no``,
``on``, and ``off``). This can be especially problematic when constructing
Pillar data. Make sure that your Pillars which need to use the string versions
of these values are enclosed in quotes.  Pillars will be parsed twice by salt,
so you'll need to wrap your values in multiple quotes, for example '"false"'.

The '%' Sign
============

The `%` symbol has a special meaning in YAML, it needs to be passed as a
string literal:

.. code-block:: yaml

    cheese:
      ssh_auth.present:
        - user: tbortels
        - source: salt://ssh_keys/chease.pub
        - config: '%h/.ssh/authorized_keys'

Time Expressions
================

PyYAML will load a time expression as the integer value of that, assuming
``HH:MM``. So for example, ``12:00`` is loaded by PyYAML as ``720``. An
excellent explanation for why can be found here__.

To keep time expressions like this from being loaded as integers, always quote
them.

.. note::
    When using a jinja ``load_yaml`` map, items must be quoted twice. For
    example:

    .. code-block:: yaml

        {% load_yaml as wsus_schedule %}

        FRI_10:
          time: '"23:00"'
          day: 6 - Every Friday
        SAT_10:
          time: '"06:00"'
          day: 7 - Every Saturday
        SAT_20:
          time: '"14:00"'
          day: 7 - Every Saturday
        SAT_30:
          time: '"22:00"'
          day: 7 - Every Saturday
        SUN_10:
          time: '"06:00"'
          day: 1 - Every Sunday
        {% endload %}

.. __: http://stackoverflow.com/a/31007425

YAML does not like "Double Short Decs"
======================================

If I can find a way to make YAML accept "Double Short Decs" then I will, since
I think that double short decs would be awesome. So what is a "Double Short
Dec"? It is when you declare a multiple short decs in one ID. Here is a
standard short dec, it works great:

.. code-block:: yaml

    vim:
      pkg.installed

The short dec means that there are no arguments to pass, so it is not required
to add any arguments, and it can save space.

YAML though, gets upset when declaring multiple short decs, for the record...

THIS DOES NOT WORK:

.. code-block:: yaml

    vim:
      pkg.installed
      user.present

Similarly declaring a short dec in the same ID dec as a standard dec does not
work either...

ALSO DOES NOT WORK:

.. code-block:: yaml

    fred:
      user.present
      ssh_auth.present:
        - name: AAAAB3NzaC...
        - user: fred
        - enc: ssh-dss
        - require:
          - user: fred

The correct way is to define them like this:

.. code-block:: yaml

    vim:
      pkg.installed: []
      user.present: []

    fred:
      user.present: []
      ssh_auth.present:
        - name: AAAAB3NzaC...
        - user: fred
        - enc: ssh-dss
        - require:
          - user: fred


Alternatively,  they can be defined the "old way",  or with multiple
"full decs":

.. code-block:: yaml

    vim:
      pkg:
        - installed
      user:
        - present

    fred:
      user:
        - present
      ssh_auth:
        - present
        - name: AAAAB3NzaC...
        - user: fred
        - enc: ssh-dss
        - require:
          - user: fred

YAML support only plain ASCII
=============================

According to YAML specification, only ASCII characters can be used.

Within double-quotes, special characters may be represented with C-style
escape sequences starting with a backslash ( \\ ).

Examples:

.. code-block:: yaml

    - micro: "\u00b5"
    - copyright: "\u00A9"
    - A: "\x41"
    - alpha: "\u0251"
    - Alef: "\u05d0"



List of usable `Unicode characters`_  will help you to identify correct numbers.

.. _`Unicode characters`: http://en.wikipedia.org/wiki/List_of_Unicode_characters


Python can also be used to discover the Unicode number for a character:

.. code-block:: python

    repr(u"Text with wrong characters i need to figure out")

This shell command can find wrong characters in your SLS files:

.. code-block:: bash

    find . -name '*.sls'  -exec  grep --color='auto' -P -n '[^\x00-\x7F]' \{} \;


Alternatively you can toggle the `yaml_utf8` setting in your master configuration
file. This is still an experimental setting but it should manage the right
encoding conversion in salt after yaml states compilations.

Underscores stripped in Integer Definitions
===========================================

If a definition only includes numbers and underscores, it is parsed by YAML as
an integer and all underscores are stripped.  To ensure the object becomes a
string, it should be surrounded by quotes.  `More information here`_.

.. _`More information here`: http://stackoverflow.com/questions/2723321/snakeyaml-how-to-disable-underscore-stripping-when-parsing

Here's an example:

.. code-block:: python

    >>> import yaml
    >>> yaml.safe_load('2013_05_10')
    20130510
    >>> yaml.safe_load('"2013_05_10"')
    '2013_05_10'

Automatic ``datetime`` conversion
=================================

If there is a value in a YAML file formatted ``2014-01-20 14:23:23`` or
similar, YAML will automatically convert this to a Python ``datetime`` object.
These objects are not msgpack serializable, and so may break core salt
functionality.  If values such as these are needed in a salt YAML file
(specifically a configuration file), they should be formatted with surrounding
strings to force YAML to serialize them as strings:

.. code-block:: python

    >>> import yaml
    >>> yaml.safe_load('2014-01-20 14:23:23')
    datetime.datetime(2014, 1, 20, 14, 23, 23)
    >>> yaml.safe_load('"2014-01-20 14:23:23"')
    '2014-01-20 14:23:23'

Additionally, numbers formatted like ``XXXX-XX-XX`` will also be converted (or
YAML will attempt to convert them, and error out if it doesn't think the date
is a real one).  Thus, for example, if a minion were to have an ID of
``4017-16-20`` the minion would not start because YAML would complain that the
date was out of range.  The workaround is the same, surround the offending
string with quotes:

.. code-block:: python

    >>> import yaml
    >>> yaml.safe_load('4017-16-20')
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "/usr/local/lib/python2.7/site-packages/yaml/__init__.py", line 93, in safe_load
        return load(stream, SafeLoader)
      File "/usr/local/lib/python2.7/site-packages/yaml/__init__.py", line 71, in load
        return loader.get_single_data()
      File "/usr/local/lib/python2.7/site-packages/yaml/constructor.py", line 39, in get_single_data
        return self.construct_document(node)
      File "/usr/local/lib/python2.7/site-packages/yaml/constructor.py", line 43, in construct_document
        data = self.construct_object(node)
      File "/usr/local/lib/python2.7/site-packages/yaml/constructor.py", line 88, in construct_object
        data = constructor(self, node)
      File "/usr/local/lib/python2.7/site-packages/yaml/constructor.py", line 312, in construct_yaml_timestamp
        return datetime.date(year, month, day)
    ValueError: month must be in 1..12
    >>> yaml.safe_load('"4017-16-20"')
    '4017-16-20'


Keys Limited to 1024 Characters
===============================

Simple keys are limited to a single line and cannot be longer that 1024 characters.
This is a limitation from PyYaml, as seen in a comment in `PyYAML's code`_, and
applies to anything parsed by YAML in Salt.

.. _PyYAML's code: http://pyyaml.org/browser/pyyaml/trunk/lib/yaml/scanner.py#L91
