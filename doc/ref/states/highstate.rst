====================================
Highstate data structure definitions
====================================

The Salt State Tree
===================

Include declaration
-------------------

.. glossary::

    Include declaration
        Defines a list of :term:`module reference` strings to include in this
        :term:`sls`.

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
        the Salt Master. A module named ``edit.vim`` is a reference to the sls
        file ``salt://edit/vim.sls``.

ID declaration
--------------

.. glossary::

    ID declaration
        Defines an individual highstate component. Always references a value of
        a dictionary containing keys referencing :term:`state declarations
        <state declaration>` and :term:`requisite declarations <requisite
        declaration>`. Can be overridden by :term:`name` and :term:`names`.

        Occurs on the top level or under the :term:`extend declaration`.

Extend declaration
------------------

.. glossary::

    Extend declaration
        Used to extend a :term:`name` declaration from an included ``sls
        module``. The keys of the extend declaration always define existing
        :term:`ID declarations <ID declaration>` which have been defined in
        included ``sls modules``.

        Occurs only in the top level and defines a dictionary.

State declaration
-----------------

.. glossary::

    State declaration
        A list which contains one string defining the :term:`function` and any
        number of :term:`function arg` dictionaries.

        Can, optionally, contain a number of additional components like the
        name override components — :term:`name` and :term:`names <name>`. Can
        also contain :term:`requisite declarations <requisite declaration>`.

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
        The name of the function to call within the state. Any given state
        declaration can only have a single function.

        Occurs as the only index in the :term:`state declaration` list.

Function arg declaration
------------------------

.. glossary::

    Function arg declaration
        A single key dictionary referencing a Python type which is to be passed
        to the named :term:`function` as a parameter. The type must be the data
        type expected by the function.

        Occurs under a :term:`function`.

Name declaration
----------------

.. glossary::

    Name declaration
        Used to override the name argument relative the :term:`state
        declaration`. If the name is not specified then the :term:`ID
        declaration` satisfies the name argument. The name is always a single
        key dictionary referencing a string.

Names declaration
-----------------

.. glossary::

    Names declaration
        Used to apply the contents of the :term:`state declaration` to multiple
        states, each with its own name.

        Example:

        .. code-block:: yaml

            python-pkgs:
              pkg:
                - installed
                - names:
                  - python-django
                  - python-crypto
                  - python-yaml

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
        <State Declaration>:
          - <Function>
          - <Function Arg>
          - <Function Arg>
          - <Function Arg>
          - <Name>: <name>
          - <Requisite Declaration>:
            - <Requisite Reference>
            - <Requisite Reference>
      <ID Declaration>:
        <State Declaration>:
          - <Function>
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
    <ID Declaration>:
      <State Declaration>:
        - <Function>
        - <Function Arg>
        - <Function Arg>
        - <Function Arg>
        - <Name>
        - <Requisite Declaration>:
          - <Requisite Reference>
          - <Requisite Reference>
    <ID Declaration>:
      <State Declaration>:
        - <Function>
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
