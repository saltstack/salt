from StringIO import StringIO

# Import Salt libs
from salt.exceptions import SaltRenderError
import salt.utils.templates


def render(template_file, env='', sls='', argline='', context=None, **kws):
    '''
    Render the data passing the functions and grains into the rendering system

    :rtype: string
    '''
    tmp_data = salt.utils.templates.wempy(template_file, to_str=True,
            salt=__salt__,
            grains=__grains__,
            opts=__opts__,
            pillar=__pillar__,
            env=env,
            sls=sls,
            context=context)
    if not tmp_data.get('result', False):
        raise SaltRenderError(tmp_data.get('data',
            'Unknown render error in the wempy renderer'))
    return StringIO(tmp_data['data'])
