====================================
Highstate data structure definitions
====================================

The Salt State Tree
===================

.. glossary::

    Top file
        The main state file that instructs minions what environment and modules
        to use during state execution.

        Configurable via :conf_master:`state_top`.

        .. seealso:: :doc:`A detailed description of the top file </ref/states/top>`

.. glossary::

    State tree
        A collection of ``SLS`` files that live under the directory specified
        in :conf_master:`file_roots`. A state tree can be organized into
        ``SLS modules``.

Include declaration
-------------------

.. glossary::

    Include declaration
        Defines a list of :term:`module reference` strings to include in this
        :term:`SLS`.

        Occurs only in the top level of the highstate structure.

Example:

.. code-block:: yaml

    include:
      - edit.vim
      - http.server

Module reference
----------------

.. glossary::

    Module reference
        The name of a SLS module defined by a separate SLS file and residing on
        the Salt Master. A module named ``edit.vim`` is a reference to the SLS
        file ``salt://edit/vim.sls``.

ID declaration
--------------

.. glossary::

    ID declaration
        Defines an individual highstate component. Always references a value of
        a dictionary containing keys referencing :term:`state declarations
        <state declaration>` and :term:`requisite declarations <requisite
        declaration>`. Can be overridden by a :term:`name declaration` or a
        :term:`names declaration`.

        Occurs on the top level or under the :term:`extend declaration`.

.. note:: Naming gotchas

        Must **not** contain a dot, otherwise highstate summary output will be
        unpredictable. (This has been fixed in versions 0.9.7 and above)

        Must be unique across entire state tree. If the same ID declaration is
        used twice, only the first one matched will be used. All subsequent
        ID declarations with the same name will be ignored.

Extend declaration
------------------

.. glossary::

    Extend declaration
        Extends a :term:`name declaration` from an included ``SLS module``. The
        keys of the extend declaration always define existing :term:`ID
        declarations <ID declaration>` which have been defined in included
        ``SLS modules``.

        Occurs only in the top level and defines a dictionary.

Extend declarations are useful for adding-to or overriding parts of a
:term:`state declaration` that is defined in another ``SLS`` file. In the
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
      file:
        - managed

State declaration
-----------------

.. glossary::

    State declaration
        A list which contains one string defining the :term:`function
        declaration` and any number of :term:`function arg declaration`
        dictionaries.

        Can, optionally, contain a number of additional components like the
        name override components — :term:`name <name declaration>` and
        :term:`names <names declaration>`. Can also contain :term:`requisite
        declarations <requisite declaration>`.

        Occurs under an :term:`ID declaration`.

Requisite declaration
---------------------

.. glossary::

    Requisite declaration
        A list containing :term:`requisite references <requisite reference>`.

        Used to build the action dependency tree. While Salt states are made to
        execute in a deterministic order, this order is managed by requiring
        and watching other Salt states.

        Occurs as a list component under a :term:`state declaration` or as a
        key under an :term:`ID declaration`.

Requisite reference
-------------------

.. glossary::

    Requisite reference
        A single key dictionary. The key is the name of the referenced
        :term:`state declaration` and the value is the ID of the referenced
        :term:`ID declaration`.

        Occurs as a single index in a :term:`requisite declaration` list.

Function declaration
--------------------

.. glossary::

    Function declaration
        The name of the function to call within the state. A state declaration
        can contain only a single function declaration.

        For example, the following state declaration calls the :mod:`installed
        <salt.states.pkg.installed>` function in the ``pkg`` state module:

        .. code-block:: yaml

            httpd:
              pkg.installed

        The function can be declared inline with the state as a shortcut, but
        the actual data structure is better referenced in this form:

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
              pkg:
                - installed
              service:
                - running

        Occurs as the only index in the :term:`state declaration` list.

Function arg declaration
------------------------

.. glossary::

    Function arg declaration
        A single key dictionary referencing a Python type which is to be passed
        to the named :term:`function declaration` as a parameter. The type must
        be the data type expected by the function.

        Occurs under a :term:`function declaration`.

For example in the following state declaration ``user``, ``group``, and
``mode`` are passed as arguments to the :mod:`managed
<salt.states.file.managed>` function in the ``file`` state module:

.. code-block:: yaml

    /etc/http/conf/http.conf:
      file.managed:
        - user: root
        - group: root
        - mode: 644

Name declaration
----------------

.. glossary::

    Name declaration
        Overrides the ``name`` argument of a :term:`state declaration`. If
        ``name`` is not specified the :term:`ID declaration` satisfies the
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
      service:
        - running
        - watch:
          - file: mywebsite

Names declaration
-----------------

.. glossary::

    Names declaration
        Expands the contents of the containing :term:`state declaration` into
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

    <ID Declaration>:
      <State Declaration>:
        - <Function>:
        - <Function Arg>
        - <Function Arg>
        - <Function Arg>
        - <Name>: <name>
        - <Requisite Declaration>:
          - <Requisite Reference>
          - <Requisite Reference>

    <ID Declaration>:
      <State Declaration>.<Function>:
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
