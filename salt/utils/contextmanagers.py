'''
Some useful context managers used by salt
'''

from contextlib import contextmanager


# This context manager have been added to python3.4
# Probably, it will be backported to python2
@contextmanager
def ignored(*exceptions):
    '''
    Context manager to ignore specified exceptions

    with ignored(OSError):
        os.remove(somefile)
    '''
    try:
        yield
    except exceptions:
        pass
