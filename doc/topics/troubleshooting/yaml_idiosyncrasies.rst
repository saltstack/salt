===================
YAML Idiosyncrasies
===================

One of Salt's strength, the use of existing serialization systems for
representing sls data, can also backfire. YAML is a general purpose system
and there are a number of things that would seem to make sense in an sls
file that cause YAML issues. It is wise to be aware of these issues, while
reports or running into them are generally rare they can still crop up at
unexpected times.

Spaces vs Tabs
==============

Yaml uses spaces, period, do not use tabs in your sls files! If strange
errors are coming up in rendering sls files, make sure to check that
no tabs have crept in!

Indentation
===========
The suggested syntax for Yaml files is to use 2 spaces for indentation,
but Yaml will follow whatever indentation system that the individual file
uses. Generally 2 space indentation works very well for sls files given
the fact that the represented data is uniform and not deeply nested.

Nested Dicts (key-value)
------------------------

When dicts are more deeply nested they no longer follow the same indentation
logic. This is rarely something that comes up in Salt, since deeply nested
options like these are discouraged when making state modules, but some do
exist. A good example is the context and default options in the file.managed
state:

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

Notice that the spacing used is 2 spaces, and that when defining the context
and defaults options there is a 4 space indent. If only a 2 space indent is
used then the information will not be correctly loaded. If using double spacing
is not desirable, then a deeply nested dict can be declared with curly braces:

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
          custom_var: "default value"
          other_var: 123 }

Integers are Parsed as Integers
===============================

When passing integers into an sls file, they are passed as integers. This means
that if a state accepts a string value and an integer is passed, that an
integer will be sent. The solution here is to send the integer as a string.

This is best explained when setting the mode for a file:

.. code-block:: yaml

    /etc/vimrc:
      file:
        - managed
        - source: salt://edit/vimrc
        - user: root
        - group: root
        - mode: 644

Salt manages this well, since the mode is passed as 644, but if the mode is
zero padded as 0644, then it is read by Yaml as an integer and evaluated as
a hexadecimal value, 0644 becomes 420. Therefore, if the file mode is
preceded by a 0 then it needs to be passed as a string:

.. code-block:: yaml

    /etc/vimrc:
      file:
        - managed
        - source: salt://edit/vimrc
        - user: root
        - group: root
        - mode: '0644'
