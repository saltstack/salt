'''
Pure python state renderer, the sls file should contain a function called sls
which returns high state data
'''

# Import python libs
import imp
import os

def render(template):
    '''
    Render the python module's components
    '''
    if not os.path.isfile(template):
        return {}
    try:
        mod = imp.load_source(
                os.path.basename(template).split('.')[0],
                template
                )
        mod.salt = __salt__
        mod.grains = __grains__
        return mod.sls()
    except:
        return {}
