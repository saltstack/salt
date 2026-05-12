.. meta::
   :description: YAML is a markup language with powerful features. YAML syntax may seem daunting, but there are only 3 simple rules to remember for writing YAML for SLS files.
   :keywords: yaml, what is yaml, how to use yaml

.. _yaml:

==============================
What is YAML and How To Use It
==============================

The default renderer for SLS files is the YAML renderer.

What is YAML
------------

What does YAML stand for? It's an acronym for *YAML Ain't Markup Language*.

`The Official YAML Website <https://yaml.org>`_ defines YAML as:

  *...a human friendly data serialization*
  *standard for all programming languages.*

However, Salt uses a small subset of YAML that maps over very commonly used data
structures, like lists and dictionaries. It is the job of the YAML renderer to
take the YAML data structure and compile it into a Python data structure for use
by Salt.

Defining YAML
-------------

Though YAML syntax may seem daunting and terse at first, there are only
three very simple rules to remember when writing YAML for SLS files.

Rule One: Indentation
+++++++++++++++++++++

YAML uses a fixed indentation scheme to represent relationships between
data layers. Salt requires that the indentation for each level consists
of exactly two spaces. Do not use tabs.


Rule Two: Colons
++++++++++++++++

Python dictionaries are, of course, simply key-value pairs. Users from other
languages may recognize this data type as hashes or associative arrays.

Dictionary keys are represented in YAML as strings terminated by a trailing
colon. Values are represented by either a string following the colon,
separated by a space:

.. code-block:: yaml

    my_key: my_value

In Python, the above maps to:

.. code-block:: python

    {"my_key": "my_value"}

Alternatively, a value can be associated with a key through indentation.

.. code-block:: yaml

    my_key:
      my_value

.. note::

    The above syntax is valid YAML but is uncommon in SLS files because most often,
    the value for a key is not singular but instead is a *list* of values.

In Python, the above maps to:

.. code-block:: python

    {"my_key": "my_value"}

Dictionaries can be nested:

.. code-block:: yaml

    first_level_dict_key:
      second_level_dict_key: value_in_second_level_dict

And in Python:

.. code-block:: python

    {"first_level_dict_key": {"second_level_dict_key": "value_in_second_level_dict"}}

Rule Three: Dashes
++++++++++++++++++

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

In Python, the above maps to:

.. code-block:: python

    {"my_dictionary": ["list_value_one", "list_value_two", "list_value_three"]}

Learning more about YAML
------------------------

One easy way to learn more about how YAML gets rendered into Python data structures is
to use an online YAML parser to see the Python output.

Here are some excellent links for experimenting with and referencing YAML:

* `Online YAML Parser <https://yaml-online-parser.appspot.com/>`_: Convert YAML
  to JSON or Python data structures.
* `The Official YAML Specification <https://yaml.org/spec/1.2/spec.html>`_
* `The Wikipedia page for YAML <https://en.wikipedia.org/wiki/YAML>`_

Templating
----------
Jinja statements and expressions are allowed by default in SLS files. See
:ref:`Understanding Jinja <understanding-jinja>`.
