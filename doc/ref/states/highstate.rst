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

Defines a list of :ref:`sls-module-reference` strings to include in this ``SLS``.

Occurs only in the top level of the SLS data structure.

Example:

.. code-block:: yaml

    include:
      - edit.vim
      - http.server

.. _sls-module-reference:

SLS module reference
--------------------

A reference to an SLS module defined by a separate SLS file or
directory residing on the Salt Master.
For example ``edit.vim`` is a reference to the SLS
file ``salt://edit/vim.sls``.

.. _id-declaration:

ID declaration
--------------

A label that identifies an individual :ref:`highstate <running-highstate>` component.
The ID is a reference to a dictionary containing entries of one or more
:ref:`state-declaration` components.
The ID is used as an implicit name argument for the state function for any of
the referenced state declarations that do not provide an
explicit name with a :ref:`name-declaration` or a :ref:`names-declaration`.

Occurs on the top level or under the :ref:`extend-declaration`.

Must be unique across the entire state tree. If the same ID declaration is
used twice, then a compilation error will occur.

.. note:: Naming gotchas

    In Salt versions earlier than 0.9.7, ID declarations containing dots would
    result in unpredictable output.

.. _state-declaration:

State declaration
-----------------

A state declaration consists of a :ref:`state-module-declaration`,
a :ref:`function-declaration` and any number of
:ref:`function-arg-declaration` items.

Can, optionally, contain a number of additional components like the
name components — :ref:`name <name-declaration>` and
:ref:`names <names-declaration>`. Can also contain :ref:`requisite
declarations <requisite-declaration>`.

Occurs under an :ref:`ID-declaration`.

.. _state-module-declaration:

State Module declaration
------------------------

Names the Salt state module (for example ``file``, ``pkg``,
``service``) that provides the function invoked for the state.

Occurs in the key/identifier of the :ref:`state-declaration` dictionary
under an :ref:`ID declaration <id-declaration>`.

Multiple state module declarations can be specified under the same
ID declaration but per ID each state module must be unique.

.. _function-declaration:

Function declaration
--------------------

The name of the function to call within the state. A state declaration
can contain only a single function declaration.

Occurs in the :ref:`state-declaration`

For example, the following state declaration calls the :mod:`installed
<salt.states.pkg.installed>` function in the ``pkg`` state module:

.. code-block:: yaml

    httpd:
      pkg.installed: []

The function can be declared combined inline with the
:ref:`state-module-declaration` separated by a period `.`
as a short form dot notation.
The actual data structure is compiled to the long form shown below:

.. code-block:: yaml

    httpd:
      pkg:
        - fun: installed

If no arguments need to be given to the function, the argument list can be
omitted and the state declaration can be given as a single string in short form:

.. code-block:: yaml

    httpd:
      pkg.installed

Note that this string short form cannot be more than once per ID declaration.
When passing a function without arguments and another state declaration within
a single ID declaration component, then an empty list or dictionary needs
to be specified as the arguments value since otherwise it does not represent
a valid data structure.

VALID:

.. code-block:: yaml

    httpd:
      pkg.installed: []
      service.running: {}

INVALID:

.. code-block:: yaml

    httpd:
      pkg.installed
      service.running

.. _function-arg-declaration:

Function arg declaration
------------------------

A argument consisting of keyword and value which is to be passed to the named
:ref:`function-declaration` as a parameter. The type of each value must be
the data type expected by the function.
The function arguments can be specified as a dictionary or as a list with each
item as single item dictionary.

Occurs under a :ref:`function-declaration`.

For example in the following state declaration ``user``, ``group``, and
``mode`` are passed as arguments to the :mod:`managed
<salt.states.file.managed>` function in the ``file`` state module by
specifying the arguments as a dictionary:

.. code-block:: yaml

    /etc/http/conf/http.conf:
      file.managed:
        user: root
        group: root
        mode: '0644'

In this example the arguments are specified as a list of single item dictionaries:

.. code-block:: yaml

    /etc/http/conf/http.conf:
      file.managed:
        - user: root
        - group: root
        - mode: '0644'

.. _requisite-declaration:

Requisite declaration
---------------------

A key value pair of key that is a :ref:`requisite type <requisite-types>`
with a value that is a list containing :ref:`requisite references <requisite-reference>`.

Used to build the action dependency tree. While Salt states are made to
execute in a deterministic order, this order is managed by requiring
and watching other Salt states.

Occurs as a component in a :ref:`state-declaration`.

.. code-block:: yaml

    <Requisite type declaration>:
        - <Requisite Reference>
        - <Requisite Reference>

.. code-block:: yaml

    require:  # requisite type
        - file: /etc/http/conf/http.conf
        - service: httpd
        - httpd

See requisites: :ref:`Requisites <requisites>`

.. _requisite-type-declaration:

Requisite type declaration
--------------------------

The type of the dependency/requisite relationship.

Occurs in a :ref:`requisite-declaration`.

See :ref:`requisite-types`

.. _requisite-reference:

Requisite reference
-------------------

One of the items in a :ref:`requisite-declaration` list that specifies
a target of the requisite.

Either

- A key value pair where the key is the name of the referenced
  :ref:`state-module-declaration` and the value is the ID of the referenced
  :ref:`ID-declaration` or the :ref:`name <name-declaration>` of the
  referenced :ref:`state-declaration`.
  For example the reference `file: vim` is a reference a state declaration
  with the to the state module ``file`` with the ID or name ``vim``
- A single string identifier. In version 2016.3.0, the state module name was
  made optional. If the state module is omitted, all states matching the
  identifier will be required, regardless of which state module they are using.

Occurs in a :ref:`requisite-declaration` list.

.. _name-declaration:

Name declaration
----------------

Specifies the ``name`` argument of a :ref:`state-declaration`. If
``name`` is not specified the :ref:`ID-declaration` satisfies the
``name`` argument.

The name is a string.

Including a ``name`` declaration is useful for a variety of scenarios.

For example, avoiding clashing ID declarations. The following two state
declarations cannot both have ``/etc/motd`` as the ID declaration:

.. code-block:: yaml

    motd_perms:
      file.managed:
        name: /etc/motd
        mode: '0644'

    motd_quote:
      file.append:
        name: /etc/motd
        text: "Of all smells, bread; of all tastes, salt."

Another common reason to override ``name`` is if the ID declaration is long and
needs to be referenced in multiple places. In the example below it is much
easier to specify ``mywebsite`` than to specify
``/etc/apache2/sites-available/mywebsite.com`` multiple times:

.. code-block:: yaml

    mywebsite:
      file.managed:
        name: /etc/apache2/sites-available/mywebsite.com
        source: salt://mywebsite.com

    a2ensite mywebsite.com:
      cmd.wait:
        unless: test -L /etc/apache2/sites-enabled/mywebsite.com
        watch:
          - file: mywebsite

    apache2:
      service.running:
        watch:
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
        names:
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
        humanname: IUS Community Packages for Enterprise Linux 6 - $basearch
        gpgcheck: 1
        baseurl: http://mirror.rackspace.com/ius/stable/CentOS/6/$basearch
        gpgkey: http://dl.iuscommunity.org/pub/ius/IUS-COMMUNITY-GPG-KEY
        names:
            - ius
            - ius-devel:
              - baseurl: http://mirror.rackspace.com/ius/development/CentOS/6/$basearch

.. _extend-declaration:

Extend declaration
------------------

Extends a :ref:`state-declaration` from an included ``SLS module``.

Occurs only in the top level and defines a dictionary.

States cannot be extended more than once in a single state run.

See extending states: :ref:`Extending External SLS Data <extending-external-sls-data>`

.. _states-highstate-example:

Large example
=============

Here is the layout in yaml using the names of the highdata structure
components.

.. code-block:: yaml

    <Include Declaration>:
      - <SLS Module Reference>
      - <SLS Module Reference>

    <Extend Declaration>:
      <ID Declaration>:
        [<overrides>]

    # inline short form dot notation for function declaration with dictionary
    # for function arguments, names, and requisites
    <ID declaration>:
      <State Module Declaration>.<Function Declaration>:
        <Function Arg Declaration>
        <Function Arg Declaration>
        <Function Arg Declaration>
        <Name or Names Declaration>
        <Requisite Declaration>
        <Requisite Declaration>

    # inline short form dot notation for function declaration with list
    # for function arguments, names, and requisites
    <ID declaration>:
      <State Module declaration>.<Function Declaration>:
        - <Function Arg Declaration>
        - <Function Arg Declaration>
        - <Function Arg Declaration>
        - <Name or Names Declaration>
        - <Requisite Declaration>
        - <Requisite Declaration>

    # multiple states for single id
    <ID Declaration>:
      <State Module Declaration>.<Function Declaration>:
        <Function Arg Declaration>s...
        <Name or Names Declaration>
        <Requisite Declaration>s...
      <State Module Declaration>.<Function Declaration>:
        <Function Arg Declaration>s...
        <Name or Names Declaration>
        <Requisite Declaration>s...

    # traditional declaration

    <ID Declaration>:
      <State Module Declaration>:
        - <Function Declaration>
        - <Function Arg Declaration>s...
        - <Name or Names Declaration>
        - <Requisite Declaration>s...
      <State Module Declaration>:
        - <Function Declaration>
        - <Function Arg Declaration>s...
        - <Name or Names Declaration>
        - <Requisite Declaration>s...
