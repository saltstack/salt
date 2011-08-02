'''
Module for issuing alerts from the monitor service.
Examples:
    alert.notice 'things are going great'
    alert.warning 'the {} is wobbling' turboencabulator
    alert.error 'the {1} is {0:.1f} mm from failure' 12.34 'wain shaft'
'''

__opts__ = {}

def _alert(level, msg, *args, **kwargs):
    return "{}: {}".format(level, msg.format(*args, **kwargs))

def notice(msg, *args, **kwargs):
    '''
    Send a 'notice' alert.
    msg = a message optionally containing string.format() '{}' references
    args = positional args passed to string.format()
    kwargs = keyword args passed to string.format()
    '''
    return _alert("NOTICE", msg, *args, **kwargs)

def warning(msg, *args, **kwargs):
    '''
    Send a 'warning' alert.
    msg = a message optionally containing string.format() '{}' references
    args = positional args passed to string.format()
    kwargs = keyword args passed to string.format()
    '''
    return _alert("WARNING", msg, *args, **kwargs)

def error(msg, *args, **kwargs):
    '''
    Send an 'error' alert.
    msg = a message optionally containing string.format() '{}' references
    args = positional args passed to string.format()
    kwargs = keyword args passed to string.format()
    '''
    return _alert("ERROR", msg, *args, **kwargs)

def critical(msg, *args, **kwargs):
    '''
    Send a 'critical' alert.
    msg = a message optionally containing string.format() '{}' references
    args = positional args passed to string.format()
    kwargs = keyword args passed to string.format()
    '''
    return _alert("FATAL", msg, *args, **kwargs)

def fatal(msg, *args, **kwargs):
    '''
    Send a 'fatal' alert.
    msg = a message optionally containing string.format() '{}' references
    args = positional args passed to string.format()
    kwargs = keyword args passed to string.format()
    '''
    return _alert("FATAL", msg, *args, **kwargs)
