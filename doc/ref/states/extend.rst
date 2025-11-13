.. _extending-external-sls-data:

===========================
Extending External SLS Data
===========================

Sometimes a state defined in one SLS file will need to be modified from a
separate SLS file. A good example of this is when an argument needs to be
overwritten or when a service needs to watch an additional state.

The Extend Declaration
----------------------

A standard way to extend is via the extend declaration. The extend
declaration is a top level declaration like ``include`` that allows
overriding or augmenting state declarations from other SLS files.
Use ``extend`` to override arguments, append requisites,
or otherwise modify an existing ID without editing the original SLS.

Overview
--------

- ``extend`` is a top-level mapping at the same syntactic level as ``include`` or a top-level ID.
- The SLS module that defines the target ID must be included so the ID exists before the
  extend merge is applied.
- Requisite lists (for example ``watch`` and ``require``) are appended; most other keys
  are replaced by the extend entry.
- Only one top-level ``extend`` mapping may appear in a single SLS file; later mappings
  will overwrite earlier ones.

Example
-------

The following shows the original SLS entries (the files being extended) and an extending SLS
that includes them and declares a single ``extend`` block.

Original: ``salt://http/init.sls``

.. code-block:: yaml

    apache:
      pkg.installed: []
      file:
        - name: /etc/httpd/conf/httpd.conf
        - source: salt://http/httpd.conf
      service.running:
        - name: httpd
        - watch:
          - file: apache

Original: ``salt://ssh/init.sls``

.. code-block:: yaml

    ssh-server:
      pkg.installed: []
      service.running:
        - name: sshd

Extending SLS: ``salt://profile/webserver_extend.sls``

.. code-block:: yaml

    include:
      - http
      - ssh

    extend:
      apache:
        file:
          - name: /etc/httpd/conf/httpd.conf
          - source: salt://http/httpd2.conf

      ssh-server:
        service:
          - watch:
            - file: /etc/ssh/banner

    /etc/ssh/banner:
      file.managed:
        - source: salt://ssh/banner

Behavior for this example
-------------------------

- The ``apache:file`` mapping in the extending SLS overrides with the
  ``name`` and ``source`` values from the original ``file`` mapping
  in ``http/init.sls`` with the values supplied under ``extend``.
- The ``ssh-server:service:watch`` list is appended with ``file: /etc/ssh/banner``; any
  existing watch entries declared in ``ssh/init.sls`` are preserved.
- The banner resource is declared locally (``/etc/ssh/banner``) so the appended watch has
  a concrete state to observe; if the resource were absent from the compiled data the
  relationship would be invalid.

Minimal patterns
----------------

Replace a mapping (overwrite):

.. code-block:: yaml

    extend:
      apache:
        file:
          - name: /etc/httpd/conf/httpd.conf
          - source: salt://http/httpd2.conf

Append to a requisite list (merge):

.. code-block:: yaml

    extend:
      ssh-server:
        service:
          - watch:
            - file: /etc/ssh/banner

Extend is a Top Level Declaration
---------------------------------

This means that ``extend`` can only be called once in an sls, if it is used
twice then only one of the extend blocks will be read. So this is WRONG:

.. code-block:: yaml

    include:
      - http
      - ssh

    extend:
      apache:
        file:
          - name: /etc/httpd/conf/httpd.conf
          - source: salt://http/httpd2.conf
    # Second extend will overwrite the first!! Only make one
    extend:
      ssh-server:
        service:
          - watch:
            - file: /etc/ssh/banner


The Requisite "in" Statement
----------------------------

Since one of the most common things to do when extending another SLS is to add
states for a service to watch, or anything for a watcher to watch, the
requisite in statement was added to 0.9.8 to make extending the watch and
require lists easier. The ssh-server extend statement above could be more
cleanly defined like so:

.. code-block:: yaml

    include:
      - ssh

    /etc/ssh/banner:
      file.managed:
        - source: salt://ssh/banner
        - watch_in:
          - service: ssh-server

:ref:`State Requisites <requisites>`


Rules to Extend By
------------------
There are a few rules to remember when extending states:

1. Always include the SLS being extended with an include declaration
2. Requisites (watch and require) are appended to, everything else is
   overwritten
3. extend is a top level declaration, like an ID declaration, cannot be
   declared twice in a single SLS
4. Many IDs can be extended under the extend declaration
