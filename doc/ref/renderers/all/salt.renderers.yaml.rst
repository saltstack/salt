===================
salt.renderers.yaml
===================

Understanding YAML
==================

The default renderer for SLS files is the YAML renderer. YAML is a
markup language with many powerful features. However, Salt uses
a small subset of YAML that maps over very commonly used data structures,
like lists and dictionaries. It is the job of the YAML renderer to take
the YAML data structure and compile it into a Python data structure for
use by Salt.

Though YAML syntax may seem daunting and terse at first, there are only
three very simple rules to remember when writing YAML for SLS files.

Rule One: Indentation
---------------------

YAML uses a fixed indentation scheme to represent relationships between
data layers. Salt requires that the indentation for each level consists
of exactly two spaces. Do not use tabs.


Rule Two: Colons
----------------

Python dictionaries are, of course, simply key-value pairs. Users from other
languages may recognize this data type as hashes or associative arrays.

Dictionary keys are represented in YAML as strings terminated by a trailing colon.
Values are represented by either a string following the colon, separated by a space:

.. code-block:: yaml

    my_key: my_value

In Python, the above maps to:

.. code-block:: python

    {'my_key': 'my_value'}

Dictionaries can be nested:

.. code-block:: yaml

    first_level_dict_key:
      second_level_dict_key: value_in_second_level_dict

And in Python:

.. code-block:: python

    {'first_level_dict_key': {'second_level_dict_key': 'value_in_second_level_dict' } }

Rule Three: Dashes
------------------

To represent lists of items, a single dash followed by a space is used. Multiple
items are a part of the same list as a function of their having the same level of indentation.

.. code-block:: yaml

    - list_value_one
    - list_value_two
    - list_value_three

Lists can be the value of a key-value pair. This is quite common in Salt:

.. code-block:: yaml

    my_dictionary:
      - list_value_one
      - list_value_two
      - list_value_three

Reference
---------

.. automodule:: salt.renderers.yaml
    :members: