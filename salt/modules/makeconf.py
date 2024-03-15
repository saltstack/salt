"""
Support for modifying make.conf under Gentoo

"""

import salt.utils.data
import salt.utils.files


def __virtual__():
    """
    Only work on Gentoo
    """
    if __grains__["os"] == "Gentoo":
        return "makeconf"
    return (
        False,
        "The makeconf execution module cannot be loaded: only available on Gentoo"
        " systems.",
    )


def _get_makeconf():
    """
    Find the correct make.conf. Gentoo recently moved the make.conf
    but still supports the old location, using the old location first
    """
    old_conf = "/etc/make.conf"
    new_conf = "/etc/portage/make.conf"
    if __salt__["file.file_exists"](old_conf):
        return old_conf
    elif __salt__["file.file_exists"](new_conf):
        return new_conf


def _add_var(var, value):
    """
    Add a new var to the make.conf. If using layman, the source line
    for the layman make.conf needs to be at the very end of the
    config. This ensures that the new var will be above the source
    line.
    """
    makeconf = _get_makeconf()
    layman = "source /var/lib/layman/make.conf"
    fullvar = f'{var}="{value}"'
    if __salt__["file.contains"](makeconf, layman):
        # TODO perhaps make this a function in the file module?
        cmd = [
            "sed",
            "-i",
            r"/{}/ i\{}".format(layman.replace("/", "\\/"), fullvar),
            makeconf,
        ]
        __salt__["cmd.run"](cmd)
    else:
        __salt__["file.append"](makeconf, fullvar)


def set_var(var, value):
    """
    Set a variable in the make.conf

    Return a dict containing the new value for variable::

        {'<variable>': {'old': '<old-value>',
                        'new': '<new-value>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.set_var 'LINGUAS' 'en'
    """
    makeconf = _get_makeconf()

    old_value = get_var(var)

    # If var already in file, replace its value
    if old_value is not None:
        __salt__["file.sed"](makeconf, f"^{var}=.*", f'{var}="{value}"')
    else:
        _add_var(var, value)

    new_value = get_var(var)
    return {var: {"old": old_value, "new": new_value}}


def remove_var(var):
    """
    Remove a variable from the make.conf

    Return a dict containing the new value for the variable::

        {'<variable>': {'old': '<old-value>',
                        'new': '<new-value>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.remove_var 'LINGUAS'
    """
    makeconf = _get_makeconf()

    old_value = get_var(var)

    # If var is in file
    if old_value is not None:
        __salt__["file.sed"](makeconf, f"^{var}=.*", "")

    new_value = get_var(var)
    return {var: {"old": old_value, "new": new_value}}


def append_var(var, value):
    """
    Add to or create a new variable in the make.conf

    Return a dict containing the new value for variable::

        {'<variable>': {'old': '<old-value>',
                        'new': '<new-value>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.append_var 'LINGUAS' 'en'
    """
    makeconf = _get_makeconf()

    old_value = get_var(var)

    # If var already in file, add to its value
    if old_value is not None:
        appended_value = f"{old_value} {value}"
        __salt__["file.sed"](makeconf, f"^{var}=.*", f'{var}="{appended_value}"')
    else:
        _add_var(var, value)

    new_value = get_var(var)
    return {var: {"old": old_value, "new": new_value}}


def trim_var(var, value):
    """
    Remove a value from a variable in the make.conf

    Return a dict containing the new value for variable::

        {'<variable>': {'old': '<old-value>',
                        'new': '<new-value>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.trim_var 'LINGUAS' 'en'
    """
    makeconf = _get_makeconf()

    old_value = get_var(var)

    # If var in file, trim value from its value
    if old_value is not None:
        __salt__["file.sed"](makeconf, value, "", limit=var)

    new_value = get_var(var)
    return {var: {"old": old_value, "new": new_value}}


def get_var(var):
    """
    Get the value of a variable in make.conf

    Return the value of the variable or None if the variable is not in
    make.conf

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.get_var 'LINGUAS'
    """
    makeconf = _get_makeconf()
    # Open makeconf
    with salt.utils.files.fopen(makeconf) as fn_:
        conf_file = salt.utils.data.decode(fn_.readlines())
    for line in conf_file:
        if line.startswith(var):
            ret = line.split("=", 1)[1]
            if '"' in ret:
                ret = ret.split('"')[1]
            elif "#" in ret:
                ret = ret.split("#")[0]
            ret = ret.strip()
            return ret
    return None


def var_contains(var, value):
    """
    Verify if variable contains a value in make.conf

    Return True if value is set for var

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.var_contains 'LINGUAS' 'en'
    """
    setval = get_var(var)
    # Remove any escaping that was needed to past through salt
    value = value.replace("\\", "")
    if setval is None:
        return False
    return value in setval.split()


def set_cflags(value):
    """
    Set the CFLAGS variable

    Return a dict containing the new value for variable::

        {'<variable>': {'old': '<old-value>',
                        'new': '<new-value>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.set_cflags '-march=native -O2 -pipe'
    """
    return set_var("CFLAGS", value)


def get_cflags():
    """
    Get the value of CFLAGS variable in the make.conf

    Return the value of the variable or None if the variable is
    not in the make.conf

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.get_cflags
    """
    return get_var("CFLAGS")


def append_cflags(value):
    """
    Add to or create a new CFLAGS in the make.conf

    Return a dict containing the new value for variable::

        {'<variable>': {'old': '<old-value>',
                        'new': '<new-value>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.append_cflags '-pipe'
    """
    return append_var("CFLAGS", value)


def trim_cflags(value):
    """
    Remove a value from CFLAGS variable in the make.conf

    Return a dict containing the new value for variable::

        {'<variable>': {'old': '<old-value>',
                        'new': '<new-value>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.trim_cflags '-pipe'
    """
    return trim_var("CFLAGS", value)


def cflags_contains(value):
    """
    Verify if CFLAGS variable contains a value in make.conf

    Return True if value is set for var

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.cflags_contains '-pipe'
    """
    return var_contains("CFLAGS", value)


def set_cxxflags(value):
    """
    Set the CXXFLAGS variable

    Return a dict containing the new value for variable::

        {'<variable>': {'old': '<old-value>',
                        'new': '<new-value>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.set_cxxflags '-march=native -O2 -pipe'
    """
    return set_var("CXXFLAGS", value)


def get_cxxflags():
    """
    Get the value of CXXFLAGS variable in the make.conf

    Return the value of the variable or None if the variable is
    not in the make.conf

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.get_cxxflags
    """
    return get_var("CXXFLAGS")


def append_cxxflags(value):
    """
    Add to or create a new CXXFLAGS in the make.conf

    Return a dict containing the new value for variable::

        {'<variable>': {'old': '<old-value>',
                        'new': '<new-value>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.append_cxxflags '-pipe'
    """
    return append_var("CXXFLAGS", value)


def trim_cxxflags(value):
    """
    Remove a value from CXXFLAGS variable in the make.conf

    Return a dict containing the new value for variable::

        {'<variable>': {'old': '<old-value>',
                        'new': '<new-value>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.trim_cxxflags '-pipe'
    """
    return trim_var("CXXFLAGS", value)


def cxxflags_contains(value):
    """
    Verify if CXXFLAGS variable contains a value in make.conf

    Return True if value is set for var

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.cxxflags_contains '-pipe'
    """
    return var_contains("CXXFLAGS", value)


def set_chost(value):
    """
    Set the CHOST variable

    Return a dict containing the new value for variable::

        {'<variable>': {'old': '<old-value>',
                        'new': '<new-value>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.set_chost 'x86_64-pc-linux-gnu'
    """
    return set_var("CHOST", value)


def get_chost():
    """
    Get the value of CHOST variable in the make.conf

    Return the value of the variable or None if the variable is
    not in the make.conf

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.get_chost
    """
    return get_var("CHOST")


def chost_contains(value):
    """
    Verify if CHOST variable contains a value in make.conf

    Return True if value is set for var

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.chost_contains 'x86_64-pc-linux-gnu'
    """
    return var_contains("CHOST", value)


def set_makeopts(value):
    """
    Set the MAKEOPTS variable

    Return a dict containing the new value for variable::

        {'<variable>': {'old': '<old-value>',
                        'new': '<new-value>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.set_makeopts '-j3'
    """
    return set_var("MAKEOPTS", value)


def get_makeopts():
    """
    Get the value of MAKEOPTS variable in the make.conf

    Return the value of the variable or None if the variable is
    not in the make.conf

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.get_makeopts
    """
    return get_var("MAKEOPTS")


def append_makeopts(value):
    """
    Add to or create a new MAKEOPTS in the make.conf

    Return a dict containing the new value for variable::

        {'<variable>': {'old': '<old-value>',
                        'new': '<new-value>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.append_makeopts '-j3'
    """
    return append_var("MAKEOPTS", value)


def trim_makeopts(value):
    """
    Remove a value from MAKEOPTS variable in the make.conf

    Return a dict containing the new value for variable::

        {'<variable>': {'old': '<old-value>',
                        'new': '<new-value>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.trim_makeopts '-j3'
    """
    return trim_var("MAKEOPTS", value)


def makeopts_contains(value):
    """
    Verify if MAKEOPTS variable contains a value in make.conf

    Return True if value is set for var

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.makeopts_contains '-j3'
    """
    return var_contains("MAKEOPTS", value)


def set_emerge_default_opts(value):
    """
    Set the EMERGE_DEFAULT_OPTS variable

    Return a dict containing the new value for variable::

        {'<variable>': {'old': '<old-value>',
                        'new': '<new-value>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.set_emerge_default_opts '--jobs'
    """
    return set_var("EMERGE_DEFAULT_OPTS", value)


def get_emerge_default_opts():
    """
    Get the value of EMERGE_DEFAULT_OPTS variable in the make.conf

    Return the value of the variable or None if the variable is
    not in the make.conf

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.get_emerge_default_opts
    """
    return get_var("EMERGE_DEFAULT_OPTS")


def append_emerge_default_opts(value):
    """
    Add to or create a new EMERGE_DEFAULT_OPTS in the make.conf

    Return a dict containing the new value for variable::

        {'<variable>': {'old': '<old-value>',
                        'new': '<new-value>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.append_emerge_default_opts '--jobs'
    """
    return append_var("EMERGE_DEFAULT_OPTS", value)


def trim_emerge_default_opts(value):
    """
    Remove a value from EMERGE_DEFAULT_OPTS variable in the make.conf

    Return a dict containing the new value for variable::

        {'<variable>': {'old': '<old-value>',
                        'new': '<new-value>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.trim_emerge_default_opts '--jobs'
    """
    return trim_var("EMERGE_DEFAULT_OPTS", value)


def emerge_default_opts_contains(value):
    """
    Verify if EMERGE_DEFAULT_OPTS variable contains a value in make.conf

    Return True if value is set for var

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.emerge_default_opts_contains '--jobs'
    """
    return var_contains("EMERGE_DEFAULT_OPTS", value)


def set_gentoo_mirrors(value):
    """
    Set the GENTOO_MIRRORS variable

    Return a dict containing the new value for variable::

        {'<variable>': {'old': '<old-value>',
                        'new': '<new-value>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.set_gentoo_mirrors 'http://distfiles.gentoo.org'
    """
    return set_var("GENTOO_MIRRORS", value)


def get_gentoo_mirrors():
    """
    Get the value of GENTOO_MIRRORS variable in the make.conf

    Return the value of the variable or None if the variable is
    not in the make.conf

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.get_gentoo_mirrors
    """
    return get_var("GENTOO_MIRRORS")


def append_gentoo_mirrors(value):
    """
    Add to or create a new GENTOO_MIRRORS in the make.conf

    Return a dict containing the new value for variable::

        {'<variable>': {'old': '<old-value>',
                        'new': '<new-value>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.append_gentoo_mirrors 'http://distfiles.gentoo.org'
    """
    return append_var("GENTOO_MIRRORS", value)


def trim_gentoo_mirrors(value):
    """
    Remove a value from GENTOO_MIRRORS variable in the make.conf

    Return a dict containing the new value for variable::

        {'<variable>': {'old': '<old-value>',
                        'new': '<new-value>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.trim_gentoo_mirrors 'http://distfiles.gentoo.org'
    """
    return trim_var("GENTOO_MIRRORS", value)


def gentoo_mirrors_contains(value):
    """
    Verify if GENTOO_MIRRORS variable contains a value in make.conf

    Return True if value is set for var

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.gentoo_mirrors_contains 'http://distfiles.gentoo.org'
    """
    return var_contains("GENTOO_MIRRORS", value)


def set_sync(value):
    """
    Set the SYNC variable

    Return a dict containing the new value for variable::

        {'<variable>': {'old': '<old-value>',
                        'new': '<new-value>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.set_sync 'rsync://rsync.namerica.gentoo.org/gentoo-portage'
    """
    return set_var("SYNC", value)


def get_sync():
    """
    Get the value of SYNC variable in the make.conf

    Return the value of the variable or None if the variable is
    not in the make.conf

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.get_sync
    """
    return get_var("SYNC")


def sync_contains(value):
    """
    Verify if SYNC variable contains a value in make.conf

    Return True if value is set for var

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.sync_contains 'rsync://rsync.namerica.gentoo.org/gentoo-portage'
    """
    return var_contains("SYNC", value)


def get_features():
    """
    Get the value of FEATURES variable in the make.conf

    Return the value of the variable or None if the variable is
    not in the make.conf

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.get_features
    """
    return get_var("FEATURES")


def append_features(value):
    """
    Add to or create a new FEATURES in the make.conf

    Return a dict containing the new value for variable::

        {'<variable>': {'old': '<old-value>',
                        'new': '<new-value>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.append_features 'webrsync-gpg'
    """
    return append_var("FEATURES", value)


def trim_features(value):
    """
    Remove a value from FEATURES variable in the make.conf

    Return a dict containing the new value for variable::

        {'<variable>': {'old': '<old-value>',
                        'new': '<new-value>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.trim_features 'webrsync-gpg'
    """
    return trim_var("FEATURES", value)


def features_contains(value):
    """
    Verify if FEATURES variable contains a value in make.conf

    Return True if value is set for var

    CLI Example:

    .. code-block:: bash

        salt '*' makeconf.features_contains 'webrsync-gpg'
    """
    return var_contains("FEATURES", value)
