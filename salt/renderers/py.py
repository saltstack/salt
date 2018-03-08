# -*- coding: utf-8 -*-
'''
Pure python state renderer

The SLS file should contain a function called ``run`` which returns high state
data.
The highstate data is a dictionary containing identifiers as keys, and execution
dictionaries as values. For example the following state declaration in YAML::

    common_packages:
      pkg.installed:
       - pkgs:
          - curl
          - vim


tranlastes to::

     {'common_packages': {'pkg.installed': [{'pkgs': ['curl', 'vim']}]}}

In this module, a few objects are defined for you, giving access to Salt's
execution functions, grains, pillar, etc. They are:

- ``__salt__`` - :ref:`Execution functions <all-salt.modules>` (i.e.
  ``__salt__['test.echo']('foo')``)
- ``__grains__`` - :ref:`Grains <targeting-grains>` (i.e. ``__grains__['os']``)
- ``__pillar__`` - :ref:`Pillar data <pillar>` (i.e. ``__pillar__['foo']``)
- ``__opts__`` - Minion configuration options
- ``__env__`` - The effective salt fileserver environment (i.e. ``base``). Also
  referred to as a "saltenv". ``__env__`` should not be modified in a pure
  python SLS file. To use a different environment, the environment should be
  set when executing the state. This can be done in a couple different ways:

  - Using the ``saltenv`` argument on the salt CLI (i.e. ``salt '*' state.sls foo.bar.baz saltenv=env_name``).
  - By adding a ``saltenv`` argument to an individual state within the SLS
    file. In other words, adding a line like this to the state's data
    structure: ``{'saltenv': 'env_name'}``

- ``__sls__`` - The SLS path of the file. For example, if the root of the base
  environment is ``/srv/salt``, and the SLS file is
  ``/srv/salt/foo/bar/baz.sls``, then ``__sls__`` in that file will be
  ``foo.bar.baz``.

The global contet `data` (same as context ``{{ data }}` ` for states written with Jinja + YAML.
The following YAML + Jinja state declaration::

    {% if data['id'] == 'mysql1' %}
    highstate_run:
      local.state.apply:
        - tgt: mysql1
    {% endif %}

Translate to::

    if data['id'] == 'mysql1':
        return {'highstate_run': {'local.state.apply': [{'tgt': 'mysql1'}]}}

.. code-block:: python
   :linenos:

    #!py

    def run():
        config = {}

        if __grains__['os'] == 'Ubuntu':
            user = 'ubuntu'
            group = 'ubuntu'
            home = '/home/{0}'.format(user)
        else:
            user = 'root'
            group = 'root'
            home = '/root/'

        config['s3cmd'] = {
            'pkg': [
                'installed',
                {'name': 's3cmd'},
            ],
        }

        config[home + '/.s3cfg'] = {
            'file.managed': [
                {'source': 'salt://s3cfg/templates/s3cfg'},
                {'template': 'jinja'},
                {'user': user},
                {'group': group},
                {'mode': 600},
                {'context': {
                    'aws_key': __pillar__['AWS_ACCESS_KEY_ID'],
                    'aws_secret_key': __pillar__['AWS_SECRET_ACCESS_KEY'],
                    },
                },
            ],
        }

        return config

'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import os

# Import salt libs
from salt.exceptions import SaltRenderError
import salt.utils.templates


def render(template, saltenv='base', sls='', tmplpath=None, **kws):
    '''
    Render the python module's components

    :rtype: string
    '''
    template = tmplpath
    if not os.path.isfile(template):
        raise SaltRenderError('Template {0} is not a file!'.format(template))

    tmp_data = salt.utils.templates.py(
            template,
            True,
            __salt__=__salt__,
            salt=__salt__,
            __grains__=__grains__,
            grains=__grains__,
            __opts__=__opts__,
            opts=__opts__,
            __pillar__=__pillar__,
            pillar=__pillar__,
            __env__=saltenv,
            saltenv=saltenv,
            __sls__=sls,
            sls=sls,
            **kws)
    if not tmp_data.get('result', False):
        raise SaltRenderError(tmp_data.get('data',
            'Unknown render error in py renderer'))

    return tmp_data['data']
