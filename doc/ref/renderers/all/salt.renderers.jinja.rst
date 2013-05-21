====================
salt.renderers.jinja
====================

Jinja in States
===============

.. _Jinja: http://jinja.pocoo.org/docs/templates/

The most basic usage of Jinja in state files is using control structures to wrap
conditional or redundant state elements:

.. code-block:: yaml

    {% if grains['os'] != 'FreeBSD' %}
    tcsh:
        pkg:
            - installed
    {% endif %}

    motd:
      file.managed:
        {% if grains['os'] == 'FreeBSD' %}
        - name: /etc/motd
        {% elif grains['os'] == 'Debian' %}
        - name: /etc/motd.tail
        {% endif %}
        - source: salt://motd

In this example, the first if block will only be evaluated on minions that
aren't running FreeBSD, and the second block changes the file name based on the
*os* grain.

Writing **if-else** blocks can lead to very redundant state files however. In
this case, using :doc:`pillars</topics/pillar/index>`, or using a previously
defined variable might be easier:

.. code-block:: yaml

    {% set motd = ['/etc/motd'] %}
    {% if grains['os'] == 'Debian' %}
      {% set motd = ['/etc/motd.tail', '/var/run/motd'] %}
    {% endif %}

    {% for motdfile in motd %}
    {{ motdfile }}:
      file.managed:
        - source: salt://motd
    {% endfor %}

Using a variable set by the template, the `for loop`_ will iterate over the
list of MOTD files to update, adding a state block for each file.

.. _`for loop`: http://jinja.pocoo.org/docs/templates/#for

Passing Variables
=================

It is also possible to pass additional variable context directly into a
template, using the ``defaults`` and ``context`` mappings of the
:doc:`file.managed</ref/states/all/salt.states.file>` state:

.. code-block:: yaml

    /etc/motd:
      file.managed:
        - source: salt://motd
        - template: jinja
        - defaults:
            message: 'Foo'
        {% if grains['os'] == 'FreeBSD' %}
        - context:
            message: 'Bar'
        {% endif %}

The template will receive a variable ``message``, which would be accessed in the
template using ``{{ message }}``. If the operating system is FreeBSD, the value
of the variable ``message`` would be *Bar*, otherwise it is the default
*Foo*

Include and Import
==================

Includes and imports_ can be used to share common, reusable state configuration
between state files and between files.

.. code-block:: yaml

    {% from 'lib.sls' import test %}

This would import the ``test`` template variable or macro, not the ``test``
state element, from the file ``lib.sls``. In the case that the included file
performs checks again grains, or something else that requires context, passing
the context into the included file is required:

.. code-block:: yaml

    {% from 'lib.sls' import test with context %}

.. _imports: http://jinja.pocoo.org/docs/templates/#import

Template Inheritance
====================

`Template inheritance`_ works fine from state files and files. The search path
starts at the root of the state tree or pillar.

Macros
======

Macros_ are helpful for eliminating redundant code, however stripping whitespace
from the template block, as well as contained blocks, may be necessary to
emulate a variable return from the macro.

.. code-block:: yaml

    # init.sls
    {% from 'lib.sls' import pythonpkg with context %}

    python-virtualenv:
      pkg.installed:
        - name: {{ pythonpkg('virtualenv') }}

    python-fabric:
      pkg.installed:
        - name: {{ pythonpkg('fabric') }}

.. code-block:: yaml

    # lib.sls
    {% macro pythonpkg(pkg) -%}
      {%- if grains['os'] == 'FreeBSD' -%}
        py27-{{ pkg }}
      {%- elif grains['os'] == 'Debian' -%}
        python-{{ pkg }}
      {%- endif -%}
    {%- endmacro %}

This would define a macro_ that would return a string of the full package name,
depending on the packaging system's naming convention. The whitespace of the
macro was eliminated, so that the macro would return a string without line
breaks, using `whitespace control`_.

.. _`Template inheritance`: http://jinja.pocoo.org/docs/templates/#template-inheritance
.. _`Macros`: http://jinja.pocoo.org/docs/templates/#macros
.. _`macro`: http://jinja.pocoo.org/docs/templates/#macros
.. _`whitespace control`: http://jinja.pocoo.org/docs/templates/#whitespace-control

Jinja in Files
==============

Jinja_ can be used in the same way in managed files:

.. code-block:: yaml

    # redis.sls
    /etc/redis/redis.conf:
        file.managed:
            - source: salt://redis.conf
            - template: jinja
            - context:
                bind: 127.0.0.1

.. code-block:: yaml

    # lib.sls
    {% set port = 6379 %}

.. code-block:: ini

    # redis.conf
    {% from 'lib.sls' import port with context %}
    port {{ port }}
    bind {{ bind }}

As an example, configuration was pulled from the file context and from an
external template file.


.. automodule:: salt.renderers.jinja
    :members:
