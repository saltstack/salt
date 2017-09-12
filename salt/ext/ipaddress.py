'''
Python 2.[67] port of Python 3.4's ipaddress module

Almost verbatim copy of the core lib, with compatibility changes
Source: https://bitbucket.org/kwi/py2-ipaddress/
'''
# pylint: skip-file

# List of compatibility changes:

# Python 3 uses only new-style classes.
# s/class \(\w\+\):/class \1(object):/

# Use iterator versions of map and range:
from itertools import imap as map
range = xrange

# Except that xrange only supports machine integers, not longs, so...
def long_range(start, end):
    while start < end:
        yield start
        start += 1

# This backport uses bytearray instead of bytes, as bytes is the same
# as str in Python 2.7.
bytes = bytearray

# Python 2 does not support exception chaining.
# s/ from None$//

# When checking for instances of int, also allow Python 2's long.
_builtin_isinstance = isinstance

def isinstance(val, types):
    if types is int:
        types = (int, long)
    elif type(types) is tuple and int in types:
        types += (long,)
    return _builtin_isinstance(val, types)

# functools.lru_cache is Python 3.2+ only.
# /@functools.lru_cache()/d

# int().to_bytes is Python 3.2+ only.
# s/\(\w+\)\.to_bytes(/_int_to_bytes(\1, /
def _int_to_bytes(self, length, byteorder, signed=False):
    assert byteorder == 'big' and signed is False
    if self < 0 or self >= 256**length:
        raise OverflowError()
    return bytearray(('%0*x' % (length * 2, self)).decode('hex'))

# int.from_bytes is Python 3.2+ only.
# s/int\.from_bytes(/_int_from_bytes(/g
def _int_from_bytes(what, byteorder, signed=False):
    assert byteorder == 'big' and signed is False
    return int(str(bytearray(what)).encode('hex'), 16)

# Python 2.6 has no int.bit_length()
if hasattr(int, 'bit_length'):
    _int_bit_length = lambda i: i.bit_length()
else:
    _int_bit_length = lambda i: len(bin(abs(i))) - 2

# ----------------------------------------------------------------------------


# Copyright 2007 Google Inc.
#  Licensed to PSF under a Contributor Agreement.

"""A fast, lightweight IPv4/IPv6 manipulation library in Python.

This library is used to create/poke/manipulate IPv4 and IPv6 addresses
and networks.

"""

__version__ = '1.0'


import functools

IPV4LENGTH = 32
IPV6LENGTH = 128

class AddressValueError(ValueError):
    """A Value Error related to the address."""


class NetmaskValueError(ValueError):
    """A Value Error related to the netmask."""


def ip_address(address):
    """Take an IP string/int and return an object of the correct type.

    Args:
        address: A string or integer, the IP address.  Either IPv4 or
          IPv6 addresses may be supplied; integers less than 2**32 will
          be considered to be IPv4 by default.

    Returns:
        An IPv4Address or IPv6Address object.

    Raises:
        ValueError: if the *address* passed isn't either a v4 or a v6
          address

    """
    try:
        return IPv4Address(address)
    except (AddressValueError, NetmaskValueError):
        pass

    try:
        return IPv6Address(address)
    except (AddressValueError, NetmaskValueError):
        pass

    raise ValueError('%r does not appear to be an IPv4 or IPv6 address' %
                     address)


def ip_network(address, strict=True):
    """Take an IP string/int and return an object of the correct type.

    Args:
        address: A string or integer, the IP network.  Either IPv4 or
          IPv6 networks may be supplied; integers less than 2**32 will
          be considered to be IPv4 by default.

    Returns:
        An IPv4Network or IPv6Network object.

    Raises:
        ValueError: if the string passed isn't either a v4 or a v6
          address. Or if the network has host bits set.

    """
    try:
        return IPv4Network(address, strict)
    except (AddressValueError, NetmaskValueError):
        pass

    try:
        return IPv6Network(address, strict)
    except (AddressValueError, NetmaskValueError):
        pass

    raise ValueError('%r does not appear to be an IPv4 or IPv6 network' %
                     address)


def ip_interface(address):
    """Take an IP string/int and return an object of the correct type.

    Args:
        address: A string or integer, the IP address.  Either IPv4 or
          IPv6 addresses may be supplied; integers less than 2**32 will
          be considered to be IPv4 by default.

    Returns:
        An IPv4Interface or IPv6Interface object.

    Raises:
        ValueError: if the string passed isn't either a v4 or a v6
          address.

    Notes:
        The IPv?Interface classes describe an Address on a particular
        Network, so they're basically a combination of both the Address
        and Network classes.

    """
    try:
        return IPv4Interface(address)
    except (AddressValueError, NetmaskValueError):
        pass

    try:
        return IPv6Interface(address)
    except (AddressValueError, NetmaskValueError):
        pass

    raise ValueError('%r does not appear to be an IPv4 or IPv6 interface' %
                     address)


def v4_int_to_packed(address):
    """Represent an address as 4 packed bytes in network (big-endian) order.

    Args:
        address: An integer representation of an IPv4 IP address.

    Returns:
        The integer address packed as 4 bytes in network (big-endian) order.

    Raises:
        ValueError: If the integer is negative or too large to be an
          IPv4 IP address.

    """
    try:
        return _int_to_bytes(address, 4, 'big')
    except:
        raise ValueError("Address negative or too large for IPv4")


def v6_int_to_packed(address):
    """Represent an address as 16 packed bytes in network (big-endian) order.

    Args:
        address: An integer representation of an IPv6 IP address.

    Returns:
        The integer address packed as 16 bytes in network (big-endian) order.

    """
    try:
        return _int_to_bytes(address, 16, 'big')
    except:
        raise ValueError("Address negative or too large for IPv6")


def _split_optional_netmask(address):
    """Helper to split the netmask and raise AddressValueError if needed"""
    addr = str(address).split('/')
    if len(addr) > 2:
        raise AddressValueError("Only one '/' permitted in %r" % address)
    return addr


def _find_address_range(addresses):
    """Find a sequence of IPv#Address.

    Args:
        addresses: a list of IPv#Address objects.

    Returns:
        A tuple containing the first and last IP addresses in the sequence.

    """
    first = last = addresses[0]
    for ip in addresses[1:]:
        if ip._ip == last._ip + 1:
            last = ip
        else:
            break
    return (first, last)


def _count_righthand_zero_bits(number, bits):
    """Count the number of zero bits on the right hand side.

    Args:
        number: an integer.
        bits: maximum number of bits to count.

    Returns:
        The number of zero bits on the right hand side of the number.

    """
    if number == 0:
        return bits
    for i in range(bits):
        if (number >> i) & 1:
            return i
    # All bits of interest were zero, even if there are more in the number
    return bits


def summarize_address_range(first, last):
    """Summarize a network range given the first and last IP addresses.

    Example:
        >>> list(summarize_address_range(IPv4Address('192.0.2.0'),
        ...                              IPv4Address('192.0.2.130')))
        ...                                #doctest: +NORMALIZE_WHITESPACE
        [IPv4Network('192.0.2.0/25'), IPv4Network('192.0.2.128/31'),
         IPv4Network('192.0.2.130/32')]

    Args:
        first: the first IPv4Address or IPv6Address in the range.
        last: the last IPv4Address or IPv6Address in the range.

    Returns:
        An iterator of the summarized IPv(4|6) network objects.

    Raise:
        TypeError:
            If the first and last objects are not IP addresses.
            If the first and last objects are not the same version.
        ValueError:
            If the last object is not greater than the first.
            If the version of the first address is not 4 or 6.

    """
    if (not (isinstance(first, _BaseAddress) and
             isinstance(last, _BaseAddress))):
        raise TypeError('first and last must be IP addresses, not networks')
    if first.version != last.version:
        raise TypeError("%s and %s are not of the same version" % (
                         first, last))
    if first > last:
        raise ValueError('last IP address must be greater than first')

    if first.version == 4:
        ip = IPv4Network
    elif first.version == 6:
        ip = IPv6Network
    else:
        raise ValueError('unknown IP version')

    ip_bits = first._max_prefixlen
    first_int = first._ip
    last_int = last._ip
    while first_int <= last_int:
        nbits = min(_count_righthand_zero_bits(first_int, ip_bits),
                    _int_bit_length(last_int - first_int + 1) - 1)
        net = ip('%s/%d' % (first, ip_bits - nbits))
        yield net
        first_int += 1 << nbits
        if first_int - 1 == ip._ALL_ONES:
            break
        first = first.__class__(first_int)


def _collapse_addresses_recursive(addresses):
    """Loops through the addresses, collapsing concurrent netblocks.

    Example:

        ip1 = IPv4Network('192.0.2.0/26')
        ip2 = IPv4Network('192.0.2.64/26')
        ip3 = IPv4Network('192.0.2.128/26')
        ip4 = IPv4Network('192.0.2.192/26')

        _collapse_addresses_recursive([ip1, ip2, ip3, ip4]) ->
          [IPv4Network('192.0.2.0/24')]

        This shouldn't be called directly; it is called via
          collapse_addresses([]).

    Args:
        addresses: A list of IPv4Network's or IPv6Network's

    Returns:
        A list of IPv4Network's or IPv6Network's depending on what we were
        passed.

    """
    while True:
        last_addr = None
        ret_array = []
        optimized = False

        for cur_addr in addresses:
            if not ret_array:
                last_addr = cur_addr
                ret_array.append(cur_addr)
            elif (cur_addr.network_address >= last_addr.network_address and
                cur_addr.broadcast_address <= last_addr.broadcast_address):
                optimized = True
            elif cur_addr == list(last_addr.supernet().subnets())[1]:
                ret_array[-1] = last_addr = last_addr.supernet()
                optimized = True
            else:
                last_addr = cur_addr
                ret_array.append(cur_addr)

        addresses = ret_array
        if not optimized:
            return addresses


def collapse_addresses(addresses):
    """Collapse a list of IP objects.

    Example:
        collapse_addresses([IPv4Network('192.0.2.0/25'),
                            IPv4Network('192.0.2.128/25')]) ->
                           [IPv4Network('192.0.2.0/24')]

    Args:
        addresses: An iterator of IPv4Network or IPv6Network objects.

    Returns:
        An iterator of the collapsed IPv(4|6)Network objects.

    Raises:
        TypeError: If passed a list of mixed version objects.

    """
    i = 0
    addrs = []
    ips = []
    nets = []

    # split IP addresses and networks
    for ip in addresses:
        if isinstance(ip, _BaseAddress):
            if ips and ips[-1]._version != ip._version:
                raise TypeError("%s and %s are not of the same version" % (
                                 ip, ips[-1]))
            ips.append(ip)
        elif ip._prefixlen == ip._max_prefixlen:
            if ips and ips[-1]._version != ip._version:
                raise TypeError("%s and %s are not of the same version" % (
                                 ip, ips[-1]))
            try:
                ips.append(ip.ip)
            except AttributeError:
                ips.append(ip.network_address)
        else:
            if nets and nets[-1]._version != ip._version:
                raise TypeError("%s and %s are not of the same version" % (
                                 ip, nets[-1]))
            nets.append(ip)

    # sort and dedup
    ips = sorted(set(ips))
    nets = sorted(set(nets))

    while i < len(ips):
        (first, last) = _find_address_range(ips[i:])
        i = ips.index(last) + 1
        addrs.extend(summarize_address_range(first, last))

    return iter(_collapse_addresses_recursive(sorted(
        addrs + nets, key=_BaseNetwork._get_networks_key)))


def get_mixed_type_key(obj):
    """Return a key suitable for sorting between networks and addresses.

    Address and Network objects are not sortable by default; they're
    fundamentally different so the expression

        IPv4Address('192.0.2.0') <= IPv4Network('192.0.2.0/24')

    doesn't make any sense.  There are some times however, where you may wish
    to have ipaddress sort these for you anyway. If you need to do this, you
    can use this function as the key= argument to sorted().

    Args:
      obj: either a Network or Address object.
    Returns:
      appropriate key.

    """
    if isinstance(obj, _BaseNetwork):
        return obj._get_networks_key()
    elif isinstance(obj, _BaseAddress):
        return obj._get_address_key()
    return NotImplemented


class _TotalOrderingMixin(object):
    # Helper that derives the other comparison operations from
    # __lt__ and __eq__
    # We avoid functools.total_ordering because it doesn't handle
    # NotImplemented correctly yet (http://bugs.python.org/issue10042)
    def __eq__(self, other):
        raise NotImplementedError
    def __ne__(self, other):
        equal = self.__eq__(other)
        if equal is NotImplemented:
            return NotImplemented
        return not equal
    def __lt__(self, other):
        raise NotImplementedError
    def __le__(self, other):
        less = self.__lt__(other)
        if less is NotImplemented or not less:
            return self.__eq__(other)
        return less
    def __gt__(self, other):
        less = self.__lt__(other)
        if less is NotImplemented:
            return NotImplemented
        equal = self.__eq__(other)
        if equal is NotImplemented:
            return NotImplemented
        return not (less or equal)
    def __ge__(self, other):
        less = self.__lt__(other)
        if less is NotImplemented:
            return NotImplemented
        return not less

class _IPAddressBase(_TotalOrderingMixin):

    """The mother class."""

    @property
    def exploded(self):
        """Return the longhand version of the IP address as a string."""
        return self._explode_shorthand_ip_string()

    @property
    def compressed(self):
        """Return the shorthand version of the IP address as a string."""
        return str(self)

    @property
    def reverse_pointer(self):
        """The name of the reverse DNS pointer for the IP address, e.g.:
            >>> ipaddress.ip_address("127.0.0.1").reverse_pointer
            '1.0.0.127.in-addr.arpa'
            >>> ipaddress.ip_address("2001:db8::1").reverse_pointer
            '1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.8.b.d.0.1.0.0.2.ip6.arpa'

        """
        return self._reverse_pointer()

    @property
    def version(self):
        msg = '%200s has no version specified' % (type(self),)
        raise NotImplementedError(msg)

    def _check_int_address(self, address):
        if address < 0:
            msg = "%d (< 0) is not permitted as an IPv%d address"
            raise AddressValueError(msg % (address, self._version))
        if address > self._ALL_ONES:
            msg = "%d (>= 2**%d) is not permitted as an IPv%d address"
            raise AddressValueError(msg % (address, self._max_prefixlen,
                                           self._version))

    def _check_packed_address(self, address, expected_len):
        address_len = len(address)
        if address_len != expected_len:
            msg = "%r (len %d != %d) is not permitted as an IPv%d address"
            raise AddressValueError(msg % (address, address_len,
                                           expected_len, self._version))

    def _ip_int_from_prefix(self, prefixlen):
        """Turn the prefix length into a bitwise netmask

        Args:
            prefixlen: An integer, the prefix length.

        Returns:
            An integer.

        """
        return self._ALL_ONES ^ (self._ALL_ONES >> prefixlen)

    def _prefix_from_ip_int(self, ip_int):
        """Return prefix length from the bitwise netmask.

        Args:
            ip_int: An integer, the netmask in expanded bitwise format

        Returns:
            An integer, the prefix length.

        Raises:
            ValueError: If the input intermingles zeroes & ones
        """
        trailing_zeroes = _count_righthand_zero_bits(ip_int,
                                                     self._max_prefixlen)
        prefixlen = self._max_prefixlen - trailing_zeroes
        leading_ones = ip_int >> trailing_zeroes
        all_ones = (1 << prefixlen) - 1
        if leading_ones != all_ones:
            byteslen = self._max_prefixlen // 8
            details = _int_to_bytes(ip_int, byteslen, 'big')
            msg = 'Netmask pattern %r mixes zeroes & ones'
            raise ValueError(msg % details)
        return prefixlen

    def _report_invalid_netmask(self, netmask_str):
        msg = '%r is not a valid netmask' % netmask_str
        raise NetmaskValueError(msg)

    def _prefix_from_prefix_string(self, prefixlen_str):
        """Return prefix length from a numeric string

        Args:
            prefixlen_str: The string to be converted

        Returns:
            An integer, the prefix length.

        Raises:
            NetmaskValueError: If the input is not a valid netmask
        """
        # int allows a leading +/- as well as surrounding whitespace,
        # so we ensure that isn't the case
        if not _BaseV4._DECIMAL_DIGITS.issuperset(prefixlen_str):
            self._report_invalid_netmask(prefixlen_str)
        try:
            prefixlen = int(prefixlen_str)
        except ValueError:
            self._report_invalid_netmask(prefixlen_str)
        if not (0 <= prefixlen <= self._max_prefixlen):
            self._report_invalid_netmask(prefixlen_str)
        return prefixlen

    def _prefix_from_ip_string(self, ip_str):
        """Turn a netmask/hostmask string into a prefix length

        Args:
            ip_str: The netmask/hostmask to be converted

        Returns:
            An integer, the prefix length.

        Raises:
            NetmaskValueError: If the input is not a valid netmask/hostmask
        """
        # Parse the netmask/hostmask like an IP address.
        try:
            ip_int = self._ip_int_from_string(ip_str)
        except AddressValueError:
            self._report_invalid_netmask(ip_str)

        # Try matching a netmask (this would be /1*0*/ as a bitwise regexp).
        # Note that the two ambiguous cases (all-ones and all-zeroes) are
        # treated as netmasks.
        try:
            return self._prefix_from_ip_int(ip_int)
        except ValueError:
            pass

        # Invert the bits, and try matching a /0+1+/ hostmask instead.
        ip_int ^= self._ALL_ONES
        try:
            return self._prefix_from_ip_int(ip_int)
        except ValueError:
            self._report_invalid_netmask(ip_str)


class _BaseAddress(_IPAddressBase):

    """A generic IP object.

    This IP class contains the version independent methods which are
    used by single IP addresses.
    """

    def __init__(self, address):
        if (not isinstance(address, bytes)
            and '/' in str(address)):
            raise AddressValueError("Unexpected '/' in %r" % address)

    def __int__(self):
        return self._ip

    def __eq__(self, other):
        try:
            return (self._ip == other._ip
                    and self._version == other._version)
        except AttributeError:
            return NotImplemented

    def __lt__(self, other):
        if self._version != other._version:
            raise TypeError('%s and %s are not of the same version' % (
                             self, other))
        if not isinstance(other, _BaseAddress):
            raise TypeError('%s and %s are not of the same type' % (
                             self, other))
        if self._ip != other._ip:
            return self._ip < other._ip
        return False

    # Shorthand for Integer addition and subtraction. This is not
    # meant to ever support addition/subtraction of addresses.
    def __add__(self, other):
        if not isinstance(other, int):
            return NotImplemented
        return self.__class__(int(self) + other)

    def __sub__(self, other):
        if not isinstance(other, int):
            return NotImplemented
        return self.__class__(int(self) - other)

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, str(self))

    def __str__(self):
        return str(self._string_from_ip_int(self._ip))

    def __hash__(self):
        return hash(hex(int(self._ip)))

    def _get_address_key(self):
        return (self._version, self)


class _BaseNetwork(_IPAddressBase):

    """A generic IP network object.

    This IP class contains the version independent methods which are
    used by networks.

    """
    def __init__(self, address):
        self._cache = {}

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, str(self))

    def __str__(self):
        return '%s/%d' % (self.network_address, self.prefixlen)

    def hosts(self):
        """Generate Iterator over usable hosts in a network.

        This is like __iter__ except it doesn't return the network
        or broadcast addresses.

        """
        network = int(self.network_address)
        broadcast = int(self.broadcast_address)
        for x in long_range(network + 1, broadcast):
            yield self._address_class(x)

    def __iter__(self):
        network = int(self.network_address)
        broadcast = int(self.broadcast_address)
        for x in long_range(network, broadcast + 1):
            yield self._address_class(x)

    def __getitem__(self, n):
        network = int(self.network_address)
        broadcast = int(self.broadcast_address)
        if n >= 0:
            if network + n > broadcast:
                raise IndexError
            return self._address_class(network + n)
        else:
            n += 1
            if broadcast + n < network:
                raise IndexError
            return self._address_class(broadcast + n)

    def __lt__(self, other):
        if self._version != other._version:
            raise TypeError('%s and %s are not of the same version' % (
                             self, other))
        if not isinstance(other, _BaseNetwork):
            raise TypeError('%s and %s are not of the same type' % (
                             self, other))
        if self.network_address != other.network_address:
            return self.network_address < other.network_address
        if self.netmask != other.netmask:
            return self.netmask < other.netmask
        return False

    def __eq__(self, other):
        try:
            return (self._version == other._version and
                    self.network_address == other.network_address and
                    int(self.netmask) == int(other.netmask))
        except AttributeError:
            return NotImplemented

    def __hash__(self):
        return hash(int(self.network_address) ^ int(self.netmask))

    def __contains__(self, other):
        # always false if one is v4 and the other is v6.
        if self._version != other._version:
            return False
        # dealing with another network.
        if isinstance(other, _BaseNetwork):
            return False
        # dealing with another address
        else:
            # address
            return (int(self.network_address) <= int(other._ip) <=
                    int(self.broadcast_address))

    def overlaps(self, other):
        """Tell if self is partly contained in other."""
        return self.network_address in other or (
            self.broadcast_address in other or (
                other.network_address in self or (
                    other.broadcast_address in self)))

    @property
    def broadcast_address(self):
        x = self._cache.get('broadcast_address')
        if x is None:
            x = self._address_class(int(self.network_address) |
                                    int(self.hostmask))
            self._cache['broadcast_address'] = x
        return x

    @property
    def hostmask(self):
        x = self._cache.get('hostmask')
        if x is None:
            x = self._address_class(int(self.netmask) ^ self._ALL_ONES)
            self._cache['hostmask'] = x
        return x

    @property
    def with_prefixlen(self):
        return '%s/%d' % (self.network_address, self._prefixlen)

    @property
    def with_netmask(self):
        return '%s/%s' % (self.network_address, self.netmask)

    @property
    def with_hostmask(self):
        return '%s/%s' % (self.network_address, self.hostmask)

    @property
    def num_addresses(self):
        """Number of hosts in the current subnet."""
        return int(self.broadcast_address) - int(self.network_address) + 1

    @property
    def _address_class(self):
        # Returning bare address objects (rather than interfaces) allows for
        # more consistent behaviour across the network address, broadcast
        # address and individual host addresses.
        msg = '%200s has no associated address class' % (type(self),)
        raise NotImplementedError(msg)

    @property
    def prefixlen(self):
        return self._prefixlen

    def address_exclude(self, other):
        """Remove an address from a larger block.

        For example:

            addr1 = ip_network('192.0.2.0/28')
            addr2 = ip_network('192.0.2.1/32')
            addr1.address_exclude(addr2) =
                [IPv4Network('192.0.2.0/32'), IPv4Network('192.0.2.2/31'),
                IPv4Network('192.0.2.4/30'), IPv4Network('192.0.2.8/29')]

        or IPv6:

            addr1 = ip_network('2001:db8::1/32')
            addr2 = ip_network('2001:db8::1/128')
            addr1.address_exclude(addr2) =
                [ip_network('2001:db8::1/128'),
                ip_network('2001:db8::2/127'),
                ip_network('2001:db8::4/126'),
                ip_network('2001:db8::8/125'),
                ...
                ip_network('2001:db8:8000::/33')]

        Args:
            other: An IPv4Network or IPv6Network object of the same type.

        Returns:
            An iterator of the IPv(4|6)Network objects which is self
            minus other.

        Raises:
            TypeError: If self and other are of differing address
              versions, or if other is not a network object.
            ValueError: If other is not completely contained by self.

        """
        if not self._version == other._version:
            raise TypeError("%s and %s are not of the same version" % (
                             self, other))

        if not isinstance(other, _BaseNetwork):
            raise TypeError("%s is not a network object" % other)

        if not (other.network_address >= self.network_address and
                other.broadcast_address <= self.broadcast_address):
            raise ValueError('%s not contained in %s' % (other, self))
        if other == self:
            raise StopIteration

        # Make sure we're comparing the network of other.
        other = other.__class__('%s/%s' % (other.network_address,
                                           other.prefixlen))

        s1, s2 = self.subnets()
        while s1 != other and s2 != other:
            if (other.network_address >= s1.network_address and
                other.broadcast_address <= s1.broadcast_address):
                yield s2
                s1, s2 = s1.subnets()
            elif (other.network_address >= s2.network_address and
                  other.broadcast_address <= s2.broadcast_address):
                yield s1
                s1, s2 = s2.subnets()
            else:
                # If we got here, there's a bug somewhere.
                raise AssertionError('Error performing exclusion: '
                                     's1: %s s2: %s other: %s' %
                                     (s1, s2, other))
        if s1 == other:
            yield s2
        elif s2 == other:
            yield s1
        else:
            # If we got here, there's a bug somewhere.
            raise AssertionError('Error performing exclusion: '
                                 's1: %s s2: %s other: %s' %
                                 (s1, s2, other))

    def compare_networks(self, other):
        """Compare two IP objects.

        This is only concerned about the comparison of the integer
        representation of the network addresses.  This means that the
        host bits aren't considered at all in this method.  If you want
        to compare host bits, you can easily enough do a
        'HostA._ip < HostB._ip'

        Args:
            other: An IP object.

        Returns:
            If the IP versions of self and other are the same, returns:

            -1 if self < other:
              eg: IPv4Network('192.0.2.0/25') < IPv4Network('192.0.2.128/25')
              IPv6Network('2001:db8::1000/124') <
                  IPv6Network('2001:db8::2000/124')
            0 if self == other
              eg: IPv4Network('192.0.2.0/24') == IPv4Network('192.0.2.0/24')
              IPv6Network('2001:db8::1000/124') ==
                  IPv6Network('2001:db8::1000/124')
            1 if self > other
              eg: IPv4Network('192.0.2.128/25') > IPv4Network('192.0.2.0/25')
                  IPv6Network('2001:db8::2000/124') >
                      IPv6Network('2001:db8::1000/124')

          Raises:
              TypeError if the IP versions are different.

        """
        # does this need to raise a ValueError?
        if self._version != other._version:
            raise TypeError('%s and %s are not of the same type' % (
                             self, other))
        # self._version == other._version below here:
        if self.network_address < other.network_address:
            return -1
        if self.network_address > other.network_address:
            return 1
        # self.network_address == other.network_address below here:
        if self.netmask < other.netmask:
            return -1
        if self.netmask > other.netmask:
            return 1
        return 0

    def _get_networks_key(self):
        """Network-only key function.

        Returns an object that identifies this address' network and
        netmask. This function is a suitable "key" argument for sorted()
        and list.sort().

        """
        return (self._version, self.network_address, self.netmask)

    def subnets(self, prefixlen_diff=1, new_prefix=None):
        """The subnets which join to make the current subnet.

        In the case that self contains only one IP
        (self._prefixlen == 32 for IPv4 or self._prefixlen == 128
        for IPv6), yield an iterator with just ourself.

        Args:
            prefixlen_diff: An integer, the amount the prefix length
              should be increased by. This should not be set if
              new_prefix is also set.
            new_prefix: The desired new prefix length. This must be a
              larger number (smaller prefix) than the existing prefix.
              This should not be set if prefixlen_diff is also set.

        Returns:
            An iterator of IPv(4|6) objects.

        Raises:
            ValueError: The prefixlen_diff is too small or too large.
                OR
            prefixlen_diff and new_prefix are both set or new_prefix
              is a smaller number than the current prefix (smaller
              number means a larger network)

        """
        if self._prefixlen == self._max_prefixlen:
            yield self
            return

        if new_prefix is not None:
            if new_prefix < self._prefixlen:
                raise ValueError('new prefix must be longer')
            if prefixlen_diff != 1:
                raise ValueError('cannot set prefixlen_diff and new_prefix')
            prefixlen_diff = new_prefix - self._prefixlen

        if prefixlen_diff < 0:
            raise ValueError('prefix length diff must be > 0')
        new_prefixlen = self._prefixlen + prefixlen_diff

        if new_prefixlen > self._max_prefixlen:
            raise ValueError(
                'prefix length diff %d is invalid for netblock %s' % (
                    new_prefixlen, self))

        first = self.__class__('%s/%s' %
                                 (self.network_address,
                                  self._prefixlen + prefixlen_diff))

        yield first
        current = first
        while True:
            broadcast = current.broadcast_address
            if broadcast == self.broadcast_address:
                return
            new_addr = self._address_class(int(broadcast) + 1)
            current = self.__class__('%s/%s' % (new_addr,
                                                new_prefixlen))

            yield current

    def supernet(self, prefixlen_diff=1, new_prefix=None):
        """The supernet containing the current network.

        Args:
            prefixlen_diff: An integer, the amount the prefix length of
              the network should be decreased by.  For example, given a
              /24 network and a prefixlen_diff of 3, a supernet with a
              /21 netmask is returned.

        Returns:
            An IPv4 network object.

        Raises:
            ValueError: If self.prefixlen - prefixlen_diff < 0. I.e., you have
              a negative prefix length.
                OR
            If prefixlen_diff and new_prefix are both set or new_prefix is a
              larger number than the current prefix (larger number means a
              smaller network)

        """
        if self._prefixlen == 0:
            return self

        if new_prefix is not None:
            if new_prefix > self._prefixlen:
                raise ValueError('new prefix must be shorter')
            if prefixlen_diff != 1:
                raise ValueError('cannot set prefixlen_diff and new_prefix')
            prefixlen_diff = self._prefixlen - new_prefix

        if self.prefixlen - prefixlen_diff < 0:
            raise ValueError(
                'current prefixlen is %d, cannot have a prefixlen_diff of %d' %
                (self.prefixlen, prefixlen_diff))
        # TODO (pmoody): optimize this.
        t = self.__class__('%s/%d' % (self.network_address,
                                      self.prefixlen - prefixlen_diff),
                                     strict=False)
        return t.__class__('%s/%d' % (t.network_address, t.prefixlen))

    @property
    def is_multicast(self):
        """Test if the address is reserved for multicast use.

        Returns:
            A boolean, True if the address is a multicast address.
            See RFC 2373 2.7 for details.

        """
        return (self.network_address.is_multicast and
                self.broadcast_address.is_multicast)

    @property
    def is_reserved(self):
        """Test if the address is otherwise IETF reserved.

        Returns:
            A boolean, True if the address is within one of the
            reserved IPv6 Network ranges.

        """
        return (self.network_address.is_reserved and
                self.broadcast_address.is_reserved)

    @property
    def is_link_local(self):
        """Test if the address is reserved for link-local.

        Returns:
            A boolean, True if the address is reserved per RFC 4291.

        """
        return (self.network_address.is_link_local and
                self.broadcast_address.is_link_local)

    @property
    def is_private(self):
        """Test if this address is allocated for private networks.

        Returns:
            A boolean, True if the address is reserved per
            iana-ipv4-special-registry or iana-ipv6-special-registry.

        """
        return (self.network_address.is_private and
                self.broadcast_address.is_private)

    @property
    def is_global(self):
        """Test if this address is allocated for public networks.

        Returns:
            A boolean, True if the address is not reserved per
            iana-ipv4-special-registry or iana-ipv6-special-registry.

        """
        return not self.is_private

    @property
    def is_unspecified(self):
        """Test if the address is unspecified.

        Returns:
            A boolean, True if this is the unspecified address as defined in
            RFC 2373 2.5.2.

        """
        return (self.network_address.is_unspecified and
                self.broadcast_address.is_unspecified)

    @property
    def is_loopback(self):
        """Test if the address is a loopback address.

        Returns:
            A boolean, True if the address is a loopback address as defined in
            RFC 2373 2.5.3.

        """
        return (self.network_address.is_loopback and
                self.broadcast_address.is_loopback)


class _BaseV4(object):

    """Base IPv4 object.

    The following methods are used by IPv4 objects in both single IP
    addresses and networks.

    """

    # Equivalent to 255.255.255.255 or 32 bits of 1's.
    _ALL_ONES = (2**IPV4LENGTH) - 1
    _DECIMAL_DIGITS = frozenset('0123456789')

    # the valid octets for host and netmasks. only useful for IPv4.
    _valid_mask_octets = frozenset((255, 254, 252, 248, 240, 224, 192, 128, 0))

    def __init__(self, address):
        self._version = 4
        self._max_prefixlen = IPV4LENGTH

    def _explode_shorthand_ip_string(self):
        return str(self)

    def _ip_int_from_string(self, ip_str):
        """Turn the given IP string into an integer for comparison.

        Args:
            ip_str: A string, the IP ip_str.

        Returns:
            The IP ip_str as an integer.

        Raises:
            AddressValueError: if ip_str isn't a valid IPv4 Address.

        """
        if not ip_str:
            raise AddressValueError('Address cannot be empty')

        octets = ip_str.split('.')
        if len(octets) != 4:
            raise AddressValueError("Expected 4 octets in %r" % ip_str)

        try:
            return _int_from_bytes(map(self._parse_octet, octets), 'big')
        except ValueError as exc:
            raise AddressValueError("%s in %r" % (exc, ip_str))

    def _parse_octet(self, octet_str):
        """Convert a decimal octet into an integer.

        Args:
            octet_str: A string, the number to parse.

        Returns:
            The octet as an integer.

        Raises:
            ValueError: if the octet isn't strictly a decimal from [0..255].

        """
        if not octet_str:
            raise ValueError("Empty octet not permitted")
        # Whitelist the characters, since int() allows a lot of bizarre stuff.
        if not self._DECIMAL_DIGITS.issuperset(octet_str):
            msg = "Only decimal digits permitted in %r"
            raise ValueError(msg % octet_str)
        # We do the length check second, since the invalid character error
        # is likely to be more informative for the user
        if len(octet_str) > 3:
            msg = "At most 3 characters permitted in %r"
            raise ValueError(msg % octet_str)
        # Convert to integer (we know digits are legal)
        octet_int = int(octet_str, 10)
        # Any octets that look like they *might* be written in octal,
        # and which don't look exactly the same in both octal and
        # decimal are rejected as ambiguous
        if octet_int > 7 and octet_str[0] == '0':
            msg = "Ambiguous (octal/decimal) value in %r not permitted"
            raise ValueError(msg % octet_str)
        if octet_int > 255:
            raise ValueError("Octet %d (> 255) not permitted" % octet_int)
        return octet_int

    def _string_from_ip_int(self, ip_int):
        """Turns a 32-bit integer into dotted decimal notation.

        Args:
            ip_int: An integer, the IP address.

        Returns:
            The IP address as a string in dotted decimal notation.

        """
        return '.'.join(map(str, _int_to_bytes(ip_int, 4, 'big')))

    def _is_valid_netmask(self, netmask):
        """Verify that the netmask is valid.

        Args:
            netmask: A string, either a prefix or dotted decimal
              netmask.

        Returns:
            A boolean, True if the prefix represents a valid IPv4
            netmask.

        """
        mask = netmask.split('.')
        if len(mask) == 4:
            try:
                for x in mask:
                    if int(x) not in self._valid_mask_octets:
                        return False
            except ValueError:
                # Found something that isn't an integer or isn't valid
                return False
            for idx, y in enumerate(mask):
                if idx > 0 and y > mask[idx - 1]:
                    return False
            return True
        try:
            netmask = int(netmask)
        except ValueError:
            return False
        return 0 <= netmask <= self._max_prefixlen

    def _is_hostmask(self, ip_str):
        """Test if the IP string is a hostmask (rather than a netmask).

        Args:
            ip_str: A string, the potential hostmask.

        Returns:
            A boolean, True if the IP string is a hostmask.

        """
        bits = ip_str.split('.')
        try:
            parts = [x for x in map(int, bits) if x in self._valid_mask_octets]
        except ValueError:
            return False
        if len(parts) != len(bits):
            return False
        if parts[0] < parts[-1]:
            return True
        return False

    def _reverse_pointer(self):
        """Return the reverse DNS pointer name for the IPv4 address.

        This implements the method described in RFC1035 3.5.

        """
        reverse_octets = str(self).split('.')[::-1]
        return '.'.join(reverse_octets) + '.in-addr.arpa'

    @property
    def max_prefixlen(self):
        return self._max_prefixlen

    @property
    def version(self):
        return self._version


class IPv4Address(_BaseV4, _BaseAddress):

    """Represent and manipulate single IPv4 Addresses."""

    def __init__(self, address):

        """
        Args:
            address: A string or integer representing the IP

              Additionally, an integer can be passed, so
              IPv4Address('192.0.2.1') == IPv4Address(3221225985).
              or, more generally
              IPv4Address(int(IPv4Address('192.0.2.1'))) ==
                IPv4Address('192.0.2.1')

        Raises:
            AddressValueError: If ipaddress isn't a valid IPv4 address.

        """
        _BaseAddress.__init__(self, address)
        _BaseV4.__init__(self, address)

        # Efficient constructor from integer.
        if isinstance(address, int):
            self._check_int_address(address)
            self._ip = address
            return

        # Constructing from a packed address
        if isinstance(address, bytes):
            self._check_packed_address(address, 4)
            self._ip = _int_from_bytes(address, 'big')
            return

        # Assume input argument to be string or any object representation
        # which converts into a formatted IP string.
        addr_str = str(address)
        self._ip = self._ip_int_from_string(addr_str)

    @property
    def packed(self):
        """The binary representation of this address."""
        return v4_int_to_packed(self._ip)

    @property
    def is_reserved(self):
        """Test if the address is otherwise IETF reserved.

         Returns:
             A boolean, True if the address is within the
             reserved IPv4 Network range.

        """
        reserved_network = IPv4Network('240.0.0.0/4')
        return self in reserved_network

    @property
    def is_private(self):
        """Test if this address is allocated for private networks.

        Returns:
            A boolean, True if the address is reserved per
            iana-ipv4-special-registry.

        """
        return (self in IPv4Network('0.0.0.0/8') or
                self in IPv4Network('10.0.0.0/8') or
                self in IPv4Network('127.0.0.0/8') or
                self in IPv4Network('169.254.0.0/16') or
                self in IPv4Network('172.16.0.0/12') or
                self in IPv4Network('192.0.0.0/29') or
                self in IPv4Network('192.0.0.170/31') or
                self in IPv4Network('192.0.2.0/24') or
                self in IPv4Network('192.168.0.0/16') or
                self in IPv4Network('198.18.0.0/15') or
                self in IPv4Network('198.51.100.0/24') or
                self in IPv4Network('203.0.113.0/24') or
                self in IPv4Network('240.0.0.0/4') or
                self in IPv4Network('255.255.255.255/32'))


    @property
    def is_multicast(self):
        """Test if the address is reserved for multicast use.

        Returns:
            A boolean, True if the address is multicast.
            See RFC 3171 for details.

        """
        multicast_network = IPv4Network('224.0.0.0/4')
        return self in multicast_network

    @property
    def is_unspecified(self):
        """Test if the address is unspecified.

        Returns:
            A boolean, True if this is the unspecified address as defined in
            RFC 5735 3.

        """
        unspecified_address = IPv4Address('0.0.0.0')
        return self == unspecified_address

    @property
    def is_loopback(self):
        """Test if the address is a loopback address.

        Returns:
            A boolean, True if the address is a loopback per RFC 3330.

        """
        loopback_network = IPv4Network('127.0.0.0/8')
        return self in loopback_network

    @property
    def is_link_local(self):
        """Test if the address is reserved for link-local.

        Returns:
            A boolean, True if the address is link-local per RFC 3927.

        """
        linklocal_network = IPv4Network('169.254.0.0/16')
        return self in linklocal_network


class IPv4Interface(IPv4Address):

    def __init__(self, address):
        if isinstance(address, (bytes, int)):
            IPv4Address.__init__(self, address)
            self.network = IPv4Network(self._ip)
            self._prefixlen = self._max_prefixlen
            return

        addr = _split_optional_netmask(address)
        IPv4Address.__init__(self, addr[0])

        self.network = IPv4Network(address, strict=False)
        self._prefixlen = self.network._prefixlen

        self.netmask = self.network.netmask
        self.hostmask = self.network.hostmask

    def __str__(self):
        return '%s/%d' % (self._string_from_ip_int(self._ip),
                          self.network.prefixlen)

    def __eq__(self, other):
        address_equal = IPv4Address.__eq__(self, other)
        if not address_equal or address_equal is NotImplemented:
            return address_equal
        try:
            return self.network == other.network
        except AttributeError:
            # An interface with an associated network is NOT the
            # same as an unassociated address. That's why the hash
            # takes the extra info into account.
            return False

    def __lt__(self, other):
        address_less = IPv4Address.__lt__(self, other)
        if address_less is NotImplemented:
            return NotImplemented
        try:
            return self.network < other.network
        except AttributeError:
            # We *do* allow addresses and interfaces to be sorted. The
            # unassociated address is considered less than all interfaces.
            return False

    def __hash__(self):
        return self._ip ^ self._prefixlen ^ int(self.network.network_address)

    @property
    def ip(self):
        return IPv4Address(self._ip)

    @property
    def with_prefixlen(self):
        return '%s/%s' % (self._string_from_ip_int(self._ip),
                          self._prefixlen)

    @property
    def with_netmask(self):
        return '%s/%s' % (self._string_from_ip_int(self._ip),
                          self.netmask)

    @property
    def with_hostmask(self):
        return '%s/%s' % (self._string_from_ip_int(self._ip),
                          self.hostmask)


class IPv4Network(_BaseV4, _BaseNetwork):

    """This class represents and manipulates 32-bit IPv4 network + addresses..

    Attributes: [examples for IPv4Network('192.0.2.0/27')]
        .network_address: IPv4Address('192.0.2.0')
        .hostmask: IPv4Address('0.0.0.31')
        .broadcast_address: IPv4Address('192.0.2.32')
        .netmask: IPv4Address('255.255.255.224')
        .prefixlen: 27

    """
    # Class to use when creating address objects
    _address_class = IPv4Address

    def __init__(self, address, strict=True):

        """Instantiate a new IPv4 network object.

        Args:
            address: A string or integer representing the IP [& network].
              '192.0.2.0/24'
              '192.0.2.0/255.255.255.0'
              '192.0.0.2/0.0.0.255'
              are all functionally the same in IPv4. Similarly,
              '192.0.2.1'
              '192.0.2.1/255.255.255.255'
              '192.0.2.1/32'
              are also functionally equivalent. That is to say, failing to
              provide a subnetmask will create an object with a mask of /32.

              If the mask (portion after the / in the argument) is given in
              dotted quad form, it is treated as a netmask if it starts with a
              non-zero field (e.g. /255.0.0.0 == /8) and as a hostmask if it
              starts with a zero field (e.g. 0.255.255.255 == /8), with the
              single exception of an all-zero mask which is treated as a
              netmask == /0. If no mask is given, a default of /32 is used.

              Additionally, an integer can be passed, so
              IPv4Network('192.0.2.1') == IPv4Network(3221225985)
              or, more generally
              IPv4Interface(int(IPv4Interface('192.0.2.1'))) ==
                IPv4Interface('192.0.2.1')

        Raises:
            AddressValueError: If ipaddress isn't a valid IPv4 address.
            NetmaskValueError: If the netmask isn't valid for
              an IPv4 address.
            ValueError: If strict is True and a network address is not
              supplied.

        """

        _BaseV4.__init__(self, address)
        _BaseNetwork.__init__(self, address)

        # Constructing from a packed address
        if isinstance(address, bytes):
            self.network_address = IPv4Address(address)
            self._prefixlen = self._max_prefixlen
            self.netmask = IPv4Address(self._ALL_ONES)
            #fixme: address/network test here
            return

        # Efficient constructor from integer.
        if isinstance(address, int):
            self.network_address = IPv4Address(address)
            self._prefixlen = self._max_prefixlen
            self.netmask = IPv4Address(self._ALL_ONES)
            #fixme: address/network test here.
            return

        # Assume input argument to be string or any object representation
        # which converts into a formatted IP prefix string.
        addr = _split_optional_netmask(address)
        self.network_address = IPv4Address(self._ip_int_from_string(addr[0]))

        if len(addr) == 2:
            try:
                # Check for a netmask in prefix length form
                self._prefixlen = self._prefix_from_prefix_string(addr[1])
            except NetmaskValueError:
                # Check for a netmask or hostmask in dotted-quad form.
                # This may raise NetmaskValueError.
                self._prefixlen = self._prefix_from_ip_string(addr[1])
        else:
            self._prefixlen = self._max_prefixlen
        self.netmask = IPv4Address(self._ip_int_from_prefix(self._prefixlen))

        if strict:
            if (IPv4Address(int(self.network_address) & int(self.netmask)) !=
                self.network_address):
                raise ValueError('%s has host bits set' % self)
        self.network_address = IPv4Address(int(self.network_address) &
                                           int(self.netmask))

        if self._prefixlen == (self._max_prefixlen - 1):
            self.hosts = self.__iter__

    @property
    def is_global(self):
        """Test if this address is allocated for public networks.

        Returns:
            A boolean, True if the address is not reserved per
            iana-ipv4-special-registry.

        """
        return (not (self.network_address in IPv4Network('100.64.0.0/10') and
                    self.broadcast_address in IPv4Network('100.64.0.0/10')) and
                not self.is_private)



class _BaseV6(object):

    """Base IPv6 object.

    The following methods are used by IPv6 objects in both single IP
    addresses and networks.

    """

    _ALL_ONES = (2**IPV6LENGTH) - 1
    _HEXTET_COUNT = 8
    _HEX_DIGITS = frozenset('0123456789ABCDEFabcdef')

    def __init__(self, address):
        self._version = 6
        self._max_prefixlen = IPV6LENGTH

    def _ip_int_from_string(self, ip_str):
        """Turn an IPv6 ip_str into an integer.

        Args:
            ip_str: A string, the IPv6 ip_str.

        Returns:
            An int, the IPv6 address

        Raises:
            AddressValueError: if ip_str isn't a valid IPv6 Address.

        """
        if not ip_str:
            raise AddressValueError('Address cannot be empty')

        parts = ip_str.split(':')

        # An IPv6 address needs at least 2 colons (3 parts).
        _min_parts = 3
        if len(parts) < _min_parts:
            msg = "At least %d parts expected in %r" % (_min_parts, ip_str)
            raise AddressValueError(msg)

        # If the address has an IPv4-style suffix, convert it to hexadecimal.
        if '.' in parts[-1]:
            try:
                ipv4_int = IPv4Address(parts.pop())._ip
            except AddressValueError as exc:
                raise AddressValueError("%s in %r" % (exc, ip_str))
            parts.append('%x' % ((ipv4_int >> 16) & 0xFFFF))
            parts.append('%x' % (ipv4_int & 0xFFFF))

        # An IPv6 address can't have more than 8 colons (9 parts).
        # The extra colon comes from using the "::" notation for a single
        # leading or trailing zero part.
        _max_parts = self._HEXTET_COUNT + 1
        if len(parts) > _max_parts:
            msg = "At most %d colons permitted in %r" % (_max_parts-1, ip_str)
            raise AddressValueError(msg)

        # Disregarding the endpoints, find '::' with nothing in between.
        # This indicates that a run of zeroes has been skipped.
        skip_index = None
        for i in range(1, len(parts) - 1):
            if not parts[i]:
                if skip_index is not None:
                    # Can't have more than one '::'
                    msg = "At most one '::' permitted in %r" % ip_str
                    raise AddressValueError(msg)
                skip_index = i

        # parts_hi is the number of parts to copy from above/before the '::'
        # parts_lo is the number of parts to copy from below/after the '::'
        if skip_index is not None:
            # If we found a '::', then check if it also covers the endpoints.
            parts_hi = skip_index
            parts_lo = len(parts) - skip_index - 1
            if not parts[0]:
                parts_hi -= 1
                if parts_hi:
                    msg = "Leading ':' only permitted as part of '::' in %r"
                    raise AddressValueError(msg % ip_str)  # ^: requires ^::
            if not parts[-1]:
                parts_lo -= 1
                if parts_lo:
                    msg = "Trailing ':' only permitted as part of '::' in %r"
                    raise AddressValueError(msg % ip_str)  # :$ requires ::$
            parts_skipped = self._HEXTET_COUNT - (parts_hi + parts_lo)
            if parts_skipped < 1:
                msg = "Expected at most %d other parts with '::' in %r"
                raise AddressValueError(msg % (self._HEXTET_COUNT-1, ip_str))
        else:
            # Otherwise, allocate the entire address to parts_hi.  The
            # endpoints could still be empty, but _parse_hextet() will check
            # for that.
            if len(parts) != self._HEXTET_COUNT:
                msg = "Exactly %d parts expected without '::' in %r"
                raise AddressValueError(msg % (self._HEXTET_COUNT, ip_str))
            if not parts[0]:
                msg = "Leading ':' only permitted as part of '::' in %r"
                raise AddressValueError(msg % ip_str)  # ^: requires ^::
            if not parts[-1]:
                msg = "Trailing ':' only permitted as part of '::' in %r"
                raise AddressValueError(msg % ip_str)  # :$ requires ::$
            parts_hi = len(parts)
            parts_lo = 0
            parts_skipped = 0

        try:
            # Now, parse the hextets into a 128-bit integer.
            ip_int = 0
            for i in range(parts_hi):
                ip_int <<= 16
                ip_int |= self._parse_hextet(parts[i])
            ip_int <<= 16 * parts_skipped
            for i in range(-parts_lo, 0):
                ip_int <<= 16
                ip_int |= self._parse_hextet(parts[i])
            return ip_int
        except ValueError as exc:
            raise AddressValueError("%s in %r" % (exc, ip_str))

    def _parse_hextet(self, hextet_str):
        """Convert an IPv6 hextet string into an integer.

        Args:
            hextet_str: A string, the number to parse.

        Returns:
            The hextet as an integer.

        Raises:
            ValueError: if the input isn't strictly a hex number from
              [0..FFFF].

        """
        # Whitelist the characters, since int() allows a lot of bizarre stuff.
        if not self._HEX_DIGITS.issuperset(hextet_str):
            raise ValueError("Only hex digits permitted in %r" % hextet_str)
        # We do the length check second, since the invalid character error
        # is likely to be more informative for the user
        if len(hextet_str) > 4:
            msg = "At most 4 characters permitted in %r"
            raise ValueError(msg % hextet_str)
        # Length check means we can skip checking the integer value
        return int(hextet_str, 16)

    def _compress_hextets(self, hextets):
        """Compresses a list of hextets.

        Compresses a list of strings, replacing the longest continuous
        sequence of "0" in the list with "" and adding empty strings at
        the beginning or at the end of the string such that subsequently
        calling ":".join(hextets) will produce the compressed version of
        the IPv6 address.

        Args:
            hextets: A list of strings, the hextets to compress.

        Returns:
            A list of strings.

        """
        best_doublecolon_start = -1
        best_doublecolon_len = 0
        doublecolon_start = -1
        doublecolon_len = 0
        for index, hextet in enumerate(hextets):
            if hextet == '0':
                doublecolon_len += 1
                if doublecolon_start == -1:
                    # Start of a sequence of zeros.
                    doublecolon_start = index
                if doublecolon_len > best_doublecolon_len:
                    # This is the longest sequence of zeros so far.
                    best_doublecolon_len = doublecolon_len
                    best_doublecolon_start = doublecolon_start
            else:
                doublecolon_len = 0
                doublecolon_start = -1

        if best_doublecolon_len > 1:
            best_doublecolon_end = (best_doublecolon_start +
                                    best_doublecolon_len)
            # For zeros at the end of the address.
            if best_doublecolon_end == len(hextets):
                hextets += ['']
            hextets[best_doublecolon_start:best_doublecolon_end] = ['']
            # For zeros at the beginning of the address.
            if best_doublecolon_start == 0:
                hextets = [''] + hextets

        return hextets

    def _string_from_ip_int(self, ip_int=None):
        """Turns a 128-bit integer into hexadecimal notation.

        Args:
            ip_int: An integer, the IP address.

        Returns:
            A string, the hexadecimal representation of the address.

        Raises:
            ValueError: The address is bigger than 128 bits of all ones.

        """
        if ip_int is None:
            ip_int = int(self._ip)

        if ip_int > self._ALL_ONES:
            raise ValueError('IPv6 address is too large')

        hex_str = '%032x' % ip_int
        hextets = ['%x' % int(hex_str[x:x+4], 16) for x in range(0, 32, 4)]

        hextets = self._compress_hextets(hextets)
        return ':'.join(hextets)

    def _explode_shorthand_ip_string(self):
        """Expand a shortened IPv6 address.

        Args:
            ip_str: A string, the IPv6 address.

        Returns:
            A string, the expanded IPv6 address.

        """
        if isinstance(self, IPv6Network):
            ip_str = str(self.network_address)
        elif isinstance(self, IPv6Interface):
            ip_str = str(self.ip)
        else:
            ip_str = str(self)

        ip_int = self._ip_int_from_string(ip_str)
        hex_str = '%032x' % ip_int
        parts = [hex_str[x:x+4] for x in range(0, 32, 4)]
        if isinstance(self, (_BaseNetwork, IPv6Interface)):
            return '%s/%d' % (':'.join(parts), self._prefixlen)
        return ':'.join(parts)

    def _reverse_pointer(self):
        """Return the reverse DNS pointer name for the IPv6 address.

        This implements the method described in RFC3596 2.5.

        """
        reverse_chars = self.exploded[::-1].replace(':', '')
        return '.'.join(reverse_chars) + '.ip6.arpa'

    @property
    def max_prefixlen(self):
        return self._max_prefixlen

    @property
    def version(self):
        return self._version


class IPv6Address(_BaseV6, _BaseAddress):

    """Represent and manipulate single IPv6 Addresses."""

    def __init__(self, address):
        """Instantiate a new IPv6 address object.

        Args:
            address: A string or integer representing the IP

              Additionally, an integer can be passed, so
              IPv6Address('2001:db8::') ==
                IPv6Address(42540766411282592856903984951653826560)
              or, more generally
              IPv6Address(int(IPv6Address('2001:db8::'))) ==
                IPv6Address('2001:db8::')

        Raises:
            AddressValueError: If address isn't a valid IPv6 address.

        """
        _BaseAddress.__init__(self, address)
        _BaseV6.__init__(self, address)

        # Efficient constructor from integer.
        if isinstance(address, int):
            self._check_int_address(address)
            self._ip = address
            return

        # Constructing from a packed address
        if isinstance(address, bytes):
            self._check_packed_address(address, 16)
            self._ip = _int_from_bytes(address, 'big')
            return

        # Assume input argument to be string or any object representation
        # which converts into a formatted IP string.
        addr_str = str(address)
        self._ip = self._ip_int_from_string(addr_str)

    @property
    def packed(self):
        """The binary representation of this address."""
        return v6_int_to_packed(self._ip)

    @property
    def is_multicast(self):
        """Test if the address is reserved for multicast use.

        Returns:
            A boolean, True if the address is a multicast address.
            See RFC 2373 2.7 for details.

        """
        multicast_network = IPv6Network('ff00::/8')
        return self in multicast_network

    @property
    def is_reserved(self):
        """Test if the address is otherwise IETF reserved.

        Returns:
            A boolean, True if the address is within one of the
            reserved IPv6 Network ranges.

        """
        reserved_networks = [IPv6Network('::/8'), IPv6Network('100::/8'),
                             IPv6Network('200::/7'), IPv6Network('400::/6'),
                             IPv6Network('800::/5'), IPv6Network('1000::/4'),
                             IPv6Network('4000::/3'), IPv6Network('6000::/3'),
                             IPv6Network('8000::/3'), IPv6Network('A000::/3'),
                             IPv6Network('C000::/3'), IPv6Network('E000::/4'),
                             IPv6Network('F000::/5'), IPv6Network('F800::/6'),
                             IPv6Network('FE00::/9')]

        return any(self in x for x in reserved_networks)

    @property
    def is_link_local(self):
        """Test if the address is reserved for link-local.

        Returns:
            A boolean, True if the address is reserved per RFC 4291.

        """
        linklocal_network = IPv6Network('fe80::/10')
        return self in linklocal_network

    @property
    def is_site_local(self):
        """Test if the address is reserved for site-local.

        Note that the site-local address space has been deprecated by RFC 3879.
        Use is_private to test if this address is in the space of unique local
        addresses as defined by RFC 4193.

        Returns:
            A boolean, True if the address is reserved per RFC 3513 2.5.6.

        """
        sitelocal_network = IPv6Network('fec0::/10')
        return self in sitelocal_network

    @property
    def is_private(self):
        """Test if this address is allocated for private networks.

        Returns:
            A boolean, True if the address is reserved per
            iana-ipv6-special-registry.

        """
        return (self in IPv6Network('::1/128') or
                self in IPv6Network('::/128') or
                self in IPv6Network('::ffff:0:0/96') or
                self in IPv6Network('100::/64') or
                self in IPv6Network('2001::/23') or
                self in IPv6Network('2001:2::/48') or
                self in IPv6Network('2001:db8::/32') or
                self in IPv6Network('2001:10::/28') or
                self in IPv6Network('fc00::/7') or
                self in IPv6Network('fe80::/10'))

    @property
    def is_global(self):
        """Test if this address is allocated for public networks.

        Returns:
            A boolean, true if the address is not reserved per
            iana-ipv6-special-registry.

        """
        return not self.is_private

    @property
    def is_unspecified(self):
        """Test if the address is unspecified.

        Returns:
            A boolean, True if this is the unspecified address as defined in
            RFC 2373 2.5.2.

        """
        return self._ip == 0

    @property
    def is_loopback(self):
        """Test if the address is a loopback address.

        Returns:
            A boolean, True if the address is a loopback address as defined in
            RFC 2373 2.5.3.

        """
        return self._ip == 1

    @property
    def ipv4_mapped(self):
        """Return the IPv4 mapped address.

        Returns:
            If the IPv6 address is a v4 mapped address, return the
            IPv4 mapped address. Return None otherwise.

        """
        if (self._ip >> 32) != 0xFFFF:
            return None
        return IPv4Address(self._ip & 0xFFFFFFFF)

    @property
    def teredo(self):
        """Tuple of embedded teredo IPs.

        Returns:
            Tuple of the (server, client) IPs or None if the address
            doesn't appear to be a teredo address (doesn't start with
            2001::/32)

        """
        if (self._ip >> 96) != 0x20010000:
            return None
        return (IPv4Address((self._ip >> 64) & 0xFFFFFFFF),
                IPv4Address(~self._ip & 0xFFFFFFFF))

    @property
    def sixtofour(self):
        """Return the IPv4 6to4 embedded address.

        Returns:
            The IPv4 6to4-embedded address if present or None if the
            address doesn't appear to contain a 6to4 embedded address.

        """
        if (self._ip >> 112) != 0x2002:
            return None
        return IPv4Address((self._ip >> 80) & 0xFFFFFFFF)


class IPv6Interface(IPv6Address):

    def __init__(self, address):
        if isinstance(address, (bytes, int)):
            IPv6Address.__init__(self, address)
            self.network = IPv6Network(self._ip)
            self._prefixlen = self._max_prefixlen
            return

        addr = _split_optional_netmask(address)
        IPv6Address.__init__(self, addr[0])
        self.network = IPv6Network(address, strict=False)
        self.netmask = self.network.netmask
        self._prefixlen = self.network._prefixlen
        self.hostmask = self.network.hostmask

    def __str__(self):
        return '%s/%d' % (self._string_from_ip_int(self._ip),
                          self.network.prefixlen)

    def __eq__(self, other):
        address_equal = IPv6Address.__eq__(self, other)
        if not address_equal or address_equal is NotImplemented:
            return address_equal
        try:
            return self.network == other.network
        except AttributeError:
            # An interface with an associated network is NOT the
            # same as an unassociated address. That's why the hash
            # takes the extra info into account.
            return False

    def __lt__(self, other):
        address_less = IPv6Address.__lt__(self, other)
        if address_less is NotImplemented:
            return NotImplemented
        try:
            return self.network < other.network
        except AttributeError:
            # We *do* allow addresses and interfaces to be sorted. The
            # unassociated address is considered less than all interfaces.
            return False

    def __hash__(self):
        return self._ip ^ self._prefixlen ^ int(self.network.network_address)

    @property
    def ip(self):
        return IPv6Address(self._ip)

    @property
    def with_prefixlen(self):
        return '%s/%s' % (self._string_from_ip_int(self._ip),
                          self._prefixlen)

    @property
    def with_netmask(self):
        return '%s/%s' % (self._string_from_ip_int(self._ip),
                          self.netmask)

    @property
    def with_hostmask(self):
        return '%s/%s' % (self._string_from_ip_int(self._ip),
                          self.hostmask)

    @property
    def is_unspecified(self):
        return self._ip == 0 and self.network.is_unspecified

    @property
    def is_loopback(self):
        return self._ip == 1 and self.network.is_loopback


class IPv6Network(_BaseV6, _BaseNetwork):

    """This class represents and manipulates 128-bit IPv6 networks.

    Attributes: [examples for IPv6('2001:db8::1000/124')]
        .network_address: IPv6Address('2001:db8::1000')
        .hostmask: IPv6Address('::f')
        .broadcast_address: IPv6Address('2001:db8::100f')
        .netmask: IPv6Address('ffff:ffff:ffff:ffff:ffff:ffff:ffff:fff0')
        .prefixlen: 124

    """

    # Class to use when creating address objects
    _address_class = IPv6Address

    def __init__(self, address, strict=True):
        """Instantiate a new IPv6 Network object.

        Args:
            address: A string or integer representing the IPv6 network or the
              IP and prefix/netmask.
              '2001:db8::/128'
              '2001:db8:0000:0000:0000:0000:0000:0000/128'
              '2001:db8::'
              are all functionally the same in IPv6.  That is to say,
              failing to provide a subnetmask will create an object with
              a mask of /128.

              Additionally, an integer can be passed, so
              IPv6Network('2001:db8::') ==
                IPv6Network(42540766411282592856903984951653826560)
              or, more generally
              IPv6Network(int(IPv6Network('2001:db8::'))) ==
                IPv6Network('2001:db8::')

            strict: A boolean. If true, ensure that we have been passed
              A true network address, eg, 2001:db8::1000/124 and not an
              IP address on a network, eg, 2001:db8::1/124.

        Raises:
            AddressValueError: If address isn't a valid IPv6 address.
            NetmaskValueError: If the netmask isn't valid for
              an IPv6 address.
            ValueError: If strict was True and a network address was not
              supplied.

        """
        _BaseV6.__init__(self, address)
        _BaseNetwork.__init__(self, address)

        # Efficient constructor from integer.
        if isinstance(address, int):
            self.network_address = IPv6Address(address)
            self._prefixlen = self._max_prefixlen
            self.netmask = IPv6Address(self._ALL_ONES)
            return

        # Constructing from a packed address
        if isinstance(address, bytes):
            self.network_address = IPv6Address(address)
            self._prefixlen = self._max_prefixlen
            self.netmask = IPv6Address(self._ALL_ONES)
            return

        # Assume input argument to be string or any object representation
        # which converts into a formatted IP prefix string.
        addr = _split_optional_netmask(address)

        self.network_address = IPv6Address(self._ip_int_from_string(addr[0]))

        if len(addr) == 2:
            # This may raise NetmaskValueError
            self._prefixlen = self._prefix_from_prefix_string(addr[1])
        else:
            self._prefixlen = self._max_prefixlen

        self.netmask = IPv6Address(self._ip_int_from_prefix(self._prefixlen))
        if strict:
            if (IPv6Address(int(self.network_address) & int(self.netmask)) !=
                self.network_address):
                raise ValueError('%s has host bits set' % self)
        self.network_address = IPv6Address(int(self.network_address) &
                                           int(self.netmask))

        if self._prefixlen == (self._max_prefixlen - 1):
            self.hosts = self.__iter__

    def hosts(self):
        """Generate Iterator over usable hosts in a network.

          This is like __iter__ except it doesn't return the
          Subnet-Router anycast address.

        """
        network = int(self.network_address)
        broadcast = int(self.broadcast_address)
        for x in long_range(1, broadcast - network + 1):
            yield self._address_class(network + x)

    @property
    def is_site_local(self):
        """Test if the address is reserved for site-local.

        Note that the site-local address space has been deprecated by RFC 3879.
        Use is_private to test if this address is in the space of unique local
        addresses as defined by RFC 4193.

        Returns:
            A boolean, True if the address is reserved per RFC 3513 2.5.6.

        """
        return (self.network_address.is_site_local and
                self.broadcast_address.is_site_local)
