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
    """
    pass


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
