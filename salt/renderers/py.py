'''
Pure python state renderer

The sls file should contain a function called ``run`` which returns high state
data
'''

# Import python libs
import os

# Import salt libs
from salt.exceptions import SaltRenderError
import salt.utils.templates


def render(template, env='', sls='', tmplpath=None, **kws):
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
            __grains__=__grains__,
            __opts__=__opts__,
            __pillar__=__pillar__,
            __env__=env,
            __sls__=sls,
            **kws)
    if not tmp_data.get('result', False):
        raise SaltRenderError(tmp_data.get('data',
            'Unknown render error in py renderer'))

    return tmp_data['data']
