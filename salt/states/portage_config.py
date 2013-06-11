'''
Management of Portage package configuration on Gentoo
=====================================================

A state module to manage Portage configuration on Gentoo

.. code-block:: yaml

    salt:
        portage_config.flags:
            - use:
                - openssl
'''

def __virtual__():
    '''
    Only load if the portage_config module is available in __salt__
    '''
    return 'portage_config' if 'portage_config.get_missing_flags' in __salt__ else False

def mod_init(low):
    '''
    Enforce a nice structure on the configuration files.
    '''
    __salt__['portage_config.enforce_nice_config']()
    return True

def _flags_helper(conf, atom, flags, test=False):
    flags = __salt__['portage_config.get_missing_flags'](conf, atom, flags)
    if flags:
        old_flags = __salt__['portage_config.get_flags_from_package_conf'](conf, atom)
        if not test:
            __salt__['portage_config.append_to_package_conf'](conf, atom, flags)
        return {'old': old_flags, 'new': flags}
    return None

def _mask_helper(conf, atom, test=False):
    is_present = __salt__['portage_config.is_present'](conf, atom)
    if not is_present:
        if not test:
            __salt__['portage_config.append_to_package_conf'](conf, string = atom)
        return True
    return False

def flags(name, use=[], accept_keywords=[], env=[], license=[], properties=[], unmask=False, mask=False):
    '''
    Enforce the given flags on the given package or DEPEND atom.
    Please be warned that, in most cases, you need to rebuild the affected packages in
    order to apply the changes.

    name
        The name of the package or his DEPEND atom
    use
        A list of use flags
    accept_keywords
        A list of keywords to accept. "~ARCH" means current host arch, and will
        be translated in a line without keywords
    env
        A list of enviroment files
    license
        A list of accepted licenses
    properties
        A list of additional properties
    unmask
        A boolean to unmask the package
    mask
        A boolean to mask the package
    '''
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}

    if use:
        changes = _flags_helper('use', name, use, __opts__['test'])
        if changes:
            ret['changes']['use'] = changes

    if accept_keywords:
        changes = _flags_helper('accept_keywords', name, accept_keywords, __opts__['test'])
        if changes:
            ret['changes']['accept_keywords'] = changes

    if env:
        changes = _flags_helper('env', name, env, __opts__['test'])
        if changes:
            ret['changes']['env'] = changes

    if license:
        changes = _flags_helper('license', name, license, __opts__['test'])
        if changes:
            ret['changes']['license'] = changes

    if properties:
        changes = _flags_helper('properties', name, properties, __opts__['test'])
        if changes:
            ret['changes']['properties'] = changes

    if mask:
        if _mask_helper('mask', name, __opts__['test']):
            ret['changes']['mask'] = 'masked'

    if unmask:
        if _mask_helper('unmask', name, __opts__['test']):
            ret['changes']['unmask'] = 'unmasked'

    if __opts__['test']:
        ret['result'] = None

    return ret
