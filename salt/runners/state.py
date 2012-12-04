'''
Execute overstate functions
'''

# Import Salt libs
import salt.overstate
import salt.output

def over(env='base', os_fn=None):
    '''
    Execute an overstate sequence to orchestrate the executing of states
    over a group of systems
    '''
    overstate = salt.overstate.OverState(__opts__, env, os_fn)
    for stage in overstate.stages_iter():
        if isinstance(stage, dict):
            # This is highstate data
            for key, val in stage.items():
                salt.output.display_output(
                        {key: val},
                        'highstate',
                        opts=__opts__)
        elif isinstance(stage, list):
            # This is a stage
            salt.output.display_output(stage, 'overstatestage', opts=__opts__)
    return overstate.over_run

def show_stages(env='base', os_fn=None):
    '''
    Display the stage data to be executed
    '''
    overstate = salt.overstate.OverState(__opts__, env, os_fn)
    salt.output.display_output(
            overstate.over,
            'overstatestage',
            opts=__opts__)
    return overstate.over
