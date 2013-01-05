'''
Support for modifying make.conf under Gentoo

'''

def __virtual__():
    '''
    Only work on Gentoo
    '''
    if __grains__['os'] == 'Gentoo':
        return 'makeconf'
    return False

def _get_makeconf():
    '''
    Find the correct make.conf. Gentoo recently moved the make.conf
    but still supports the old location, using the old location first
    '''
    old_conf = '/etc/make.conf'
    new_conf = '/etc/portage/make.conf'
    if __salt__['file.file_exists'](old_conf):
        return old_conf
    elif __salt__['file.file_exists'](new_conf):
        return new_conf

def _add_var(var, value):
    '''
    Add a new var to the make.conf. If using layman, the source line
    for the layman make.conf needs to be at the very end of the
    config. This ensures that the new var will be above the source
    line.
    '''
    makeconf = _get_makeconf()
    layman = 'source /var/lib/layman/make.conf'
    fullvar = '{0}="{1}"'.format(var, value)
    if __salt__['file.contains'](makeconf, layman):
        # TODO perhaps make this a function in the file module?
        cmd = r"sed -i '/{0}/ i\{1}' {2}".format(
            layman.replace("/", "\/"),
            fullvar,
            makeconf)
        print cmd
        __salt__['cmd.run'](cmd)
    else:
        __salt__['file.append'](makeconf, fullvar)

def set_var(var, value):
    '''
    Set a variable in the make.conf

    Return a dict containing the new value for variable::

        {'<variable>': {'old': '<old-value>',
                        'new': '<new-value>'}}

    CLI Example::

        salt '*' makeconf.set_var 'LINGUAS' 'en'
    '''
    makeconf = _get_makeconf()

    old_value = get_var(var)

    # If var already in file, replace its value
    if old_value is not None:
        __salt__['file.sed'](makeconf, '^{0}=.*'.format(var),
                             '{0}="{1}"'.format(var, value))
    else:
        _add_var(var, value)

    new_value = get_var(var)
    return {var: {'old': old_value, 'new': new_value}}

def get_var(var):
    '''
    Get the value of a variable in the make.conf

    Return the value of the variable or None if the variable is
    not in the make.conf

    CLI Example::

        salt '*' makeconf.get_var 'LINGUAS'
    '''
    makeconf = _get_makeconf()
    cmd = 'grep "{0}" {1} | grep -vE "^#"'.format(var, makeconf)
    out = __salt__['cmd.run'](cmd).split('=')
    try:
        ret = out[1].replace('"', '')
        return ret
    except IndexError:
        return None
