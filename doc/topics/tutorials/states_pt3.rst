=======================
States tutorial, part 3
=======================

This tutorial builds on the topic covered in :doc:`part 2 <states_pt2>`. It is
recommended that you begin there.

This tutorial will cover more advanced templating and configuration techniques
for ``sls`` files.

Templating SLS modules
======================

SLS modules may require programming logic or inline executions. This is
accomplished with module templating. The default module templating system used
is `Jinja2`_  and may be configured by changing the :conf_master:`renderer`
value in the master config.

.. _`Jinja2`: http://jinja.pocoo.org/

All states are passed through a templating system when they are initially read,
so all that is required to make use of the templating system is to add some
templating code. An example of an sls module with templating may look like
this:

.. code-block:: yaml

    {% for usr in 'moe','larry','curly' %}
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

Using Grains in SLS modules
===========================

Often times a state will need to behave differently on different systems.
:doc:`Salt grains </topics/targeting/grains>` can be used from within sls modules. An object
called ``grains`` is made available in the template context:

.. code-block:: yaml

    apache:
      pkg.installed:
        {% if grains['os'] == 'RedHat' %}
        - name: httpd
        {% elif grains['os'] == 'Ubuntu' %}
        - name: apache2
        {% endif %}

Calling Salt modules from templates
===================================

All of the Salt modules loaded by the minion are available within the
templating system. This allows data to be gathered in real time on the target
system. It also allows for shell commands to be run easily from within the sls
modules.

The Salt module functions are also made available in the template context as
``salt``:

.. code-block:: yaml

    {% for usr in 'moe','larry','curly' %}
    {{ usr }}:
      group:
        - present
      user:
        - present
        - gid: {{ salt['file.group_to_gid'](usr) }}
        - require:
          - group: {{ usr }}
    {% endfor %}

Below is an example that uses the ``network.hwaddr`` function to retrieve the
MAC address for eth0:

    salt['network.hwaddr']('eth0')

Advanced SLS module syntax
==========================

Last we will cover some incredibly useful techniques for more complex State
trees.

:term:`Include declaration`
---------------------------

You have seen an example of how to spread a Salt tree across several files but
in order to be able to have :term:`requisite references <requisite reference>`
span multiple files you must use an :term:`include declaration`. For example:

``python-libs.sls``:

.. code-block:: yaml

    python-dateutil:
      pkg.installed

``django.sls``:

.. code-block:: yaml

    include:
      - python-libs

    django:
      pkg.installed:
        - require:
          - pkg: python-dateutil

:term:`Extend declaration`
--------------------------

You can modify previous declarations by using an :term:`extend declaration`. For
example the following modifies the Apache tree to also restart Apache when the
vhosts file is changed:

``apache.sls``:

.. code-block:: yaml

    apache:
      pkg.installed

``mywebsite.sls``:

.. code-block:: yaml

    include:
      - apache

    extend:
      apache:
        service:
          - watch:
            - file: /etc/httpd/extra/httpd-vhosts.conf

    /etc/httpd/extra/httpd-vhosts.conf:
      file.managed:
        - source: salt://httpd-vhosts.conf


:term:`Name declaration`
------------------------

You can override the :term:`ID declaration` by using a :term:`name
declaration`. For example, the previous example is a bit more maintainable if
rewritten as follows:

``mywebsite.sls``:

.. code-block:: yaml
    :emphasize-lines: 8,10,13

    include:
      - apache

    extend:
      apache:
        service:
          - watch:
            - file: mywebsite

    mywebsite:
      file.managed:
        - name: /etc/httpd/extra/httpd-vhosts.conf
        - source: salt://httpd-vhosts.conf

:term:`Names declaration`
-------------------------

Even more powerful is using a :term:`names declaration` to override the
:term:`ID declaration` for multiple states at once. This often can remove the
need for looping in a template. For example, the first example in this tutorial
can be rewritten without the loop:

.. code-block:: yaml

    stooges:
      user.present:
        - names:
          - moe
          - larry
          - curly

Continue learning
=================

The best way to continue learning about Salt States is to read through the
:doc:`reference documentation </ref/states/index>` and to look through examples
of existing :term:`state trees <state tree>`. You can find examples in the
`salt-states repository`_ and please send a pull-request on GitHub with any
state trees that you build and want to share!

.. _`salt-states repository`: https://github.com/saltstack/salt-states

If you have any questions, suggestions, or just want to chat with other people
who are using Salt we have an :doc:`active community </topics/community>`.
