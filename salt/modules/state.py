'''
Control the state system on the minion
'''

import salt.state


__outputter__ = {
                 'highstate': 'highstate',
                 }


def low(data):
    '''
    Execute a single low data call
    This function is mostly intended for testing the state system

    CLI Example::

        salt '*' state.low '{"state": "pkg", "fun": "installed", "name": "vi"}'
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

    CLI Example::

        salt '*' state.high '{"vim": {"pkg": ["installed"]}}'
    '''
    st_ = salt.state.State(__opts__)
    return st_.call_high(data)


def template(tem):
    '''
    Execute the information stored in a template file on the minion

    CLI Example::

        salt '*' state.template '<Path to template on the minion>'
    '''
    st_ = salt.state.State(__opts__)
    return st_.call_template(tem)


def template_str(tem):
    '''
    Execute the information stored in a template file on the minion

    CLI Example::

        salt '*' state.template_str '<Template String>'
    '''
    st_ = salt.state.State(__opts__)
    return st_.call_template_str(tem)


def highstate():
    '''
    Retrive the state data from the salt master for this minion and execute it

    CLI Example::

        salt '*' state.highstate
    '''
    st_ = salt.state.HighState(__opts__)
    return st_.call_highstate()


def show_highstate():
    '''
    Retrive the highstate data from the salt master and display it

    CLI Example::

        salt '*' state.show_highstate
    '''
    st_ = salt.state.HighState(__opts__)
    return st_.compile_highstate()


def show_lowstate():
    '''
    List out the low data that will be applied to this minion

    CLI Example::

        salt '*' show_lowstate
    '''
    st_ = salt.state.HighState(__opts__)
    return st_.compile_low_chunks()
