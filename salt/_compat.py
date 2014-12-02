# -*- coding: utf-8 -*-
'''
Salt compatibility code
'''
# pylint: disable=import-error,unused-import

# Import python libs
import sys
import types

# Import 3rd-party libs
from salt.ext.six import binary_type, string_types, text_type
from salt.ext.six.moves import cStringIO, StringIO

try:
    import cPickle as pickle
except ImportError:
    import pickle
try:
    # Python >2.5
    import xml.etree.cElementTree as ElementTree
except ImportError:
    try:
        # Python >2.5
        import xml.etree.ElementTree as ElementTree
    except ImportError:
        try:
            # normal cElementTree install
            import elementtree.cElementTree as ElementTree
        except ImportError:
            try:
                # normal ElementTree install
                import elementtree.ElementTree as ElementTree
            except ImportError:
                raise


# True if we are running on Python 3.
PY3 = sys.version_info[0] == 3


if PY3:
    import builtins
    exceptions = builtins  # pylint: disable=E0602
else:
    import exceptions  # pylint: disable=W0403


def text_(s, encoding='latin-1', errors='strict'):
    '''
    If ``s`` is an instance of ``binary_type``, return
    ``s.decode(encoding, errors)``, otherwise return ``s``
    '''
    if isinstance(s, binary_type):
        return s.decode(encoding, errors)
    return s


def bytes_(s, encoding='latin-1', errors='strict'):
    '''
    If ``s`` is an instance of ``text_type``, return
    ``s.encode(encoding, errors)``, otherwise return ``s``
    '''
    if isinstance(s, text_type):
        return s.encode(encoding, errors)
    return s


if PY3:
    def ascii_native_(s):
        if isinstance(s, text_type):
            s = s.encode('ascii')
        return str(s, 'ascii', 'strict')
else:
    def ascii_native_(s):
        if isinstance(s, text_type):
            s = s.encode('ascii')
        return str(s)

ascii_native_.__doc__ = '''
Python 3: If ``s`` is an instance of ``text_type``, return
``s.encode('ascii')``, otherwise return ``str(s, 'ascii', 'strict')``

Python 2: If ``s`` is an instance of ``text_type``, return
``s.encode('ascii')``, otherwise return ``str(s)``
'''


if PY3:
    def native_(s, encoding='latin-1', errors='strict'):
        '''
        If ``s`` is an instance of ``text_type``, return
        ``s``, otherwise return ``str(s, encoding, errors)``
        '''
        if isinstance(s, text_type):
            return s
        return str(s, encoding, errors)
else:
    def native_(s, encoding='latin-1', errors='strict'):
        '''
        If ``s`` is an instance of ``text_type``, return
        ``s.encode(encoding, errors)``, otherwise return ``str(s)``
        '''
        if isinstance(s, text_type):
            return s.encode(encoding, errors)
        return str(s)

native_.__doc__ = '''
Python 3: If ``s`` is an instance of ``text_type``, return ``s``, otherwise
return ``str(s, encoding, errors)``

Python 2: If ``s`` is an instance of ``text_type``, return
``s.encode(encoding, errors)``, otherwise return ``str(s)``
'''


def string_io(data=None):  # cStringIO can't handle unicode
    '''
    Pass data through to stringIO module and return result
    '''
    try:
        return cStringIO(bytes(data))
    except (UnicodeEncodeError, TypeError):
        return StringIO(data)
