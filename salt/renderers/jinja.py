# -*- coding: utf-8 -*-
'''
Jinja loading utils to enable a more powerful backend for jinja templates

Jinja in States
===============

.. _Jinja: http://jinja.pocoo.org/docs/templates/

The most basic usage of Jinja in state files is using control structures to
wrap conditional or redundant state elements:

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

Template Inheritance
====================

`Template inheritance`_ works fine from state files and files. The search path
starts at the root of the state tree or pillar.

.. _`Template inheritance`: http://jinja.pocoo.org/docs/templates/#template-inheritance
.. _`Macros`: http://jinja.pocoo.org/docs/templates/#macros
.. _`macro`: http://jinja.pocoo.org/docs/templates/#macros
.. _`whitespace control`: http://jinja.pocoo.org/docs/templates/#whitespace-control

Filters
=======

Saltstack extends `builtin filters`_ with these custom filters:

strftime
  Converts any time related object into a time based string. It requires a
  valid :ref:`strftime directives <python2:strftime-strptime-behavior>`. An
  :ref:`exhaustive list <python2:strftime-strptime-behavior>` can be found in
  the official Python documentation.

  .. code-block:: yaml

      {% set curtime = None | strftime() %}

  Fuzzy dates require the `timelib`_ Python module is installed.

  .. code-block:: yaml

      {{ "2002/12/25"|strftime("%y") }}
      {{ "1040814000"|strftime("%Y-%m-%d") }}
      {{ datetime|strftime("%u") }}
      {{ "tomorrow"|strftime }}

sequence
  Ensure that parsed data is a sequence.

yaml_encode
  Serializes a single object into a YAML scalar with any necessary
  handling for escaping special characters.  This will work for any
  scalar YAML data type: ints, floats, timestamps, booleans, strings,
  unicode.  It will *not* work for multi-objects such as sequences or
  maps.

  .. code-block:: yaml

      {%- set bar = 7 %}
      {%- set baz = none %}
      {%- set zip = true %}
      {%- set zap = 'The word of the day is "salty"' %}

      {%- load_yaml as foo %}
      bar: {{ bar|yaml_encode }}
      baz: {{ baz|yaml_encode }}
      baz: {{ zip|yaml_encode }}
      baz: {{ zap|yaml_encode }}
      {%- endload %}

  In the above case ``{{ bar }}`` and ``{{ foo.bar }}`` should be
  identical and ``{{ baz }}`` and ``{{ foo.baz }}`` should be
  identical.

yaml_dquote
  Serializes a string into a properly-escaped YAML double-quoted
  string.  This is useful when the contents of a string are unknown
  and may contain quotes or unicode that needs to be preserved.  The
  resulting string will be emitted with opening and closing double
  quotes.

  .. code-block:: yaml

      {%- set bar = '"The quick brown fox . . ."' %}
      {%- set baz = 'The word of the day is "salty".' %}

      {%- load_yaml as foo %}
      bar: {{ bar|yaml_dquote }}
      baz: {{ baz|yaml_dquote }}
      {%- endload %}

  In the above case ``{{ bar }}`` and ``{{ foo.bar }}`` should be
  identical and ``{{ baz }}`` and ``{{ foo.baz }}`` should be
  identical.  If variable contents are not guaranteed to be a string
  then it is better to use ``yaml_encode`` which handles all YAML
  scalar types.

yaml_squote
   Similar to the ``yaml_dquote`` filter but with single quotes.  Note
   that YAML only allows special escapes inside double quotes so
   ``yaml_squote`` is not nearly as useful (viz. you likely want to
   use ``yaml_encode`` or ``yaml_dquote``).

.. _`builtin filters`: http://jinja.pocoo.org/docs/templates/#builtin-filters
.. _`timelib`: https://github.com/pediapress/timelib/

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

.. note::

    Macros and variables can be shared across templates. They should not be
    starting with one or more underscores, and should be managed by one of the
    following tags: `macro`, `set`, `load_yaml`, `load_json`, `import_yaml` and
    `import_json`.

Calling Salt Functions
======================

The Jinja renderer provides a shorthand lookup syntax for the ``salt``
dictionary of :term:`execution function <Execution Function>`.

.. versionadded:: 2014.7.0

.. code-block:: yaml

    # The following two function calls are equivalent.
    {{ salt['cmd.run']('whoami') }}
    {{ salt.cmd.run('whoami') }}

Debugging
=========

The ``show_full_context`` function can be used to output all variables present
in the current Jinja context.

.. versionadded:: 2014.7.0

.. code-block:: yaml

    Context is: {{ show_full_context() }}
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import salt libs
from salt.exceptions import SaltRenderError
import salt.utils.templates

# Import 3rd-party libs
import salt.ext.six as six
from salt.ext.six.moves import StringIO  # pylint: disable=import-error

log = logging.getLogger(__name__)


def _split_module_dicts():
    '''
    Create a copy of __salt__ dictionary with module.function and module[function]

    Takes advantage of Jinja's syntactic sugar lookup:

    .. code-block::

        {{ salt.cmd.run('uptime') }}
    '''
    if not isinstance(__salt__, dict):
        return __salt__
    mod_dict = dict(__salt__)
    for module_func_name, mod_fun in six.iteritems(mod_dict.copy()):
        mod, fun = module_func_name.split('.', 1)
        if mod not in mod_dict:
            # create an empty object that we can add attributes to
            mod_dict[mod] = lambda: None
        setattr(mod_dict[mod], fun, mod_fun)
    return mod_dict


def render(template_file, saltenv='base', sls='', argline='',
                          context=None, tmplpath=None, **kws):
    '''
    Render the template_file, passing the functions and grains into the
    Jinja rendering system.

    :rtype: string
    '''
    from_str = argline == '-s'
    if not from_str and argline:
        raise SaltRenderError(
                'Unknown renderer option: {opt}'.format(opt=argline)
        )

    tmp_data = salt.utils.templates.JINJA(template_file,
                                          to_str=True,
                                          salt=_split_module_dicts(),
                                          grains=__grains__,
                                          opts=__opts__,
                                          pillar=__pillar__,
                                          saltenv=saltenv,
                                          sls=sls,
                                          context=context,
                                          tmplpath=tmplpath,
                                          **kws)
    if not tmp_data.get('result', False):
        raise SaltRenderError(
                tmp_data.get('data', 'Unknown render error in jinja renderer')
        )
    return StringIO(tmp_data['data'])
