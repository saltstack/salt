def _no_op(name, **kws):
    '''
    No-op state to support state config via the stateconf renderer.
    '''
    return dict(name=name, result=True, changes={}, comment='')

set = context = _no_op
