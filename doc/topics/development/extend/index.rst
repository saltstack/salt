.. _development-salt-extend:

===========
Salt Extend
===========

``salt-extend`` is a templating tool for extending SaltStack. If you're looking to add a module to
SaltStack, then the ``salt-extend`` utility can guide you through the process.

You can use Salt Extend to quickly create templated modules for adding new behaviours to some of the module subsystems within Salt.

Salt Extend takes a template directory and merges it into a SaltStack source code directory.

Command line usage
~~~~~~~~~~~~~~~~~~

*See* :ref:`salt-extend <salt-extend>`

Choosing a template
~~~~~~~~~~~~~~~~~~~

The following templates are available:

module
^^^^^^

Creates a new execution module within salt/modules/{{module_name}}.py

module_unit
^^^^^^^^^^^

Creates a new execution module unit test suite within tests/unit/modules/{{module_name}}_test.py

state
^^^^^

Creates a new state module within salt/states/{{module_name}}.py

state_unit
^^^^^^^^^^

Creates a new state module unit test suite within tests/unit/states/{{module_name}}_test.py


Adding templates
~~~~~~~~~~~~~~~~

1. Create a directory under <src>/templates
2. Create a file ``template.yml`` containing properties for

 * ``description`` - a description of the template
 * ``questions`` - a collection of additional questions to ask the user, the name of the item will
   be used as the key in the context dictionary within the jinja template.
   
   * ``question`` - The question to ask the user, as a string
   * ``default`` - (optional) the default value, can contain Jinja2 template syntax and has access to the default context properties

Example template.yml
^^^^^^^^^^^^^^^^^^^^

.. code-block:: yaml

    description: "Execution module"
    questions:
        depending_libraries:
            question: "What libraries does this module depend upon?"
        virtual_name:
            question: "What module virtual name to use?"
            default: "{{module_name}}"

3. Create the files within <src>/templates/<your template> to match the target

.. note::
    
    File names can contain Jinja 2 template syntax, e.g. *'{{module_name}}.py}}'*

Example file in the template directory
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    print('Hello {{module_name}}')
    __virtual__ = '{{__virtual_name__}}'
    
Default context properties
^^^^^^^^^^^^^^^^^^^^^^^^^^

The default context provides the following properties

* ``description`` - A description of the template
* ``short_description`` - A short description of the module as entered by the user
* ``version`` - The version name of the next release
* ``module_name`` - The module name as entered by the user
* ``release_date`` - The current date in the format *YYYY-MM-DD*
* ``year`` - The current year in the format *YYYY*

As well as any additional properties entered from the questions section of ``template.yml``

API
~~~

salt.utils.extend module
========================

.. automodule:: salt.utils.extend
    :members: