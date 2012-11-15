from __future__ import absolute_import

import salt.utils.templates
from salt.exceptions import SaltRenderError

def render(template_file, env='', sls='', argline='', context=None, **kws):
    '''
    Renderer options:

        -s    Interpret renderer input as a string rather than as a file path.

    '''
    if argline == '-s':
        from_str = True
    elif argline:
        raise SaltRenderError(
                  'Unknown renderer option: {opt}'.format(opt=argline)
              )
    tmp_data = salt.utils.templates.mako(
                    template_file, from_str, to_str=True,
                    salt=__salt__,
                    grains=__grains__,
                    opts=__opts__,
                    pillar=__pillar__,
                    env=env,
                    sls=sls,
                    context=context)
    if not tmp_data.get('result', False):
        raise SaltRenderError(tmp_data.get('data',
            'Unknown render error in mako renderer'))
    return tmp_data['data']




