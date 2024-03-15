"""
Query and modify an LDAP database (alternative interface)
=========================================================

.. versionadded:: 2016.3.0

This is an alternative to the ``ldap`` interface provided by the
:py:mod:`ldapmod <salt.modules.ldapmod>` execution module.

:depends: - ``ldap`` Python module
"""

import logging

import salt.utils.data

available_backends = set()
try:
    import ldap
    import ldap.ldapobject  # pylint: disable=no-name-in-module
    import ldap.modlist  # pylint: disable=no-name-in-module
    import ldap.sasl  # pylint: disable=no-name-in-module

    available_backends.add("ldap")
except ImportError:
    pass


log = logging.getLogger(__name__)


def __virtual__():
    """Only load this module if the Python ldap module is present"""
    if available_backends:
        return True
    return False


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


def _convert_exception(e):
    """Convert an ldap backend exception to an LDAPError and raise it."""
    raise LDAPError(f"exception in ldap backend: {e!r}", e) from e


def _bind(l, bind=None):
    """Bind helper."""
    if bind is None:
        return
    method = bind.get("method", "simple")
    if method is None:
        return
    elif method == "simple":
        l.simple_bind_s(bind.get("dn", ""), bind.get("password", ""))
    elif method == "sasl":
        sasl_class = getattr(ldap.sasl, bind.get("mechanism", "EXTERNAL").lower())
        creds = bind.get("credentials", None)
        if creds is None:
            creds = {}
        auth = sasl_class(*creds.get("args", []), **creds.get("kwargs", {}))
        l.sasl_interactive_bind_s(bind.get("dn", ""), auth)
    else:
        raise ValueError(
            'unsupported bind method "'
            + method
            + '"; supported bind methods: simple sasl'
        )


def _format_unicode_password(pwd):
    """Formats a string per Microsoft AD password specifications.
    The string must be enclosed in double quotes and UTF-16 encoded.
    See: https://msdn.microsoft.com/en-us/library/cc223248.aspx

    :param pwd:
       The desired password as a string

    :returns:
        A unicode string
    """
    return f'"{pwd}"'.encode("utf-16-le")


class _connect_ctx:
    def __init__(self, c):
        self.c = c

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass


def connect(connect_spec=None):
    """Connect and optionally bind to an LDAP server.

    :param connect_spec:
        This can be an LDAP connection object returned by a previous
        call to :py:func:`connect` (in which case the argument is
        simply returned), ``None`` (in which case an empty dict is
        used), or a dict with the following keys:

        * ``'backend'``
            Optional; default depends on which Python LDAP modules are
            installed.  Name of the Python LDAP module to use.  Only
            ``'ldap'`` is supported at the moment.

        * ``'url'``
            Optional; defaults to ``'ldapi:///'``.  URL to the LDAP
            server.

        * ``'bind'``
            Optional; defaults to ``None``.  Describes how to bind an
            identity to the LDAP connection.  If ``None``, an
            anonymous connection is made.  Valid keys:

            * ``'method'``
                Optional; defaults to ``None``.  The authentication
                method to use.  Valid values include but are not
                necessarily limited to ``'simple'``, ``'sasl'``, and
                ``None``.  If ``None``, an anonymous connection is
                made.  Available methods depend on the chosen backend.

            * ``'mechanism'``
                Optional; defaults to ``'EXTERNAL'``.  The SASL
                mechanism to use.  Ignored unless the method is
                ``'sasl'``.  Available methods depend on the chosen
                backend and the server's capabilities.

            * ``'credentials'``
                Optional; defaults to ``None``.  An object specific to
                the chosen SASL mechanism and backend that represents
                the authentication credentials.  Ignored unless the
                method is ``'sasl'``.

                For the ``'ldap'`` backend, this is a dictionary.  If
                ``None``, an empty dict is used.  Keys:

                * ``'args'``
                    Optional; defaults to an empty list.  A list of
                    arguments to pass to the SASL mechanism
                    constructor.  See the SASL mechanism constructor
                    documentation in the ``ldap.sasl`` Python module.

                * ``'kwargs'``
                    Optional; defaults to an empty dict.  A dict of
                    keyword arguments to pass to the SASL mechanism
                    constructor.  See the SASL mechanism constructor
                    documentation in the ``ldap.sasl`` Python module.

            * ``'dn'``
                Optional; defaults to an empty string.  The
                distinguished name to bind.

            * ``'password'``
                Optional; defaults to an empty string.  Password for
                binding.  Ignored if the method is ``'sasl'``.

        * ``'tls'``
            Optional; defaults to ``None``.  A backend-specific object
            containing settings to override default TLS behavior.

            For the ``'ldap'`` backend, this is a dictionary.  Not all
            settings in this dictionary are supported by all versions
            of ``python-ldap`` or the underlying TLS library.  If
            ``None``, an empty dict is used.  Possible keys:

            * ``'starttls'``
                If present, initiate a TLS connection using StartTLS.
                (The value associated with this key is ignored.)

            * ``'cacertdir'``
                Set the path of the directory containing CA
                certificates.

            * ``'cacertfile'``
                Set the pathname of the CA certificate file.

            * ``'certfile'``
                Set the pathname of the certificate file.

            * ``'cipher_suite'``
                Set the allowed cipher suite.

            * ``'crlcheck'``
                Set the CRL evaluation strategy.  Valid values are
                ``'none'``, ``'peer'``, and ``'all'``.

            * ``'crlfile'``
                Set the pathname of the CRL file.

            * ``'dhfile'``
                Set the pathname of the file containing the parameters
                for Diffie-Hellman ephemeral key exchange.

            * ``'keyfile'``
                Set the pathname of the certificate key file.

            * ``'newctx'``
                If present, instruct the underlying TLS library to
                create a new TLS context.  (The value associated with
                this key is ignored.)

            * ``'protocol_min'``
                Set the minimum protocol version.

            * ``'random_file'``
                Set the pathname of the random file when
                ``/dev/random`` and ``/dev/urandom`` are not
                available.

            * ``'require_cert'``
                Set the certificate validation policy.  Valid values
                are ``'never'``, ``'hard'``, ``'demand'``,
                ``'allow'``, and ``'try'``.

        * ``'opts'``
            Optional; defaults to ``None``.  A backend-specific object
            containing options for the backend.

            For the ``'ldap'`` backend, this is a dictionary of
            OpenLDAP options to set.  If ``None``, an empty dict is
            used.  Each key is a the name of an OpenLDAP option
            constant without the ``'LDAP_OPT_'`` prefix, then
            converted to lower case.

    :returns:
        an object representing an LDAP connection that can be used as
        the ``connect_spec`` argument to any of the functions in this
        module (to avoid the overhead of making and terminating
        multiple connections).

        This object should be used as a context manager.  It is safe
        to nest ``with`` statements.

    CLI Example:

    .. code-block:: bash

        salt '*' ldap3.connect "{
            'url': 'ldaps://ldap.example.com/',
            'bind': {
                'method': 'simple',
                'dn': 'cn=admin,dc=example,dc=com',
                'password': 'secret'}
        }"
    """
    if isinstance(connect_spec, _connect_ctx):
        return connect_spec
    if connect_spec is None:
        connect_spec = {}
    backend_name = connect_spec.get("backend", "ldap")
    if backend_name not in available_backends:
        raise ValueError(
            "unsupported backend or required Python module"
            + f" unavailable: {backend_name}"
        )
    url = connect_spec.get("url", "ldapi:///")
    try:
        l = ldap.initialize(url)
        l.protocol_version = ldap.VERSION3

        # set up tls
        tls = connect_spec.get("tls", None)
        if tls is None:
            tls = {}
        vars = {}
        for k, v in tls.items():
            if k in ("starttls", "newctx"):
                vars[k] = True
            elif k in ("crlcheck", "require_cert"):
                l.set_option(
                    getattr(ldap, "OPT_X_TLS_" + k.upper()),
                    getattr(ldap, "OPT_X_TLS_" + v.upper()),
                )
            else:
                l.set_option(getattr(ldap, "OPT_X_TLS_" + k.upper()), v)
        if vars.get("starttls", False):
            l.start_tls_s()
        if vars.get("newctx", False):
            l.set_option(ldap.OPT_X_TLS_NEWCTX, 0)

        # set up other options
        l.set_option(ldap.OPT_REFERRALS, 0)
        opts = connect_spec.get("opts", None)
        if opts is None:
            opts = {}
        for k, v in opts.items():
            opt = getattr(ldap, "OPT_" + k.upper())
            l.set_option(opt, v)

        _bind(l, connect_spec.get("bind", None))
    except ldap.LDAPError as e:
        _convert_exception(e)
    return _connect_ctx(l)


def search(
    connect_spec,
    base,
    scope="subtree",
    filterstr="(objectClass=*)",
    attrlist=None,
    attrsonly=0,
):
    """Search an LDAP database.

    :param connect_spec:
        See the documentation for the ``connect_spec`` parameter for
        :py:func:`connect`.

    :param base:
        Distinguished name of the entry at which to start the search.

    :param scope:
        One of the following:

        * ``'subtree'``
            Search the base and all of its descendants.

        * ``'base'``
            Search only the base itself.

        * ``'onelevel'``
            Search only the base's immediate children.

    :param filterstr:
        String representation of the filter to apply in the search.

    :param attrlist:
        Limit the returned attributes to those in the specified list.
        If ``None``, all attributes of each entry are returned.

    :param attrsonly:
        If non-zero, don't return any attribute values.

    :returns:
        a dict of results.  The dict is empty if there are no results.
        The dict maps each returned entry's distinguished name to a
        dict that maps each of the matching attribute names to a list
        of its values.

    CLI Example:

    .. code-block:: bash

        salt '*' ldap3.search "{
            'url': 'ldaps://ldap.example.com/',
            'bind': {
                'method': 'simple',
                'dn': 'cn=admin,dc=example,dc=com',
                'password': 'secret',
            },
        }" "base='dc=example,dc=com'"
    """
    l = connect(connect_spec)
    scope = getattr(ldap, "SCOPE_" + scope.upper())
    try:
        results = l.c.search_s(base, scope, filterstr, attrlist, attrsonly)
    except ldap.NO_SUCH_OBJECT:
        results = []
    except ldap.LDAPError as e:
        _convert_exception(e)
    return dict(results)


def add(connect_spec, dn, attributes):
    """Add an entry to an LDAP database.

    :param connect_spec:
        See the documentation for the ``connect_spec`` parameter for
        :py:func:`connect`.

    :param dn:
        Distinguished name of the entry.

    :param attributes:
        Non-empty dict mapping each of the new entry's attributes to a
        non-empty iterable of values.

    :returns:
        ``True`` if successful, raises an exception otherwise.

    CLI Example:

    .. code-block:: bash

        salt '*' ldap3.add "{
            'url': 'ldaps://ldap.example.com/',
            'bind': {
                'method': 'simple',
                'password': 'secret',
            },
        }" "dn='dc=example,dc=com'" "attributes={'example': 'values'}"
    """
    l = connect(connect_spec)
    # convert the "iterable of values" to lists in case that's what
    # addModlist() expects (also to ensure that the caller's objects
    # are not modified)
    attributes = {
        attr: salt.utils.data.encode(list(vals)) for attr, vals in attributes.items()
    }
    log.info("adding entry: dn: %s attributes: %s", repr(dn), repr(attributes))

    if "unicodePwd" in attributes:
        attributes["unicodePwd"] = [
            _format_unicode_password(x) for x in attributes["unicodePwd"]
        ]

    modlist = ldap.modlist.addModlist(attributes)
    try:
        l.c.add_s(dn, modlist)
    except ldap.LDAPError as e:
        _convert_exception(e)
    return True


def delete(connect_spec, dn):
    """Delete an entry from an LDAP database.

    :param connect_spec:
        See the documentation for the ``connect_spec`` parameter for
        :py:func:`connect`.

    :param dn:
        Distinguished name of the entry.

    :returns:
        ``True`` if successful, raises an exception otherwise.

    CLI Example:

    .. code-block:: bash

        salt '*' ldap3.delete "{
            'url': 'ldaps://ldap.example.com/',
            'bind': {
                'method': 'simple',
                'password': 'secret'}
        }" dn='cn=admin,dc=example,dc=com'
    """
    l = connect(connect_spec)
    log.info("deleting entry: dn: %s", repr(dn))
    try:
        l.c.delete_s(dn)
    except ldap.LDAPError as e:
        _convert_exception(e)
    return True


def modify(connect_spec, dn, directives):
    """Modify an entry in an LDAP database.

    :param connect_spec:
        See the documentation for the ``connect_spec`` parameter for
        :py:func:`connect`.

    :param dn:
        Distinguished name of the entry.

    :param directives:
        Iterable of directives that indicate how to modify the entry.
        Each directive is a tuple of the form ``(op, attr, vals)``,
        where:

        * ``op`` identifies the modification operation to perform.
          One of:

          * ``'add'`` to add one or more values to the attribute

          * ``'delete'`` to delete some or all of the values from the
            attribute.  If no values are specified with this
            operation, all of the attribute's values are deleted.
            Otherwise, only the named values are deleted.

          * ``'replace'`` to replace all of the attribute's values
            with zero or more new values

        * ``attr`` names the attribute to modify

        * ``vals`` is an iterable of values to add or delete

    :returns:
        ``True`` if successful, raises an exception otherwise.

    CLI Example:

    .. code-block:: bash

        salt '*' ldap3.modify "{
            'url': 'ldaps://ldap.example.com/',
            'bind': {
                'method': 'simple',
                'password': 'secret'}
        }" dn='cn=admin,dc=example,dc=com'
        directives="('add', 'example', ['example_val'])"
    """
    l = connect(connect_spec)
    # convert the "iterable of values" to lists in case that's what
    # modify_s() expects (also to ensure that the caller's objects are
    # not modified)
    modlist = [
        (getattr(ldap, "MOD_" + op.upper()), attr, list(vals))
        for op, attr, vals in directives
    ]

    for idx, mod in enumerate(modlist):
        if mod[1] == "unicodePwd":
            modlist[idx] = (
                mod[0],
                mod[1],
                [_format_unicode_password(x) for x in mod[2]],
            )

    modlist = salt.utils.data.decode(modlist, to_str=True, preserve_tuples=True)
    try:
        l.c.modify_s(dn, modlist)
    except ldap.LDAPError as e:
        _convert_exception(e)
    return True


def change(connect_spec, dn, before, after):
    """Modify an entry in an LDAP database.

    This does the same thing as :py:func:`modify`, but with a simpler
    interface.  Instead of taking a list of directives, it takes a
    before and after view of an entry, determines the differences
    between the two, computes the directives, and executes them.

    Any attribute value present in ``before`` but missing in ``after``
    is deleted.  Any attribute value present in ``after`` but missing
    in ``before`` is added.  Any attribute value in the database that
    is not mentioned in either ``before`` or ``after`` is not altered.
    Any attribute value that is present in both ``before`` and
    ``after`` is ignored, regardless of whether that attribute value
    exists in the database.

    :param connect_spec:
        See the documentation for the ``connect_spec`` parameter for
        :py:func:`connect`.

    :param dn:
        Distinguished name of the entry.

    :param before:
        The expected state of the entry before modification.  This is
        a dict mapping each attribute name to an iterable of values.

    :param after:
        The desired state of the entry after modification.  This is a
        dict mapping each attribute name to an iterable of values.

    :returns:
        ``True`` if successful, raises an exception otherwise.

    CLI Example:

    .. code-block:: bash

        salt '*' ldap3.change "{
            'url': 'ldaps://ldap.example.com/',
            'bind': {
                'method': 'simple',
                'password': 'secret'}
        }" dn='cn=admin,dc=example,dc=com'
        before="{'example_value': 'before_val'}"
        after="{'example_value': 'after_val'}"
    """
    l = connect(connect_spec)
    # convert the "iterable of values" to lists in case that's what
    # modifyModlist() expects (also to ensure that the caller's dicts
    # are not modified)
    before = {attr: salt.utils.data.encode(list(vals)) for attr, vals in before.items()}
    after = {attr: salt.utils.data.encode(list(vals)) for attr, vals in after.items()}

    if "unicodePwd" in after:
        after["unicodePwd"] = [_format_unicode_password(x) for x in after["unicodePwd"]]

    modlist = ldap.modlist.modifyModlist(before, after)

    try:
        l.c.modify_s(dn, modlist)
    except ldap.LDAPError as e:
        _convert_exception(e)
    return True
