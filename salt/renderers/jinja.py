from __future__ import absolute_import

# Import Salt libs
from salt.exceptions import SaltRenderError
import salt.utils.templates



def render(template_file, env='', sls='', argline='', context=None, **kws):
    '''
    Render the template_file, passing the functions and grains into the
    Jinja rendering system.

    Renderer options:

        -s    Interpret renderer input as a string rather than as a file path.

    '''
    from_str = argline=='-s'
    if not from_str and argline:
        raise SaltRenderError(
                  'Unknown renderer option: {opt}'.format(opt=argline)
              )
    tmp_data = salt.utils.templates.jinja(
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
            'Unknown render error in jinja renderer'))
    return tmp_data['data']

