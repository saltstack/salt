# coding: utf-8
from salt.msgpack.__version__ import *
from salt.msgpack._msgpack import *

# alias for compatibility to simplejson/marshal/pickle.
load = unpack
loads = unpackb

dump = pack
dumps = packb

def packs(*args, **kw):
    from warnings import warn
    warn("msgpack.packs() is deprecated. Use packb() instead.", DeprecationWarning)
    return packb(*args, **kw)

def unpacks(*args, **kw):
    from warnings import warn
    warn("msgpack.unpacks() is deprecated. Use unpackb() instead.", DeprecationWarning)
    return unpackb(*args, **kw)
