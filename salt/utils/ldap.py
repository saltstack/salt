"""Common classes shared between LDAP execution and state modules."""


from salt.utils.oset import OrderedSet


class AttributeValueSet(OrderedSet):
    """Holds an attribute's values as an ordered set.

    `RFC 4511 section 4.1.7
    <https://datatracker.ietf.org/doc/html/rfc4511#section-4.1.7>`_ says, "The
    set of attribute values is unordered."  Despite this, this set is ordered so
    that it can support the `X-ORDERED
    <https://datatracker.ietf.org/doc/html/draft-chu-ldap-xordered-00>`_
    extension. (OpenLDAP has some X-ORDERED attributes in its ``cn=config``
    DIT.)

    RFC 4511 goes on to say, "Implementations MUST NOT rely upon the ordering
    being repeatable." To conform to this, the
    :py:meth:`~AttributeValueSet.__eq__` method ignores order. Salt will report
    no differences and take no action when a desired set of values already
    matches what is in LDAP, even if the reported order differs from the desired
    order.

    ``str`` values are stored as-is.  Other types are first converted to
    ``bytes``, then decoded before being stored.  If decoding fails, the
    ``bytes`` object is stored instead.  (This makes it possible for users to
    manually pre-encode a value in case this class's encoding behavior is not
    suitable for the attribute.)

    ``bytes`` objects are decoded from UTF-8, with one exception: If the
    attribute name is ``'unicodePwd'``, the values are decoded according to `the
    Microsoft AD password specification
    <https://msdn.microsoft.com/en-us/library/cc223248.aspx>`_.
    """

    def __init__(self, attr, vals=None):
        self.attr = attr
        super().__init__(vals)

    # Used by collections.abc.MutableSet to construct a new AttributeValueSet
    # object for operations such as set difference.
    def _from_iterable(self, it):
        return type(self)(self.attr, it)

    def _decode_val(self, v):
        if isinstance(v, str):
            return v
        v = bytes(v)
        try:
            if self.attr == "unicodePwd":
                tmp = v.decode("utf-16-le")
                if len(tmp) < 2 or tmp[0] != '"' or tmp[-1] != '"':
                    raise ValueError("not enclosed in double quotes")
                return tmp[1:-1]
            else:
                return v.decode()
        except:  # pylint: disable=bare-except
            pass
        return v

    def _encode_val(self, v):
        if isinstance(v, bytes):
            return v
        assert isinstance(v, str)
        if self.attr == "unicodePwd":
            return f'"{v}"'.encode("utf-16-le")
        return v.encode()

    def encode(self):
        """Encodes the values for writing to LDAP.

        When writing to LDAP, the Python ``ldap`` module `expects attribute
        values to be ``bytes`` objects
        <https://www.python-ldap.org/en/python-ldap-3.4.2/bytes_mode.html>`_.

        :returns:
            A list of ``bytes`` objects containing the encoded values.  See the
            class description for details about how the values are encoded.
        """
        return [self._encode_val(v) for v in self]

    def copy(self):
        return self.__class__(self.attr, self)

    def __contains__(self, key):
        return super().__contains__(self._decode_val(key))

    def add(self, key):
        return super().add(self._decode_val(key))

    def index(self, key):
        return super().index(self._decode_val(key))

    def __eq__(self, other):
        if other is None:
            return False
        if other is self:
            return True
        return set(self) == {self._decode_val(v) for v in other}

    def __repr__(self):
        return f"{self.__class__.__name__}({self.attr!r}, {list(self)!r})"


class LDAPError(Exception):
    """Base class of all LDAP exceptions raised by backends.

    This is only used for errors encountered while interacting with
    the LDAP server; usage errors (e.g., invalid backend name) will
    have a different type.

    :ivar cause: backend exception object, if applicable
    """

    def __init__(self, message, cause=None):
        super().__init__(message)
        self.cause = cause
