def get(key, default=KeyError, merge=False, delimiter=':', merge_lists=False):
    """
    .. versionadded:: 0.14.0

    Attempt to retrieve the named value from pillar. If the value isn't found,
    return the ``default`` value. If the ``default`` is not specified, then
    raise a ``KeyError``.

    The value can also be a path to the value to retrieve, e.g., ``'foo:bar'``
    will return ``pillar['foo']['bar']`` if it exists.

    The ``default`` value is returned if the key is not found; the default is
    ``KeyError`` (a class, not an instance), which when used as a sentinel
    causes a ``KeyError`` to be raised if the key is missing. You can pass any
    other value to be returned instead, e.g., ``None`` or an empty dict.

    CLI Example:

    .. code-block:: bash

        salt '*' pillar.get "key"
        salt '*' pillar.get "key:{subkey}" default=None
    """
