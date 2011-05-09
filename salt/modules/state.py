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
    '''
    st_ = salt.state.State(__opts__)
    err = st_.verify_data(data)
    if err:
        return err
    return st_.call(data)

def high(data):
    '''
    Execute the compound calls stored in a single set of high data
    '''
    st_ = salt.state.State(__opts__)
    return st_.call_high(data)

def template(tem):
    '''
    Execute the information stored in a template file on the minion
    '''
    st_ = salt.state.State(__opts__)
    return st_.call_template(tem)
    
def template_str(tem):
    '''
    Execute the information stored in a template file on the minion
    '''
    st_ = salt.state.State(__opts__)
    return st_.call_template_str(tem)
    
