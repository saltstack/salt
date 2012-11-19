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

Nested Dicts (key=value)
------------------------

When `dicts`_: are more deeply nested, they no longer follow the same
indentation logic. This is rarely something that comes up in Salt,
since deeply nested options like these are discouraged when making State
modules, but some do exist. A good example is the context and default options
in the :doc:`file.managed</ref/states/all/salt.states.file>` state:

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
used then the information will not be loaded correctly. If using double spacing
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
          custom_var: "default value",
          other_var: 123 }

.. _`dicts`: http://docs.python.org/library/stdtypes.html#dict

Integers are Parsed as Integers
===============================

NOTE: This has been fixed in salt 0.10.0, as of this release passing an
integer that is preceded by a 0 will be correctly parsed

When passing `integers`_ into an SLS file, they are passed as integers. This means
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
zero padded as 0644, then it is read by YAML as an integer and evaluated as
an octal value, 0644 becomes 420. Therefore, if the file mode is
preceded by a 0 then it needs to be passed as a string:

.. code-block:: yaml

    /etc/vimrc:
      file:
        - managed
        - source: salt://edit/vimrc
        - user: root
        - group: root
        - mode: '0644'
        
.. _`integers`: http://docs.python.org/library/functions.html#int

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


    
List of useable `Unicode characters`_  will help you to identify correct numbers.

.. _`Unicode characters`: http://en.wikipedia.org/wiki/List_of_Unicode_characters


Python can also be used to discover the Unicode number for a character:

.. code-block:: python

    repr(u"Text with wrong characters i need to figure out")

This shell command can find wrong characters in your SLS files:

.. code-block:: bash

    find . -name '*.sls'  -exec  grep --color='auto' -P -n '[^\x00-\x7F]' \{} \;

