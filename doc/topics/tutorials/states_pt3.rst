=======================================================
States tutorial, part 3 - Templating, Includes, Extends
=======================================================

.. note::

  This tutorial builds on topics covered in :doc:`part 1 <states_pt1>` and
  :doc:`part 2 <states_pt2>`. It is recommended that you begin there.

This part of the tutorial will cover more advanced templating and
configuration techniques for ``sls`` files.

Templating SLS modules
======================

SLS modules may require programming logic or inline execution. This is
accomplished with module templating. The default module templating system used
is `Jinja2`_  and may be configured by changing the :conf_master:`renderer`
value in the master config.

.. _`Jinja2`: http://jinja.pocoo.org/

All states are passed through a templating system when they are initially read.
To make use of the templating system, simply add some templating markup.
An example of an sls module with templating markup may look like this:

.. code-block:: jinja

    {% for usr in ['moe','larry','curly'] %}
    {{ usr }}:
      user.present
    {% endfor %}

This templated sls file once generated will look like this:

.. code-block:: yaml

    moe:
      user.present
    larry:
      user.present
    curly:
      user.present

Here's a more complex example:

.. code-blocK:: jinja

    # Comments in yaml start with a hash symbol.
    # Since jinja rendering occurs before yaml parsing, if you want to include jinja
    # in the comments you may need to escape them using 'jinja' comments to prevent
    # jinja from trying to render something which is not well-defined jinja.
    # e.g.
    # {# iterate over the Three Stooges using a {% for %}..{% endfor %} loop
    # with the iterator variable {{ usr }} becoming the state ID. #}
    {% for usr in 'moe','larry','curly' %}
    {{ usr }}:
      group:
        - present
      user:
        - present
        - gid_from_name: True
        - require:
          - group: {{ usr }}
    {% endfor %}

Using Grains in SLS modules
===========================

Often times a state will need to behave differently on different systems.
:doc:`Salt grains </topics/targeting/grains>` objects are made available
in the template context. The `grains` can be used from within sls modules:

.. code-block:: jinja

    apache:
      pkg.installed:
        {% if grains['os'] == 'RedHat' %}
        - name: httpd
        {% elif grains['os'] == 'Ubuntu' %}
        - name: apache2
        {% endif %}

Using Environment Variables in SLS modules
==========================================

You can use ``salt['environ.get']('VARNAME')`` to use an environment
variable in a Salt state.

.. code-block:: bash

   MYENVVAR="world" salt-call state.template test.sls

.. code-block:: yaml

   Create a file with contents from an environment variable:
  file.managed:
    - name: /tmp/hello
    - contents: {{ salt['environ.get']('MYENVVAR') }}

Error checking:

.. code-block:: yaml

   {% set myenvvar = salt['environ.get']('MYENVVAR') %}
   {% if myenvvar %}

   Create a file with contents from an environment variable:
     file.managed:
       - name: /tmp/hello
       - contents: {{ salt['environ.get']('MYENVVAR') }}

   {% else %}

   Fail - no environment passed in:
     test:
       A. fail_without_changes

   {% endif %}

Calling Salt modules from templates
===================================

All of the Salt modules loaded by the minion are available within the
templating system. This allows data to be gathered in real time on the target
system. It also allows for shell commands to be run easily from within the sls
modules.

The Salt module functions are also made available in the template context as
``salt:``

The following example illustrates calling the ``group_to_gid`` function in the
``file`` execution module with a single positional argument called
``some_group_that_exists``.

.. code-block:: jinja

    moe:
      user.present:
        - gid: {{ salt['file.group_to_gid']('some_group_that_exists') }}

One way to think about this might be that the ``gid`` key is being assigned
a value equivelent to the following python pseudo-code:

.. code-block:: python

    import salt.modules.file
    file.group_to_gid('some_group_that_exists')

Note that for the above example to work, ``some_group_that_exists`` must exist
before the state file is processed by the templating engine.

Below is an example that uses the ``network.hw_addr`` function to retrieve the
MAC address for eth0:

.. code-block:: python

    salt['network.hw_addr']('eth0')

To examine the possible arguments to each execution module function,
one can examine the `module reference documentation </ref/modules/all>`:

Advanced SLS module syntax
==========================

Lastly, we will cover some incredibly useful techniques for more complex State
trees.

Include declaration
-------------------

A previous example showed how to spread a Salt tree across several files.
Similarly, :doc:`requisites </ref/states/requisites>` span multiple files by
using an :ref:`include-declaration`. For example:

``python/python-libs.sls:``

.. code-block:: yaml

    python-dateutil:
      pkg.installed

``python/django.sls:``

.. code-block:: yaml

    include:
      - python.python-libs

    django:
      pkg.installed:
        - require:
          - pkg: python-dateutil

Extend declaration
------------------

You can modify previous declarations by using an :ref:`extend-declaration`. For
example the following modifies the Apache tree to also restart Apache when the
vhosts file is changed:

``apache/apache.sls:``

.. code-block:: yaml

    apache:
      pkg.installed

``apache/mywebsite.sls:``

.. code-block:: yaml

    include:
      - apache.apache

    extend:
      apache:
        service:
          - running
          - watch:
            - file: /etc/httpd/extra/httpd-vhosts.conf

    /etc/httpd/extra/httpd-vhosts.conf:
      file.managed:
        - source: salt://apache/httpd-vhosts.conf

.. include:: /_incl/extend_with_require_watch.rst

Name declaration
----------------

You can override the :ref:`id-declaration` by using a :ref:`name-declaration`.
For example, the previous example is a bit more maintainable if rewritten as
follows:

``apache/mywebsite.sls:``

.. code-block:: yaml
    :emphasize-lines: 8,10,12

    include:
      - apache.apache

    extend:
      apache:
        service:
          - running
          - watch:
            - file: mywebsite

    mywebsite:
      file.managed:
        - name: /etc/httpd/extra/httpd-vhosts.conf
        - source: salt://apache/httpd-vhosts.conf

Names declaration
-----------------

Even more powerful is using a :ref:`names-declaration` to override the
:ref:`id-declaration` for multiple states at once. This often can remove the
need for looping in a template. For example, the first example in this tutorial
can be rewritten without the loop:

.. code-block:: yaml

    stooges:
      user.present:
        - names:
          - moe
          - larry
          - curly

Next steps
==========

In :doc:`part 4 <states_pt4>` we will discuss how to use salt's
:conf_master:`file_roots` to set up a workflow in which states can be
"promoted" from dev, to QA, to production.
