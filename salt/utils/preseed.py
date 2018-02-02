# -*- coding: utf-8 -*-
'''
Utilities for managing Debian preseed

.. versionadded:: Beryllium
'''
from __future__ import absolute_import, print_function, unicode_literals
import shlex
import salt.utils.files
import salt.utils.stringutils
import salt.utils.yaml


def mksls(src, dst=None):
    '''
    Convert a preseed file to an SLS file
    '''
    ps_opts = {}
    with salt.utils.files.fopen(src, 'r') as fh_:
        for line in fh_:
            line = salt.utils.stringutils.to_unicode(line)
            if line.startswith('#'):
                continue
            if not line.strip():
                continue

            comps = shlex.split(line)
            if comps[0] not in ps_opts.keys():
                ps_opts[comps[0]] = {}
            cmds = comps[1].split('/')

            pointer = ps_opts[comps[0]]
            for cmd in cmds:
                pointer = pointer.setdefault(cmd, {})

            pointer['type'] = comps[2]
            if len(comps) > 3:
                pointer['argument'] = comps[3]

    sls = {}

    # Set language
    # ( This looks like it maps to something else )
    sls[ps_opts['d-i']['languagechooser']['language-name-fb']['argument']] = {
        'locale': ['system']
        }

    # Set keyboard
    # ( This looks like it maps to something else )
    sls[ps_opts['d-i']['kbd-chooser']['method']['argument']] = {
        'keyboard': ['system']
        }

    # Set timezone
    timezone = ps_opts['d-i']['time']['zone']['argument']
    sls[timezone] = {'timezone': ['system']}
    if ps_opts['d-i']['tzconfig']['gmt']['argument'] == 'true':
        sls[timezone]['timezone'].append('utc')

    # Set network
    if 'netcfg' in ps_opts['d-i'].keys():
        iface = ps_opts['d-i']['netcfg']['choose_interface']['argument']
        sls[iface] = {}
        sls[iface]['enabled'] = True
        if ps_opts['d-i']['netcfg']['confirm_static'] == 'true':
            sls[iface]['proto'] = 'static'
        elif ps_opts['d-i']['netcfg']['disable_dhcp'] == 'false':
            sls[iface]['proto'] = 'dhcp'
        sls[iface]['netmask'] = ps_opts['d-i']['netcfg']['get_netmask']['argument']
        sls[iface]['domain'] = ps_opts['d-i']['netcfg']['get_domain']['argument']
        sls[iface]['gateway'] = ps_opts['d-i']['netcfg']['get_gateway']['argument']
        sls[iface]['hostname'] = ps_opts['d-i']['netcfg']['get_hostname']['argument']
        sls[iface]['ipaddress'] = ps_opts['d-i']['netcfg']['get_ipaddress']['argument']
        sls[iface]['nameservers'] = ps_opts['d-i']['netcfg']['get_nameservers']['argument']

    if dst is not None:
        with salt.utils.files.fopen(dst, 'w') as fh_:
            salt.utils.yaml.safe_dump(sls, fh_, default_flow_style=False)
    else:
        return salt.utils.yaml.safe_dump(sls, default_flow_style=False)
