def arg(*args, **kwargs):
    '''
    Output the given args and kwargs
    '''
    ret = {
        'args': args,
        'kwargs': kwargs,
    }
    print ret
    return ret
