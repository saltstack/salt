import pickle

from salt.defaults import _Constant


def test_pickle_constants():
    """
    That that we can pickle and unpickle constants.
    """
    constant = _Constant("Foo", 123)
    sdata = pickle.dumps(constant)
    odata = pickle.loads(sdata)
    assert odata == constant
