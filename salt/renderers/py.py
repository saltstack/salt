# -*- coding: utf-8 -*-
'''
Pure python state renderer

The sls file should contain a function called ``run`` which returns high state
data

In this module, a few objects are defined for you, including the usual
(with``__`` added) ``__salt__`` dictionary, ``__grains__``,
``__pillar__``, ``__opts__``, ``__env__``, and ``__sls__``.

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
