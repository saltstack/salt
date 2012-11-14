from __future__ import absolute_import

# Import Salt libs
from salt.exceptions import SaltRenderError
import salt.utils.templates



def render(template_file, env='', sls='', context=None, **kws):
    '''
    Render the template_file, passing the functions and grains into the
    Jinja rendering system.

    :rtype: string
    '''
    tmp_data = salt.utils.templates.jinja(template_file, to_str=True,
                    salt=__salt__,
                    grains=__grains__,
                    opts=__opts__,
                    pillar=__pillar__,
                    env=env,
                    sls=sls,
                    context=context)
    if not tmp_data.get('result', False):
        raise SaltRenderError(tmp_data.get('data',
            'Unknown render error in jinja renderer'))
    return tmp_data['data']

