from __future__ import absolute_import
from StringIO import StringIO

import salt.utils.templates
from salt.exceptions import SaltRenderError

def render(template_file, env='', sls='', context=None, tmplpath=None, **kws):
    '''
    Render the template_file, passing the functions and grains into the
    Mako rendering system.

    :rtype: string
    '''
    tmp_data = salt.utils.templates.mako(template_file, to_str=True,
                    salt=__salt__,
                    grains=__grains__,
                    opts=__opts__,
                    pillar=__pillar__,
                    env=env,
                    sls=sls,
                    context=context,
                    tmplpath=tmplpath)
    if not tmp_data.get('result', False):
        raise SaltRenderError(tmp_data.get('data',
            'Unknown render error in mako renderer'))
    return StringIO(tmp_data['data'])
