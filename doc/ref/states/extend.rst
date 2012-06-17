===========================
Extending External SLS Data
===========================

Sometimes a state defined in one SLS file will need to be modified from a
separate SLS file. A good example of this is when an argument needs to be
overwritten or when a service needs to watch an additional state.

The Extend Declaration
----------------------

The standard way to extend is via the extend declaration. The extend
declaration is a top level declaration like ``include`` and encapsulates ID
declaration data included from other SLS files. A standard extend looks like
this:

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

A few critical things happened here, first off the SLS files that are going to
be extended are included, then the extend dec is defined. Under the extend dec
2 IDs are extended, the apache ID's file state is overwritten with a new name
and source. Than the ssh server is extended to watch the banner file in
addition to anything it is already watching.

Extend is a Top Level Declaration
---------------------------------

This means that ``extend`` can only be called once in an sls, if if is used
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

Rules to Extend By
------------------
There are a few rules to remember when extending states:

1. Always include the SLS being extended with an include declaration
2. Requisites (watch and require) are appended to, everything else is
   overwritten
3. extend is a top level declaration, like an ID declaration, cannot be
   declared twice in a single SLS
4. Many IDs can be extended under the extend declaration
