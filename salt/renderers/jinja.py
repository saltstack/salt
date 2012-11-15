'''
The default templating engine, process sls file with the jinja2 templating engine.

This renderer will take a sls file authored as a jinja2 template, render it, and
return the rendered result as a string.
'''
from __future__ import absolute_import

# Import Salt libs
from salt.exceptions import SaltRenderError
import salt.utils.templates



def render(template_file, env='', sls='', argline='', context=None, **kws):
    '''
    Render the template_file, passing the functions and grains into the
    rendering system. Return rendered content as a string.

    Renderer options:

        -s    Interpret renderer input as a string rather than as a file path.

    '''
    if argline == '-s':
        from_str = True
    elif argline:
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

