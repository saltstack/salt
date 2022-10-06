"""
Manage entries in an LDAP database
==================================

.. versionadded:: 2016.3.0

The ``states.ldap`` state module allows you to manage LDAP entries and
their attributes.
"""

import logging
from collections import OrderedDict

from salt.utils.ldap import AttributeValueSet, LDAPError
from salt.utils.oset import OrderedSet

log = logging.getLogger(__name__)


def managed(name, entries, connect_spec=None):
    """Ensure the existence (or not) of LDAP entries and their attributes.

    Example:

    .. code-block:: yaml

        ldapi:///:
          ldap.managed:
            - connect_spec:
                bind:
                  method: sasl

            - entries:

              # make sure the entry doesn't exist
              - cn=foo,ou=users,dc=example,dc=com:
                - delete_others: True

              # make sure the entry exists with only the specified
              # attribute values
              - cn=admin,dc=example,dc=com:
                - delete_others: True
                - replace:
                    cn:
                      - admin
                    description:
                      - LDAP administrator
                    objectClass:
                      - simpleSecurityObject
                      - organizationalRole
                    userPassword:
                      - {{pillar.ldap_admin_password}}

              # make sure the entry exists, its olcRootDN attribute
              # has only the specified value, the olcRootDN attribute
              # doesn't exist, and all other attributes are ignored
              - 'olcDatabase={1}hdb,cn=config':
                - replace:
                    olcRootDN:
                      - cn=admin,dc=example,dc=com
                    # the admin entry has its own password attribute
                    olcRootPW: []

              # note the use of 'default'.  also note how you don't
              # have to use list syntax if there is only one attribute
              # value
              - cn=foo,ou=users,dc=example,dc=com:
                - delete_others: True
                - default:
                    userPassword: changeme
                    shadowLastChange: 0
                    # keep sshPublicKey if present, but don't create
                    # the attribute if it is missing
                    sshPublicKey: []
                - replace:
                    cn: foo
                    uid: foo
                    uidNumber: 1000
                    gidNumber: 1000
                    gecos: Foo Bar
                    givenName: Foo
                    sn: Bar
                    homeDirectory: /home/foo
                    loginShell: /bin/bash
                    objectClass:
                      - inetOrgPerson
                      - posixAccount
                      - top
                      - ldapPublicKey
                      - shadowAccount

    :param name:
        The URL of the LDAP server.  This is ignored if
        ``connect_spec`` is either a connection object or a dict with
        a ``'url'`` entry.

    :param entries:
        A description of the desired state of zero or more LDAP
        entries.

        ``entries`` is an iterable of dicts.  Each of these dict's
        keys are the distinguished names (DNs) of LDAP entries to
        manage.  Each of these dicts is processed in order.  A later
        dict can reference an LDAP entry that was already mentioned in
        an earlier dict, which makes it possible for later dicts to
        enhance or alter the desired state of an LDAP entry.

        The DNs are mapped to a description of the LDAP entry's
        desired state.  These LDAP entry descriptions are themselves
        iterables of dicts.  Each dict in the iterable is processed in
        order.  They contain directives controlling the entry's state.
        The key names the directive type and the value is state
        information for the directive.  The specific structure of the
        state information depends on the directive type.

        The structure of ``entries`` looks like this::

            [{dn1: [{directive1: directive1_state,
                     directive2: directive2_state},
                    {directive3: directive3_state}],
              dn2: [{directive4: directive4_state,
                     directive5: directive5_state}]},
             {dn3: [{directive6: directive6_state}]}]

        These are the directives:

        * ``'delete_others'``
            Boolean indicating whether to delete attributes not
            mentioned in this dict or any of the other directive
            dicts for this DN.  Defaults to ``False``.

            If you don't want to delete an attribute if present, but
            you also don't want to add it if it is missing or modify
            it if it is present, you can use either the ``'default'``
            directive or the ``'add'`` directive with an empty value
            list.

        * ``'default'``
            A dict mapping an attribute name to an iterable of default
            values for that attribute.  If the attribute already
            exists, it is left alone.  If not, it is created using the
            given list of values.

            An empty value list is useful when you don't want to
            create an attribute if it is missing but you do want to
            preserve it if the ``'delete_others'`` key is ``True``.

        * ``'add'``
            Attribute values to add to the entry.  This is a dict
            mapping an attribute name to an iterable of values to add.

            An empty value list is useful when you don't want to
            create an attribute if it is missing but you do want to
            preserve it if the ``'delete_others'`` key is ``True``.

        * ``'delete'``
            Attribute values to remove from the entry.  This is a dict
            mapping an attribute name to an iterable of values to
            delete from the attribute.  If the iterable is empty, all
            of the attribute's values are deleted.

        * ``'replace'``
            Attribute values that will replace any existing values.  This is a
            dict (which may be empty) mapping an attribute name to an iterable
            (which may be empty) of values.

        In the above directives, the iterables of attribute values may
        instead be ``None``, in which case an empty list is used, or a
        scalar such as a string or number, in which case a new list
        containing the scalar is used.

        Note that if all attribute values are removed from an entry,
        the entire entry is deleted.

        `RFC 4511 section 4.1.7
        <https://datatracker.ietf.org/doc/html/rfc4511#section-4.1.7>`_ says,
        "The set of attribute values is unordered."  Despite this, if an
        attribute has more than one new value, the new values are sent to the
        server in the given order in case order is meaningful to the server (as
        an extension to the standard).

    :param connect_spec:
        See the description of the ``connect_spec`` parameter of the
        :py:func:`ldap3.connect <salt.modules.ldap3.connect>` function
        in the :py:mod:`ldap3 <salt.modules.ldap3>` execution module.
        If this is a dict and the ``'url'`` entry is not specified,
        the ``'url'`` entry is set to the value of the ``name``
        parameter.

    :returns:
        A dict with the following keys:

        * ``'name'``
            This is the same object passed to the ``name`` parameter.

        * ``'changes'``
            This is a dict describing the changes made (or, in test
            mode, the changes that would have been attempted).  If no
            changes were made (or no changes would have been
            attempted), then this dict is empty.  Only successful
            changes are included.

            Each key is a DN of an entry that was changed (or would
            have been changed).  Entries that were not changed (or
            would not have been changed) are not included.  The value
            is a dict with two keys:

            * ``'old'``
                The state of the entry before modification.  If the
                entry did not previously exist, this key maps to
                ``None``.  Otherwise, the value is a dict mapping each
                of the old entry's attributes to a list of its values
                before any modifications were made.  Unchanged
                attributes are excluded from this dict.

            * ``'new'``
                The state of the entry after modification.  If the
                entry was deleted, this key maps to ``None``.
                Otherwise, the value is a dict mapping each of the
                entry's attributes to a list of its values after the
                modifications were made.  Unchanged attributes are
                excluded from this dict.

            Example ``'changes'`` dict where a new entry was created
            with a single attribute containing two values::

                {'dn1': {'old': None,
                         'new': {'attr1': ['val1', 'val2']}}}

            Example ``'changes'`` dict where a new attribute was added
            to an existing entry::

                {'dn1': {'old': {},
                         'new': {'attr2': ['val3']}}}

        * ``'result'``
            One of the following values:

            * ``True`` if no changes were necessary or if all changes
              were applied successfully.
            * ``False`` if at least one change was unable to be applied.
            * ``None`` if changes would be applied but it is in test
              mode.
    """
    if connect_spec is None:
        connect_spec = {}
    try:
        connect_spec.setdefault("url", name)
    except AttributeError:
        # already a connection object
        pass

    with __salt__["ldap3.connect"](connect_spec) as l:
        old, new = _process_entries(l, entries)

        dn_set = OrderedSet()
        dn_set.update(old)
        dn_set.update(new)

        # do some cleanup
        dn_to_delete = set()
        for dn in dn_set:
            o = old.get(dn, {})
            n = new.get(dn, {})
            for x in o, n:
                to_delete = set()
                for attr, vals in x.items():
                    if not vals:
                        # clean out empty attribute lists
                        to_delete.add(attr)
                for attr in to_delete:
                    del x[attr]
            if o == n:
                # clean out unchanged entries
                dn_to_delete.add(dn)
        for dn in dn_to_delete:
            for x in old, new:
                x.pop(dn, None)
            dn_set.remove(dn)

        ret = {
            "name": name,
            "changes": {},
            "result": None,
            "comment": "",
        }

        if old == new:
            ret["comment"] = "LDAP entries already set"
            ret["result"] = True
            return ret

        if __opts__["test"]:
            ret["comment"] = "Would change LDAP entries"
            changed_old = old
            changed_new = new
            success_dn_set = dn_set
        else:
            # execute the changes
            changed_old = OrderedDict()
            changed_new = OrderedDict()
            # assume success; these will be changed on error
            ret["result"] = True
            ret["comment"] = "Successfully updated LDAP entries"
            errs = []
            success_dn_set = OrderedSet()
            for dn in dn_set:
                o = old.get(dn, {})
                n = new.get(dn, {})

                try:
                    # perform the operation
                    if o:
                        if n:
                            op = "modify"
                            assert o != n
                            __salt__["ldap3.change"](l, dn, o, n)
                        else:
                            op = "delete"
                            __salt__["ldap3.delete"](l, dn)
                    else:
                        op = "add"
                        assert n
                        __salt__["ldap3.add"](l, dn, n)

                    # update these after the op in case an exception
                    # is raised
                    changed_old[dn] = o
                    changed_new[dn] = n
                    success_dn_set.add(dn)
                except LDAPError as err:
                    log.exception("failed to %s entry %s (%s)", op, dn, err)
                    errs.append((op, dn, err))
                    continue

            if errs:
                ret["result"] = False
                ret["comment"] = "failed to " + ", ".join(
                    (op + " entry " + dn + "(" + str(err) + ")" for op, dn, err in errs)
                )

    # set ret['changes'].  filter out any unchanged attributes, and
    # convert the value sets to lists before returning them to the
    # user.
    for dn in success_dn_set:
        o = changed_old.get(dn, {})
        n = changed_new.get(dn, {})
        changes = {}
        ret["changes"][dn] = changes
        for x, xn in ((o, "old"), (n, "new")):
            if not x:
                changes[xn] = None
                continue
            changes[xn] = {
                attr: list(vals)
                for attr, vals in x.items()
                if (
                    o.get(attr, AttributeValueSet())
                    != n.get(attr, AttributeValueSet())
                )
            }

    return ret


def _process_entries(l, entries):
    """Helper for managed() to process entries and obtain before/after views.

    Collects the current database state and updates it according to the data in
    :py:func:`managed`'s ``entries`` parameter. Returns the current database
    state and what it will look like after modification.

    :param l:
        The LDAP connection object.

    :param entries:
        The same object passed to the ``entries`` parameter of
        :py:func:`manage`.

    :returns:
        An ``(old, new)`` tuple that describes the current state of the entries
        and what they will look like after modification. Each item in the tuple
        is an ``OrderedDict`` that maps an entry DN to a ``dict`` that maps an
        attribute name to an :py:class:`~salt.utils.ldap.AttributeValueSet` of
        its values. The structure looks like this::

            OrderedDict([(dn1, {attr1: AttributeValueSet([val1])}),
                         (dn2, {attr1: AttributeValueSet([val2]),
                                attr2: AttributeValueSet([val3, val4])})])

        All of an entry's attributes and values will be included, even if they
        will not be modified. If an entry mentioned in ``entries`` does not yet
        exist in the database, the DN in ``old`` will be mapped to an empty
        ``dict``. If an entry in the database will be deleted, the DN in ``new``
        will be mapped to an empty ``dict``. All value sets are non-empty: An
        attribute that will be added to an entry is not included in ``old``, and
        an attribute that will be deleted from an entry is not included in
        ``new``.

        These are ``OrderedDicts`` to ensure that the user-supplied entries are
        processed in the user-specified order (in case there are dependencies,
        such as ACL rules specified in an early entry that make it possible to
        modify a later entry).
    """

    old = OrderedDict()
    new = OrderedDict()

    for entries_dict in entries:
        for dn, directives_seq in entries_dict.items():
            # get the old entry's state.  first check to see if we've
            # previously processed the entry.
            olde = new.get(dn, None)
            if olde is None:
                # next check the database
                results = __salt__["ldap3.search"](l, dn, "base")
                if len(results) == 1:
                    attrs = results[dn]
                    olde = {
                        attr: AttributeValueSet(vals)
                        for attr, vals in attrs.items()
                        if len(vals)
                    }
                else:
                    # nothing, so it must be a brand new entry
                    assert len(results) == 0
                    olde = {}
                old[dn] = olde
            # Deep copy the old entry to create the new (don't do a simple
            # assignment or else modifications to `newe` will affect `olde`).
            newe = {attr: AttributeValueSet(vals) for attr, vals in olde.items()}
            new[dn] = newe

            # process the directives
            entry_status = {
                "delete_others": False,
                "mentioned_attributes": set(),
            }
            for directives in directives_seq:
                _update_entry(newe, entry_status, directives)
            if entry_status["delete_others"]:
                to_delete = set()
                for attr in newe:
                    if attr not in entry_status["mentioned_attributes"]:
                        to_delete.add(attr)
                for attr in to_delete:
                    del newe[attr]
    return old, new


def _update_entry(entry, status, directives):
    """Update an entry's attributes using the provided directives

    :param entry:
        A dict mapping each attribute name to a set of its values
    :param status:
        A dict holding cross-invocation status (whether delete_others
        is True or not, and the set of mentioned attributes)
    :param directives:
        A dict mapping directive types to directive-specific state
    """
    for directive, state in directives.items():
        if directive == "delete_others":
            status["delete_others"] = state
            continue
        for attr, vals in state.items():
            status["mentioned_attributes"].add(attr)
            vals = _toset(vals)
            if directive == "default":
                if vals and (attr not in entry or not entry[attr]):
                    entry[attr] = vals
            elif directive == "add":
                existing_vals = entry.get(attr, AttributeValueSet())
                # Preserve the order of pre-existing values by updating
                # existing_vals with vals rather than the other way around.
                existing_vals |= vals
                if existing_vals:
                    entry[attr] = existing_vals
            elif directive == "delete":
                existing_vals = entry.pop(attr, AttributeValueSet())
                if vals:
                    existing_vals -= vals
                    if existing_vals:
                        entry[attr] = existing_vals
            elif directive == "replace":
                existing_vals = entry.pop(attr, AttributeValueSet())
                # Preserve the order of pre-existing values by first keeping
                # the common values then inserting the new values.
                existing_vals &= vals
                existing_vals |= vals
                if existing_vals:
                    entry[attr] = existing_vals
            else:
                raise ValueError("unknown directive: " + directive)


def _normalize(thing):
    """Convert thing to bytes.

    Details:
      * bytes-like values are copied and returned.
      * str values are encoded to UTF-8 bytes.
      * int values (including Booleans) are converted to str then encoded.
      * Everything else raises an exception.
    """
    try:
        # If thing is already a bytes-like object, return a copy of the bytes.
        # The intermediate call to memoryview prevents this function from
        # interpreting an iterable of 8-bit integer values as a string of bytes.
        thing = bytes(memoryview(thing))
    except:  # pylint: disable=bare-except
        pass
    if isinstance(thing, int):
        thing = str(thing)
    if isinstance(thing, str):
        thing = thing.encode()
    if not isinstance(thing, bytes):
        raise TypeError(f"expected an int, str, or bytes-like value, got {type(thing)}")
    return thing


def _toset(thing):
    """Helper to convert various things to an ``AttributeValueSet``.

    This enables flexibility in what users provide as the list of LDAP entry
    attribute values.

    Details:
      * ``None`` becomes a new empty set.
      * ``bytes``-like, ``str``, and ``int`` values are normalized with
        ``_normalize()`` and returned as the only member of a new set.
      * Other values are assumed to be iterables of values to normalize and
        return in the new set.  (If it is not an iterable, or if an entry can't
        be normalized, an exception is raised).
    """
    if thing is None:
        coll = ()
    else:
        try:
            coll = (_normalize(thing),)
        except TypeError:
            coll = (_normalize(x) for x in thing)
    return AttributeValueSet(coll)
