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
    overstate.stages()
    salt.output.display_output(overstate.over_run, 'pprint', opts=__opts__)
    return overstate.over_run

def show_stages(env='base', os_fn=None):
    '''
    Display the stage data to be executed
    '''
    overstate = salt.overstate.OverState(__opts__, env, os_fn)
    salt.output.display_output(overstate.over, 'pprint', opts=__opts__)
    return overstate.over
