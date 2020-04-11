# -*- coding: utf-8 -*-
"""
Salt compatibility code
"""
# pylint: disable=import-error,unused-import,invalid-name,W0231,W0233

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import binascii
import logging
import sys

# Import 3rd-party libs
from salt.exceptions import SaltException
from salt.ext.six import binary_type, integer_types, string_types, text_type
from salt.ext.six.moves import StringIO, cStringIO

log = logging.getLogger(__name__)

try:
    # Python >2.5
    import xml.etree.cElementTree as ElementTree
except Exception:  # pylint: disable=broad-except
    try:
        # Python >2.5
        import xml.etree.ElementTree as ElementTree
    except Exception:  # pylint: disable=broad-except
        try:
            # normal cElementTree install
            import elementtree.cElementTree as ElementTree
        except Exception:  # pylint: disable=broad-except
            try:
                # normal ElementTree install
                import elementtree.ElementTree as ElementTree
            except Exception:  # pylint: disable=broad-except
                ElementTree = None


# True if we are running on Python 3.
PY3 = sys.version_info.major == 3


if PY3:
    import builtins

    exceptions = builtins
else:
    import exceptions


if ElementTree is not None:
    if not hasattr(ElementTree, "ParseError"):

        class ParseError(Exception):
            """
            older versions of ElementTree do not have ParseError
            """

        ElementTree.ParseError = ParseError


def text_(s, encoding="latin-1", errors="strict"):
    """
    If ``s`` is an instance of ``binary_type``, return
    ``s.decode(encoding, errors)``, otherwise return ``s``
    """
    return s.decode(encoding, errors) if isinstance(s, binary_type) else s


def bytes_(s, encoding="latin-1", errors="strict"):
    """
    If ``s`` is an instance of ``text_type``, return
    ``s.encode(encoding, errors)``, otherwise return ``s``
    """
    return s.encode(encoding, errors) if isinstance(s, text_type) else s


def ascii_native_(s):
    """
    Python 3: If ``s`` is an instance of ``text_type``, return
    ``s.encode('ascii')``, otherwise return ``str(s, 'ascii', 'strict')``

    Python 2: If ``s`` is an instance of ``text_type``, return
    ``s.encode('ascii')``, otherwise return ``str(s)``
    """
    if isinstance(s, text_type):
        s = s.encode("ascii")

    return str(s, "ascii", "strict") if PY3 else s


def native_(s, encoding="latin-1", errors="strict"):
    """
    Python 3: If ``s`` is an instance of ``text_type``, return ``s``, otherwise
    return ``str(s, encoding, errors)``

    Python 2: If ``s`` is an instance of ``text_type``, return
    ``s.encode(encoding, errors)``, otherwise return ``str(s)``
    """
    if PY3:
        out = s if isinstance(s, text_type) else str(s, encoding, errors)
    else:
        out = s.encode(encoding, errors) if isinstance(s, text_type) else str(s)

    return out


def string_io(data=None):  # cStringIO can't handle unicode
    """
    Pass data through to stringIO module and return result
    """
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
    """
    Represent and manipulate single IPv6 Addresses.
    Scope-aware version
    """

    def __init__(self, address):
        """
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
        """
        # pylint: disable-all
        if not hasattr(self, "_is_packed_binary"):
            # This method (below) won't be around for some Python 3 versions
            # and we need check this differently anyway
            self._is_packed_binary = lambda p: isinstance(p, bytes)
        # pylint: enable-all
        if isinstance(address, string_types) and "%" in address:
            buff = address.split("%")
            if len(buff) != 2:
                raise SaltException('Invalid IPv6 address: "{}"'.format(address))
            address, self.__scope = buff
        else:
            self.__scope = None

        if sys.version_info.major == 2:
            ipaddress._BaseAddress.__init__(self, address)
            ipaddress._BaseV6.__init__(self, address)
        else:
            # Python 3.4 fix. Versions higher are simply not affected
            # https://github.com/python/cpython/blob/3.4/Lib/ipaddress.py#L543-L544
            self._version = 6
            self._max_prefixlen = ipaddress.IPV6LENGTH

        # Efficient constructor from integer.
        if isinstance(address, integer_types):
            self._check_int_address(address)
            self._ip = address
        elif self._is_packed_binary(address):
            self._check_packed_address(address, 16)
            self._ip = int(binascii.hexlify(address), 16)
        else:
            address = str(address)
            if "/" in address:
                raise ipaddress.AddressValueError(
                    "Unexpected '/' in {}".format(address)
                )
            self._ip = self._ip_int_from_string(address)

    def _is_packed_binary(self, data):
        """
        Check if data is hexadecimal packed

        :param data:
        :return:
        """
        packed = False
        if isinstance(data, bytes) and len(data) == 16 and b":" not in data:
            try:
                packed = bool(int(binascii.hexlify(data), 16))
            except ValueError:
                pass

        return packed

    @property
    def scope(self):
        """
        Return scope of IPv6 address.

        :return:
        """
        return self.__scope

    def __str__(self):
        return text_type(
            self._string_from_ip_int(self._ip)
            + ("%" + self.scope if self.scope is not None else "")
        )


class IPv6InterfaceScoped(ipaddress.IPv6Interface, IPv6AddressScoped):
    """
    Update
    """

    def __init__(self, address):
        if (
            PY3
            and isinstance(address, (bytes, int))
            or not PY3
            and isinstance(address, int)
        ):
            IPv6AddressScoped.__init__(self, address)
            self.network = ipaddress.IPv6Network(self._ip)
            self._prefixlen = self._max_prefixlen
            return

        addr = ipaddress._split_optional_netmask(address)
        IPv6AddressScoped.__init__(self, addr[0])
        self.network = ipaddress.IPv6Network(address, strict=False)
        self.netmask = self.network.netmask
        self._prefixlen = self.network._prefixlen
        self.hostmask = self.network.hostmask


if ipaddress:
    ipaddress.IPv6Address = IPv6AddressScoped
    if sys.version_info.major == 2:
        ipaddress.IPv6Interface = IPv6InterfaceScoped
