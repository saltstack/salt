'''
Control the state system on the minion
'''
# Import Python modules
import os

# Import salt modules
import salt.state

def low(data):
    '''
    Execute a single low data call
    This function is mostly intended for testing the state system

    CLI Example:
    salt '*' state.low '{"state": "pkg", "fun": "installed", "name": "vim"}'
    '''
    st_ = salt.state.State(__opts__)
    err = st_.verify_data(data)
    if err:
        return err
    return st_.call(data)

def high(data):
    '''
    Execute the compound calls stored in a single set of high data
    This function is mostly intended for testing the state system

    CLI Example:
    salt '*' state.high '{"vim": {"pkg": ["installed"]}}'
    '''
    st_ = salt.state.State(__opts__)
    return st_.call_high(data)

def template(tem):
    '''
    Execute the information stored in a template file on the minion

    CLI Example:
    salt '*' state.template '<Path to template on the minion>'
    '''
    st_ = salt.state.State(__opts__)
    return st_.call_template(tem)
    
def template_str(tem):
    '''
    Execute the information stored in a template file on the minion

    CLI Example:
    salt '*' state.template_str '<Template String>'
    '''
    st_ = salt.state.State(__opts__)
    return st_.call_template_str(tem)
    
