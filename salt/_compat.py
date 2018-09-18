# -*- coding: utf-8 -*-
'''
Salt compatibility code
'''
# pylint: disable=import-error,unused-import,invalid-name

# Import python libs
from __future__ import absolute_import, unicode_literals, print_function
import sys
import types

# Import 3rd-party libs
from salt.exceptions import SaltException
from salt.ext.six import binary_type, string_types, text_type
from salt.ext.six.moves import cStringIO, StringIO

HAS_XML = True
try:
    # Python >2.5
    import xml.etree.cElementTree as ElementTree
except Exception:
    try:
        # Python >2.5
        import xml.etree.ElementTree as ElementTree
    except Exception:
        try:
            # normal cElementTree install
            import elementtree.cElementTree as ElementTree
        except Exception:
            try:
                # normal ElementTree install
                import elementtree.ElementTree as ElementTree
            except Exception:
                ElementTree = None
                HAS_XML = False


# True if we are running on Python 3.
PY3 = sys.version_info.major == 3


if PY3:
    import builtins
    exceptions = builtins
else:
    import exceptions


if HAS_XML:
    if not hasattr(ElementTree, 'ParseError'):
        class ParseError(Exception):
            '''
            older versions of ElementTree do not have ParseError
            '''
            pass

        ElementTree.ParseError = ParseError


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
        '''
        Python 3 handler.

        :param s:
        :return:
        '''
        if isinstance(s, text_type):
            s = s.encode('ascii')
        return str(s, 'ascii', 'strict')
else:
    def ascii_native_(s):
        '''
        Python 2 handler.

        :param s:
        :return:
        '''
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


try:
    if PY3:
        import ipaddress
    else:
        import salt.ext.ipaddress as ipaddress
except ImportError:
    ipaddress = None


class IPv6AddressScoped(ipaddress.IPv6Address):
    '''
    Represent and manipulate single IPv6 Addresses.
    Scope-aware version
    '''
    def __init__(self, address):
        '''
        Instantiate a new IPv6 address object. Scope is moved to an attribute 'scope'.

        Args:
            address: A string or integer representing the IP

              Additionally, an integer can be passed, so
              IPv6Address('2001:db8::') == IPv6Address(42540766411282592856903984951653826560)
              or, more generally
              IPv6Address(int(IPv6Address('2001:db8::'))) == IPv6Address('2001:db8::')

        Raises:
            AddressValueError: If address isn't a valid IPv6 address.

        :param address:
        '''
        if '%' in address:
            buff = address.split('%')
            if len(buff) != 2:
                raise SaltException('Invalid IPv6 address: "{}"'.format(address))
            address, self.__scope = buff
        else:
            self.__scope = None

        ipaddress._BaseAddress.__init__(self, address)
        ipaddress._BaseV6.__init__(self, address)

        # Efficient constructor from integer.
        if isinstance(address, int):
            self._check_int_address(address)
            self._ip = address
            return

        if isinstance(address, bytes):
            self._check_packed_address(address, 16)
            self._ip = ipaddress._int_from_bytes(address, 'big')
            return

        addr_str = str(address)
        self._ip = self._ip_int_from_string(addr_str)

    @property
    def scope(self):
        '''
        Return scope of IPv6 address.

        :return:
        '''
        return self.__scope


if ipaddress:
    ipaddress.IPv6Address = IPv6AddressScoped
