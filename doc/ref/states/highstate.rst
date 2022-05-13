.. _states-highstate:

====================================
Highstate data structure definitions
====================================

The Salt State Tree
===================

A state tree is a collection of ``SLS`` files and directories that live under the directory
specified in :conf_master:`file_roots`.

.. note::

   Directory names or filenames in the state tree cannot contain a period, with the
   exception of the period in the .sls file suffix.

.. _states-highstate-top-file:

Top file
--------

The main state file that instructs minions what environment and modules to use
during state execution.

Configurable via :conf_master:`state_top`.

.. seealso:: :ref:`A detailed description of the top file <states-top>`

.. _include-declaration:

Include declaration
-------------------

Defines a list of :ref:`module-reference` strings to include in this ``SLS``.

Occurs only in the top level of the SLS data structure.

Example:

.. code-block:: yaml

    include:
      - edit.vim
      - http.server

.. _module-reference:

Module reference
----------------

The name of a SLS module defined by a separate SLS file and residing on
the Salt Master. A module named ``edit.vim`` is a reference to the SLS
file ``salt://edit/vim.sls``.

.. _id-declaration:

ID declaration
--------------

Defines an individual :ref:`highstate <running-highstate>` component. Always
references a value of a dictionary containing keys referencing
:ref:`state-declaration` and :ref:`requisite-declaration`. Can be overridden by
a :ref:`name-declaration` or a :ref:`names-declaration`.

Occurs on the top level or under the :ref:`extend-declaration`.

Must be unique across entire state tree. If the same ID declaration is
used twice, only the first one matched will be used. All subsequent
ID declarations with the same name will be ignored.

.. note:: Naming gotchas

    In Salt versions earlier than 0.9.7, ID declarations containing dots would
    result in unpredictable output.

.. _extend-declaration:

Extend declaration
------------------

Extends a :ref:`name-declaration` from an included ``SLS module``. The
keys of the extend declaration always refer to an existing
:ref:`id-declaration` which have been defined in included ``SLS modules``.

Occurs only in the top level and defines a dictionary.

States cannot be extended more than once in a single state run.

Extend declarations are useful for adding-to or overriding parts of a
:ref:`state-declaration` that is defined in another ``SLS`` file. In the
following contrived example, the shown ``mywebsite.sls`` file is ``include``
-ing and ``extend`` -ing the ``apache.sls`` module in order to add a ``watch``
declaration that will restart Apache whenever the Apache configuration file,
``mywebsite`` changes.

.. code-block:: yaml

    include:
      - apache

    extend:
      apache:
        service:
          - watch:
            - file: mywebsite

    mywebsite:
      file.managed:
        - name: /var/www/mysite

.. seealso:: watch_in and require_in

    Sometimes it is more convenient to use the :ref:`watch_in
    <requisites-watch-in>` or :ref:`require_in <requisites-require-in>` syntax
    instead of extending another ``SLS`` file.

    :ref:`State Requisites <requisites>`

.. _state-declaration:

State declaration
-----------------

A list which contains one string defining the :ref:`function-declaration` and
any number of :ref:`function-arg-declaration` dictionaries.

Can, optionally, contain a number of additional components like the
name override components — :ref:`name <name-declaration>` and
:ref:`names <names-declaration>`. Can also contain :ref:`requisite
declarations <requisite-declaration>`.

Occurs under an :ref:`ID-declaration`.

.. _requisite-declaration:

Requisite declaration
---------------------

A list containing :ref:`requisite references <requisite-reference>`.

Used to build the action dependency tree. While Salt states are made to
execute in a deterministic order, this order is managed by requiring
and watching other Salt states.

Occurs as a list component under a :ref:`state-declaration` or as a
key under an :ref:`ID-declaration`.

.. _requisite-reference:

Requisite reference
-------------------

A single key dictionary. The key is the name of the referenced
:ref:`state-declaration` and the value is the ID of the referenced
:ref:`ID-declaration`.

Occurs as a single index in a :ref:`requisite-declaration` list.

.. _function-declaration:

Function declaration
--------------------

The name of the function to call within the state. A state declaration
can contain only a single function declaration.

For example, the following state declaration calls the :mod:`installed
<salt.states.pkg.installed>` function in the ``pkg`` state module:

.. code-block:: yaml

    httpd:
      pkg.installed: []

The function can be declared inline with the state as a shortcut.
The actual data structure is compiled to this form:

.. code-block:: yaml

    httpd:
      pkg:
        - installed

Where the function is a string in the body of the state declaration.
Technically when the function is declared in dot notation the compiler
converts it to be a string in the state declaration list. Note that the
use of the first example more than once in an ID declaration is invalid
yaml.

INVALID:

.. code-block:: yaml

    httpd:
      pkg.installed
      service.running

When passing a function without arguments and another state declaration
within a single ID declaration, then the long or "standard" format
needs to be used since otherwise it does not represent a valid data
structure.

VALID:

.. code-block:: yaml

    httpd:
      pkg.installed: []
      service.running: []

Occurs as the only index in the :ref:`state-declaration` list.

.. _function-arg-declaration:

Function arg declaration
------------------------

A single key dictionary referencing a Python type which is to be passed
to the named :ref:`function-declaration` as a parameter. The type must
be the data type expected by the function.

Occurs under a :ref:`function-declaration`.

For example in the following state declaration ``user``, ``group``, and
``mode`` are passed as arguments to the :mod:`managed
<salt.states.file.managed>` function in the ``file`` state module:

.. code-block:: yaml

    /etc/http/conf/http.conf:
      file.managed:
        - user: root
        - group: root
        - mode: 644

.. _name-declaration:

Name declaration
----------------

Overrides the ``name`` argument of a :ref:`state-declaration`. If
``name`` is not specified the :ref:`ID-declaration` satisfies the
``name`` argument.

The name is always a single key dictionary referencing a string.

Overriding ``name`` is useful for a variety of scenarios.

For example, avoiding clashing ID declarations. The following two state
declarations cannot both have ``/etc/motd`` as the ID declaration:

.. code-block:: yaml

    motd_perms:
      file.managed:
        - name: /etc/motd
        - mode: 644

    motd_quote:
      file.append:
        - name: /etc/motd
        - text: "Of all smells, bread; of all tastes, salt."

Another common reason to override ``name`` is if the ID declaration is long and
needs to be referenced in multiple places. In the example below it is much
easier to specify ``mywebsite`` than to specify
``/etc/apache2/sites-available/mywebsite.com`` multiple times:

.. code-block:: yaml

    mywebsite:
      file.managed:
        - name: /etc/apache2/sites-available/mywebsite.com
        - source: salt://mywebsite.com

    a2ensite mywebsite.com:
      cmd.wait:
        - unless: test -L /etc/apache2/sites-enabled/mywebsite.com
        - watch:
          - file: mywebsite

    apache2:
      service.running:
        - watch:
          - file: mywebsite

.. _names-declaration:

Names declaration
-----------------

Expands the contents of the containing :ref:`state-declaration` into
multiple state declarations, each with its own name.

For example, given the following state declaration:

.. code-block:: yaml

    python-pkgs:
      pkg.installed:
        - names:
          - python-django
          - python-crypto
          - python-yaml

Once converted into the lowstate data structure the above state
declaration will be expanded into the following three state declarations:

.. code-block:: yaml

      python-django:
        pkg.installed

      python-crypto:
        pkg.installed

      python-yaml:
        pkg.installed

Other values can be overridden during the expansion by providing an additional
dictionary level.

.. versionadded:: 2014.7.0

.. code-block:: yaml

  ius:
    pkgrepo.managed:
      - humanname: IUS Community Packages for Enterprise Linux 6 - $basearch
      - gpgcheck: 1
      - baseurl: http://mirror.rackspace.com/ius/stable/CentOS/6/$basearch
      - gpgkey: http://dl.iuscommunity.org/pub/ius/IUS-COMMUNITY-GPG-KEY
      - names:
          - ius
          - ius-devel:
              - baseurl: http://mirror.rackspace.com/ius/development/CentOS/6/$basearch

.. _states-highstate-example:

Large example
=============

Here is the layout in yaml using the names of the highdata structure
components.

.. code-block:: yaml

    <Include Declaration>:
      - <Module Reference>
      - <Module Reference>

    <Extend Declaration>:
      <ID Declaration>:
        [<overrides>]


    # standard declaration

    <ID Declaration>:
      <State Module>:
        - <Function>
        - <Function Arg>
        - <Function Arg>
        - <Function Arg>
        - <Name>: <name>
        - <Requisite Declaration>:
          - <Requisite Reference>
          - <Requisite Reference>


    # inline function and names

    <ID Declaration>:
      <State Module>.<Function>:
        - <Function Arg>
        - <Function Arg>
        - <Function Arg>
        - <Names>:
          - <name>
          - <name>
          - <name>
        - <Requisite Declaration>:
          - <Requisite Reference>
          - <Requisite Reference>


    # multiple states for single id

    <ID Declaration>:
      <State Module>:
        - <Function>
        - <Function Arg>
        - <Name>: <name>
        - <Requisite Declaration>:
          - <Requisite Reference>
      <State Module>:
        - <Function>
        - <Function Arg>
        - <Names>:
          - <name>
          - <name>
        - <Requisite Declaration>:
          - <Requisite Reference>
