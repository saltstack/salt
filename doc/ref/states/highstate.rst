====================================
Highstate Data Structure Definitions
====================================

Include Declaration
===================
The include declaration is always in the top level of the highstate structure
and defines a list of ``Module Reference`` strings to include in this sls.

Example:
.. code-block:: yaml
    include:
      - edit.vim
      - http.server

Module Reference
================
The name of a SLS module defined by a seperate SLS file and residing on the
Salt Master. A module named ``edit.vim`` is a reference to the sls file
salt://edit/vim.sls.

ID Declaration
================
The ID Declaration is the declaration given for defining an individual
highstate component. the ID Declaration key will always reference a value of
a dictonary containing keys referencing ``State Declarations`` and
``Requisite declarations``.

The ID Declaration can be found on the top level, or under the extend
declaration.

Extend Declaration
===================
The ``Extend Declaration`` is used to extend a name declaration from an included
``sls module``. The extend declaration is always in the top level and defines
a dictonary. The keys of the extend declaration always define existing 
``ID Declarations`` which have been defined in included ``sls modules``.

State Declaration
=================
The ``State Declaration`` is one of the 2 structures referenced under an
``ID Declaration``. The state declaration is a list which contains one
string defining the ``function`` and any number of ``function_arg``
dictonaries.
The State Declaration can also, optionaly, contain a number of additional
components, like the name override components - ``name`` and ``names``.
``State Declarations`` can also comtain ``Requisite Declarations``.

Requisite Declaration
=====================
The ``Requisite Declaration`` is used to build the action dependency tree.
While Salt states are made to execute in a deterministic order, this order
is managed by requireing and watching other salt states. The
``Requisite Declaration`` can be found as a list component under a
``State Declaration`` or as a key under an ``ID Declaration``.

``Requisite Declarations`` are always a list containing 
``Requisite References``.

Requisite Reference
===================
A ``Requisite Reference`` is a single key dictonary which occupies a single
index in a ``Requisite Declaration`` list. The dictonary key is the name
of the referenced ``State Declaration``, and the value is the ID of the
referenced ``ID Declaration``.

Function
========
The ``Function`` is the name of the function to call within the state. Any
given state declaration can only have a single function. The function is
defined as the function by the fact that it is the only index in the
``State Declaration`` list.

Function Arg
============
The ``Function Arg`` defines a given argument for the named function under a
``State Declaration``. Function Args are always a single key dictonary
referencing a python type which is to be passed to the named function.

The information to be passed to the function needs to be the data type
expected by the function.

Name
====
The name value is used to override the name argument relative the
``State Declaration``. If the name is not specified then the ``ID Declaration``
satisfies the name argument. The name is always a single key dictonary
referencing a string.

Names
=====
The names value is used to apply the contents of the State Declaration to
multiple states, each with its own name.

Example:
.. code-block:: yaml
    python-pkgs:
      pkg:
        - installed
        - names:
          - python-django
          - python-crypto
          - python-yaml

Large Example
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

