'''
Module for issuing alerts from the monitor service.
The arguments are arbitrary and only interpreted by the alert receiver.
Examples:
    alert.notice  'things are going great'
    alert.warning email 'the ${value} is wobbling'
    alert.error   netops pager 'the ${key} is {value:.1f} mm from failure'
'''

__opts__ = {}

def _alert(level, args):
    return [level] + list(args)

def notice(*args):
    '''
    Send a 'notice' alert.
    args = the alert message or array
    '''
    return _alert("NOTICE", args)

def warning(*args):
    '''
    Send a 'warning' alert.
    args = the alert message or array
    '''
    return _alert("WARNING", args)

def error(*args):
    '''
    Send an 'error' alert.
    args = the alert message or array
    '''
    return _alert("ERROR", args)

def critical(*args):
    '''
    Send a 'critical' alert.
    args = the alert message or array
    '''
    return _alert("FATAL", args)

def fatal(*args):
    '''
    Send a 'fatal' alert.
    args = the alert message or array
    '''
    return _alert("FATAL", args)
