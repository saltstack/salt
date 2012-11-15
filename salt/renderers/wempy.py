'''
Process a sls file with the Wempy templating engine

'''

# Import Salt libs
from salt.exceptions import SaltRenderError
import salt.utils.templates


def render(template_file, env='', sls='', context=None, **kws):
    '''
    Render the data passing the functions and grains into the rendering system

    Renderer options:

        -s    Interpret renderer input as a string rather than as a file path.

    '''
    if argline == '-s':
        from_str = True
    elif argline:
        raise SaltRenderError(
                  'Unknown renderer option: {opt}'.format(opt=argline)
              )
    tmp_data = salt.utils.templates.wempy(
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
            'Unknown render error in the wempy renderer'))
    return tmp_data['data']
