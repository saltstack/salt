# -*- coding: utf-8 -*-
'''
Utilities for managing kickstart

.. versionadded:: Beryllium
'''
from __future__ import absolute_import, unicode_literals
import shlex
import argparse  # pylint: disable=minimum-python-version
import salt.utils.files
import salt.utils.yaml
from salt.ext.six.moves import range


def clean_args(args):
    '''
    Cleans up the args that weren't passed in
    '''
    for arg in args:
        if not args[arg]:
            del args[arg]
    return args


def parse_auth(rule):
    '''
    Parses the auth/authconfig line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    noargs = ('back', 'test', 'nostart', 'kickstart', 'probe', 'enablecache',
              'disablecache', 'disablenis', 'enableshadow', 'disableshadow',
              'enablemd5', 'disablemd5', 'enableldap', 'enableldapauth',
              'enableldaptls', 'disableldap', 'disableldapauth',
              'enablekrb5kdcdns', 'disablekrb5kdcdns', 'enablekrb5realmdns',
              'disablekrb5realmdns', 'disablekrb5', 'disablehe-siod',
              'enablesmbauth', 'disablesmbauth', 'enablewinbind',
              'enablewinbindauth', 'disablewinbind', 'disablewinbindauth',
              'enablewinbindusedefaultdomain', 'disablewinbindusedefaultdomain',
              'enablewins', 'disablewins')
    for arg in noargs:
        parser.add_argument('--{0}'.format(arg), dest=arg, action='store_true')

    parser.add_argument('--enablenis', dest='enablenis', action='store')
    parser.add_argument('--hesiodrhs', dest='hesiodrhs', action='store')
    parser.add_argument('--krb5adminserver', dest='krb5adminserver',
                        action='append')
    parser.add_argument('--krb5kdc', dest='krb5kdc', action='append')
    parser.add_argument('--ldapbasedn', dest='ldapbasedn', action='store')
    parser.add_argument('--ldapserver', dest='ldapserver', action='append')
    parser.add_argument('--nisserver', dest='nisserver', action='append')
    parser.add_argument('--passalgo', dest='passalgo', action='store')
    parser.add_argument('--smbidmapgid', dest='smbidmapgid', action='store')
    parser.add_argument('--smbidmapuid', dest='smbidmapuid', action='store')
    parser.add_argument('--smbrealm', dest='smbrealm', action='store')
    parser.add_argument('--smbsecurity', dest='smbsecurity', action='store',
                        choices=['user', 'server', 'domain', 'dns'])
    parser.add_argument('--smbservers', dest='smbservers', action='store')
    parser.add_argument('--smbworkgroup', dest='smbworkgroup', action='store')
    parser.add_argument('--winbindjoin', dest='winbindjoin', action='store')
    parser.add_argument('--winbindseparator', dest='winbindseparator',
                        action='store')
    parser.add_argument('--winbindtemplatehomedir',
                        dest='winbindtemplatehomedir', action='store')
    parser.add_argument('--winbindtemplateprimarygroup',
                        dest='winbindtemplateprimarygroup', action='store')
    parser.add_argument('--winbindtemplateshell', dest='winbindtemplateshell',
                        action='store')

    parser.add_argument('--enablekrb5', dest='enablekrb5', action='store_true')
    if '--enablekrb5' in rules:
        parser.add_argument('--krb5realm', dest='krb5realm', action='store',
                            required=True)
    parser.add_argument('--enablehesiod', dest='enablehesiod',
                        action='store_true')
    if '--enablehesiod' in rules:
        parser.add_argument('--hesiodlhs', dest='hesiodlhs', action='store',
                            required=True)

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_autopart(rule):
    '''
    Parse the autopart line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--type', dest='type', action='store')
    parser.add_argument('--encrypted', dest='encrypted', action='store_true')
    parser.add_argument('--passphrase', dest='passphrase', action='store')
    parser.add_argument('--escrowcert', dest='escrowcert', action='store')
    parser.add_argument('--backuppassphrase', dest='backuppassphrase',
                        action='store')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_autostep(rule):
    '''
    Parse the autostep line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--autoscreenshot', dest='autoscreenshot',
                        action='store')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_bootloader(rule):
    '''
    Parse the bootloader line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--append', dest='append', action='store')
    parser.add_argument('--driveorder', dest='driveorder', action='store')
    parser.add_argument('--location', dest='location', action='store')
    parser.add_argument('--password', dest='password', action='store')
    parser.add_argument('--md5pass', dest='md5pass', action='store')
    parser.add_argument('--upgrade', dest='upgrade', action='store_true')
    parser.add_argument('--timeout', dest='timeout', action='store')
    parser.add_argument('--boot-drive', dest='bootdrive', action='store')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_btrfs(rule):
    '''
    Parse the btrfs line

    TODO: finish up the weird parsing on this one
    http://fedoraproject.org/wiki/Anaconda/Kickstart#btrfs
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--name', dest='name', action='store')
    parser.add_argument('--data', dest='data', action='store')
    parser.add_argument('--metadata', dest='metadata', action='store')
    parser.add_argument('--label', dest='label', action='store')
    parser.add_argument('--noformat', dest='noformat', action='store_true')
    parser.add_argument('--useexisting', dest='useexisting',
                        action='store_true')
    parser.add_argument('--subvol', dest='subvol', action='store_true')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_clearpart(rule):
    '''
    Parse the clearpart line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--all', dest='all', action='store_true')
    parser.add_argument('--drives', dest='drives', action='store')
    parser.add_argument('--init_label', dest='init_label', action='store_true')
    parser.add_argument('--linux', dest='linux', action='store_true')
    parser.add_argument('--none', dest='none', action='store_true')
    parser.add_argument('--initlabel', dest='init_label', action='store_true')
    parser.add_argument('--list', dest='list', action='store')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_device(rule):
    '''
    Parse the device line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    modulename = rules.pop(0)
    parser.add_argument('--opts', dest='opts', action='store')

    args = clean_args(vars(parser.parse_args(rules)))
    args['modulename'] = modulename
    parser = None
    return args


def parse_dmraid(rule):
    '''
    Parse the dmraid line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--name', dest='name', action='store')
    parser.add_argument('--dev', dest='dev', action='store')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_driverdisk(rule):
    '''
    Parse the driverdisk line
    '''
    if '--' not in rule:
        return {'partition': rule}

    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--source', dest='source', action='store')
    parser.add_argument('--biospart', dest='biospart', action='store')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_firewall(rule):
    '''
    Parse the firewall line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--enable', '--enabled', dest='enable',
                        action='store_true')
    parser.add_argument('--disable', '--disabled', dest='disable',
                        action='store_true')
    parser.add_argument('--port', dest='port', action='store')
    parser.add_argument('--service', dest='service', action='store')
    parser.add_argument('--ssh', dest='ssh', action='store_true')
    parser.add_argument('--smtp', dest='smtp', action='store_true')
    parser.add_argument('--http', dest='http', action='store_true')
    parser.add_argument('--ftp', dest='ftp', action='store_true')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_firstboot(rule):
    '''
    Parse the firstboot line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--enable', '--enabled', dest='enable',
                        action='store_true')
    parser.add_argument('--disable', '--disabled', dest='disable',
                        action='store_true')
    parser.add_argument('--reconfig', dest='reconfig', action='store_true')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_group(rule):
    '''
    Parse the group line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--name', dest='name', action='store')
    parser.add_argument('--gid', dest='gid', action='store')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_harddrive(rule):
    '''
    Parse the harddrive line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--biospart', dest='biospart', action='store')
    parser.add_argument('--partition', dest='partition', action='store')
    parser.add_argument('--dir', dest='dir', action='store')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_ignoredisk(rule):
    '''
    Parse the ignoredisk line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--drives', dest='drives', action='store')
    parser.add_argument('--only-use', dest='only-use', action='store')
    parser.add_argument('--interactive', dest='interactive',
                        action='store_true')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_iscsi(rule):
    '''
    Parse the iscsi line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--ipaddr', dest='ipaddr', action='store')
    parser.add_argument('--port', dest='port', action='store')
    parser.add_argument('--target', dest='target', action='store')
    parser.add_argument('--iface', dest='iface', action='store')
    parser.add_argument('--user', dest='user', action='store')
    parser.add_argument('--password', dest='password', action='store')
    parser.add_argument('--reverse-user', dest='reverse-user', action='store')
    parser.add_argument('--reverse-password', dest='reverse-password',
                        action='store')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_iscsiname(rule):
    '''
    Parse the iscsiname line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    #parser.add_argument('iqn')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_keyboard(rule):
    '''
    Parse the keyboard line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--vckeymap', dest='vckeymap', action='store')
    parser.add_argument('--xlayouts', dest='xlayouts', action='store')
    parser.add_argument('--switch', dest='switch', action='store')
    parser.add_argument('keyboard')

    args = clean_args(vars(parser.parse_args(rules)))

    if 'keyboard' in args and 'xlayouts' not in args:
        args['xlayouts'] = args['keyboard']

    parser = None
    return args


def parse_lang(rule):
    '''
    Parse the lang line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('lang')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_logvol(rule):
    '''
    Parse the logvol line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('mntpoint')
    parser.add_argument('--noformat', dest='noformat', action='store_true')
    parser.add_argument('--useexisting', dest='useexisting',
                        action='store_true')
    parser.add_argument('--fstype', dest='fstype', action='store')
    parser.add_argument('--fsoptions', dest='fsoptions', action='store')
    parser.add_argument('--grow', dest='grow', action='store_true')
    parser.add_argument('--maxsize', dest='maxsize', action='store')
    parser.add_argument('--recommended', dest='recommended',
                        action='store_true')
    parser.add_argument('--percent', dest='percent', action='store_true')
    parser.add_argument('--encrypted', dest='encrypted', action='store_true')
    parser.add_argument('--passphrase', dest='passphrase', action='store')
    parser.add_argument('--escrowcert', dest='escrowcert', action='store')
    parser.add_argument('--backuppassphrase', dest='backuppassphrase',
                        action='store_true')
    parser.add_argument('--name', dest='name', action='store')
    parser.add_argument('--vgname', dest='vgname', action='store')
    parser.add_argument('--size', dest='size', action='store')
    parser.add_argument('--label', dest='label', action='store')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_logging(rule):
    '''
    Parse the logging line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--host', dest='host', action='store')
    parser.add_argument('--port', dest='port', action='store')
    parser.add_argument('--level', dest='level', action='store',
                        choices=['debug', 'info', 'warning', 'error',
                                 'critical'])

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_monitor(rule):
    '''
    Parse the monitor line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--hsync', dest='hsync', action='store')
    parser.add_argument('--monitor', dest='monitor', action='store')
    parser.add_argument('--noprobe', dest='noprobe', action='store_true')
    parser.add_argument('--vsync', dest='vsync', action='store')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_multipath(rule):
    '''
    Parse the multipath line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--name', dest='name', action='store')
    parser.add_argument('--device', dest='device', action='store')
    parser.add_argument('--rule', dest='rule', action='store')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_network(rule):
    '''
    Parse the network line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--bootproto', dest='bootproto', action='store',
                        choices=['dhcp', 'bootp', 'static', 'ibft'])
    parser.add_argument('--device', dest='device', action='store')
    parser.add_argument('--ip', dest='ip', action='store')
    parser.add_argument('--ipv6', dest='ipv6', action='store')
    parser.add_argument('--gateway', dest='gateway', action='store')
    parser.add_argument('--nodefroute', dest='nodefroute', action='store_true')
    parser.add_argument('--nameserver', dest='nameserver', action='store')
    parser.add_argument('--nodns', dest='nodns', action='store_true')
    parser.add_argument('--netmask', dest='netmask', action='store')
    parser.add_argument('--hostname', dest='hostname', action='store')
    parser.add_argument('--ethtool', dest='ethtool', action='store')
    parser.add_argument('--essid', dest='essid', action='store')
    parser.add_argument('--wepkey', dest='wepkey', action='store')
    parser.add_argument('--wpakey', dest='wpakey', action='store')
    parser.add_argument('--onboot', dest='onboot', action='store')
    parser.add_argument('--dhcpclass', dest='dhcpclass', action='store')
    parser.add_argument('--mtu', dest='mtu', action='store')
    parser.add_argument('--noipv4', dest='noipv4', action='store_true')
    parser.add_argument('--noipv6', dest='noipv6', action='store_true')
    parser.add_argument('--activate', dest='activate', action='store_true')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_nfs(rule):
    '''
    Parse the nfs line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--server', dest='server', action='store')
    parser.add_argument('--dir', dest='dir', action='store')
    parser.add_argument('--opts', dest='opts', action='store')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_partition(rule):
    '''
    Parse the partition line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('mntpoint')
    parser.add_argument('--size', dest='size', action='store')
    parser.add_argument('--grow', dest='grow', action='store_true')
    parser.add_argument('--maxsize', dest='maxsize', action='store')
    parser.add_argument('--noformat', dest='noformat', action='store_true')
    parser.add_argument('--onpart', '--usepart', dest='onpart', action='store')
    parser.add_argument('--ondisk', '--ondrive', dest='ondisk', action='store')
    parser.add_argument('--asprimary', dest='asprimary', action='store_true')
    parser.add_argument('--fsprofile', dest='fsprofile', action='store')
    parser.add_argument('--fstype', dest='fstype', action='store')
    parser.add_argument('--fsoptions', dest='fsoptions', action='store')
    parser.add_argument('--label', dest='label', action='store')
    parser.add_argument('--recommended', dest='recommended',
                        action='store_true')
    parser.add_argument('--onbiosdisk', dest='onbiosdisk', action='store')
    parser.add_argument('--encrypted', dest='encrypted', action='store_true')
    parser.add_argument('--passphrase', dest='passphrase', action='store')
    parser.add_argument('--escrowcert', dest='escrowcert', action='store')
    parser.add_argument('--backupphrase', dest='backupphrase', action='store')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_raid(rule):
    '''
    Parse the raid line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)

    partitions = []
    newrules = []
    for count in range(0, len(rules)):
        if count == 0:
            newrules.append(rules[count])
            continue
        elif rules[count].startswith('--'):
            newrules.append(rules[count])
            continue
        else:
            partitions.append(rules[count])
    rules = newrules

    parser.add_argument('mntpoint')
    parser.add_argument('--level', dest='level', action='store')
    parser.add_argument('--device', dest='device', action='store')
    parser.add_argument('--spares', dest='spares', action='store')
    parser.add_argument('--fstype', dest='fstype', action='store')
    parser.add_argument('--fsoptions', dest='fsoptions', action='store')
    parser.add_argument('--label', dest='label', action='store')
    parser.add_argument('--noformat', dest='noformat', action='store_true')
    parser.add_argument('--useexisting', dest='useexisting',
                        action='store_true')
    parser.add_argument('--encrypted', dest='encrypted', action='store_true')
    parser.add_argument('--passphrase', dest='passphrase', action='store')
    parser.add_argument('--escrowcert', dest='escrowcert', action='store')
    parser.add_argument('--backuppassphrase', dest='backuppassphrase',
                        action='store')

    args = clean_args(vars(parser.parse_args(rules)))
    if partitions:
        args['partitions'] = partitions
    parser = None
    return args


def parse_reboot(rule):
    '''
    Parse the reboot line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--eject', dest='eject', action='store_true')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_repo(rule):
    '''
    Parse the repo line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--name', dest='name', action='store')
    parser.add_argument('--baseurl', dest='baseurl', action='store')
    parser.add_argument('--mirrorlist', dest='mirrorlist', action='store')
    parser.add_argument('--cost', dest='cost', action='store')
    parser.add_argument('--excludepkgs', dest='excludepkgs', action='store')
    parser.add_argument('--includepkgs', dest='includepkgs', action='store')
    parser.add_argument('--proxy', dest='proxy', action='store')
    parser.add_argument('--ignoregroups', dest='ignoregroups', action='store')
    parser.add_argument('--noverifyssl', dest='noverifyssl',
                        action='store_true')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_rescue(rule):
    '''
    Parse the rescue line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--nomount', dest='nomount', action='store_true')
    parser.add_argument('--romount', dest='romount', action='store_true')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_rootpw(rule):
    '''
    Parse the rootpw line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--iscrypted', dest='iscrypted', action='store_true')
    parser.add_argument('--plaintext', dest='plaintext', action='store_true')
    parser.add_argument('--lock', dest='lock', action='store_true')
    parser.add_argument('password')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_selinux(rule):
    '''
    Parse the selinux line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--disabled', dest='disabled', action='store_true')
    parser.add_argument('--enforcing', dest='enforcing', action='store_true')
    parser.add_argument('--permissive', dest='permissive', action='store_true')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_services(rule):
    '''
    Parse the services line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--disabled', dest='disabled', action='store')
    parser.add_argument('--enabled', dest='enabled', action='store')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_sshpw(rule):
    '''
    Parse the sshpw line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--username', dest='username', action='store')
    parser.add_argument('--iscrypted', dest='iscrypted', action='store_true')
    parser.add_argument('--plaintext', dest='plaintext', action='store_true')
    parser.add_argument('--lock', dest='lock', action='store_true')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_timezone(rule):
    '''
    Parse the timezone line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--utc', dest='utc', action='store_true')
    parser.add_argument('--nontp', dest='nontp', action='store_true')
    parser.add_argument('--ntpservers', dest='ntpservers', action='store')
    parser.add_argument('--isUtc', dest='isutc', action='store_true')
    parser.add_argument('timezone')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_updates(rule):
    '''
    Parse the updates line
    '''
    rules = shlex.split(rule)
    rules.pop(0)
    if len(rules) > 0:
        return {'url': rules[0]}
    else:
        return True


def parse_upgrade(rule):
    '''
    Parse the upgrade line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--root-device', dest='root-device', action='store')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    if args:
        return args
    return True


def parse_url(rule):
    '''
    Parse the url line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--url', dest='url', action='store')
    parser.add_argument('--proxy', dest='proxy', action='store')
    parser.add_argument('--noverifyssl', dest='noverifyssl',
                        action='store_true')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_user(rule):
    '''
    Parse the user line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--name', dest='name', action='store')
    parser.add_argument('--gecos', dest='gecos', action='store')
    parser.add_argument('--groups', dest='groups', action='store')
    parser.add_argument('--homedir', dest='homedir', action='store')
    parser.add_argument('--lock', dest='lock', action='store_true')
    parser.add_argument('--password', dest='password', action='store')
    parser.add_argument('--iscrypted', dest='iscrypted', action='store_true')
    parser.add_argument('--plaintext', dest='plaintext', action='store_true')
    parser.add_argument('--shell', dest='shell', action='store')
    parser.add_argument('--uid', dest='uid', action='store')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_vnc(rule):
    '''
    Parse the vnc line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--host', dest='host', action='store')
    parser.add_argument('--port', dest='port', action='store')
    parser.add_argument('--password', dest='password', action='store')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_volgroup(rule):
    '''
    Parse the volgroup line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)

    partitions = []
    newrules = []
    for count in range(0, len(rules)):
        if count == 0:
            newrules.append(rules[count])
            continue
        elif rules[count].startswith('--'):
            newrules.append(rules[count])
            continue
        else:
            partitions.append(rules[count])
    rules = newrules

    parser.add_argument('name')
    parser.add_argument('--noformat', dest='noformat', action='store_true')
    parser.add_argument('--useexisting', dest='useexisting',
                        action='store_true')
    parser.add_argument('--pesize', dest='pesize', action='store')
    parser.add_argument('--reserved-space', dest='reserved-space',
                        action='store')
    parser.add_argument('--reserved-percent', dest='reserved-percent',
                        action='store')

    args = clean_args(vars(parser.parse_args(rules)))
    if partitions:
        args['partitions'] = partitions
    parser = None
    return args


def parse_xconfig(rule):
    '''
    Parse the xconfig line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--defaultdesktop', dest='defaultdesktop',
                        action='store')
    parser.add_argument('--startxonboot', dest='startxonboot',
                        action='store_true')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def parse_zfcp(rule):
    '''
    Parse the zfcp line
    '''
    parser = argparse.ArgumentParser()
    rules = shlex.split(rule)
    rules.pop(0)
    parser.add_argument('--devnum', dest='devnum', action='store')
    parser.add_argument('--fcplun', dest='fcplun', action='store')
    parser.add_argument('--wwpn', dest='wwpn', action='store')

    args = clean_args(vars(parser.parse_args(rules)))
    parser = None
    return args


def mksls(src, dst=None):
    '''
    Convert a kickstart file to an SLS file
    '''
    mode = 'command'
    sls = {}
    ks_opts = {}
    with salt.utils.files.fopen(src, 'r') as fh_:
        for line in fh_:
            if line.startswith('#'):
                continue

            if mode == 'command':
                if line.startswith('auth ') or line.startswith('authconfig '):
                    ks_opts['auth'] = parse_auth(line)
                elif line.startswith('autopart'):
                    ks_opts['autopath'] = parse_autopart(line)
                elif line.startswith('autostep'):
                    ks_opts['autostep'] = parse_autostep(line)
                elif line.startswith('bootloader'):
                    ks_opts['bootloader'] = parse_bootloader(line)
                elif line.startswith('btrfs'):
                    ks_opts['btrfs'] = parse_btrfs(line)
                elif line.startswith('cdrom'):
                    ks_opts['cdrom'] = True
                elif line.startswith('clearpart'):
                    ks_opts['clearpart'] = parse_clearpart(line)
                elif line.startswith('cmdline'):
                    ks_opts['cmdline'] = True
                elif line.startswith('device'):
                    ks_opts['device'] = parse_device(line)
                elif line.startswith('dmraid'):
                    ks_opts['dmraid'] = parse_dmraid(line)
                elif line.startswith('driverdisk'):
                    ks_opts['driverdisk'] = parse_driverdisk(line)
                elif line.startswith('firewall'):
                    ks_opts['firewall'] = parse_firewall(line)
                elif line.startswith('firstboot'):
                    ks_opts['firstboot'] = parse_firstboot(line)
                elif line.startswith('group'):
                    ks_opts['group'] = parse_group(line)
                elif line.startswith('graphical'):
                    ks_opts['graphical'] = True
                elif line.startswith('halt'):
                    ks_opts['halt'] = True
                elif line.startswith('harddrive'):
                    ks_opts['harddrive'] = True
                elif line.startswith('ignoredisk'):
                    ks_opts['ignoredisk'] = parse_ignoredisk(line)
                elif line.startswith('install'):
                    ks_opts['install'] = True
                elif line.startswith('iscsi'):
                    ks_opts['iscsi'] = parse_iscsi(line)
                elif line.startswith('iscsiname'):
                    ks_opts['iscsiname'] = parse_iscsiname(line)
                elif line.startswith('keyboard'):
                    ks_opts['keyboard'] = parse_keyboard(line)
                elif line.startswith('lang'):
                    ks_opts['lang'] = parse_lang(line)
                elif line.startswith('logvol'):
                    if 'logvol' not in ks_opts.keys():
                        ks_opts['logvol'] = []
                    ks_opts['logvol'].append(parse_logvol(line))
                elif line.startswith('logging'):
                    ks_opts['logging'] = parse_logging(line)
                elif line.startswith('mediacheck'):
                    ks_opts['mediacheck'] = True
                elif line.startswith('monitor'):
                    ks_opts['monitor'] = parse_monitor(line)
                elif line.startswith('multipath'):
                    ks_opts['multipath'] = parse_multipath(line)
                elif line.startswith('network'):
                    if 'network' not in ks_opts.keys():
                        ks_opts['network'] = []
                    ks_opts['network'].append(parse_network(line))
                elif line.startswith('nfs'):
                    ks_opts['nfs'] = True
                elif line.startswith('part ') or line.startswith('partition'):
                    if 'part' not in ks_opts.keys():
                        ks_opts['part'] = []
                    ks_opts['part'].append(parse_partition(line))
                elif line.startswith('poweroff'):
                    ks_opts['poweroff'] = True
                elif line.startswith('raid'):
                    if 'raid' not in ks_opts.keys():
                        ks_opts['raid'] = []
                    ks_opts['raid'].append(parse_raid(line))
                elif line.startswith('reboot'):
                    ks_opts['reboot'] = parse_reboot(line)
                elif line.startswith('repo'):
                    ks_opts['repo'] = parse_repo(line)
                elif line.startswith('rescue'):
                    ks_opts['rescue'] = parse_rescue(line)
                elif line.startswith('rootpw'):
                    ks_opts['rootpw'] = parse_rootpw(line)
                elif line.startswith('selinux'):
                    ks_opts['selinux'] = parse_selinux(line)
                elif line.startswith('services'):
                    ks_opts['services'] = parse_services(line)
                elif line.startswith('shutdown'):
                    ks_opts['shutdown'] = True
                elif line.startswith('sshpw'):
                    ks_opts['sshpw'] = parse_sshpw(line)
                elif line.startswith('skipx'):
                    ks_opts['skipx'] = True
                elif line.startswith('text'):
                    ks_opts['text'] = True
                elif line.startswith('timezone'):
                    ks_opts['timezone'] = parse_timezone(line)
                elif line.startswith('updates'):
                    ks_opts['updates'] = parse_updates(line)
                elif line.startswith('upgrade'):
                    ks_opts['upgrade'] = parse_upgrade(line)
                elif line.startswith('url'):
                    ks_opts['url'] = True
                elif line.startswith('user'):
                    ks_opts['user'] = parse_user(line)
                elif line.startswith('vnc'):
                    ks_opts['vnc'] = parse_vnc(line)
                elif line.startswith('volgroup'):
                    ks_opts['volgroup'] = parse_volgroup(line)
                elif line.startswith('xconfig'):
                    ks_opts['xconfig'] = parse_xconfig(line)
                elif line.startswith('zerombr'):
                    ks_opts['zerombr'] = True
                elif line.startswith('zfcp'):
                    ks_opts['zfcp'] = parse_zfcp(line)

            if line.startswith('%include'):
                rules = shlex.split(line)
                if not ks_opts['include']:
                    ks_opts['include'] = []
                ks_opts['include'].append(rules[1])

            if line.startswith('%ksappend'):
                rules = shlex.split(line)
                if not ks_opts['ksappend']:
                    ks_opts['ksappend'] = []
                ks_opts['ksappend'].append(rules[1])

            if line.startswith('%packages'):
                mode = 'packages'
                if 'packages' not in ks_opts.keys():
                    ks_opts['packages'] = {'packages': {}}

                parser = argparse.ArgumentParser()
                opts = shlex.split(line)
                opts.pop(0)
                parser.add_argument('--default', dest='default', action='store_true')
                parser.add_argument('--excludedocs', dest='excludedocs',
                                    action='store_true')
                parser.add_argument('--ignoremissing', dest='ignoremissing',
                                    action='store_true')
                parser.add_argument('--instLangs', dest='instLangs', action='store')
                parser.add_argument('--multilib', dest='multilib', action='store_true')
                parser.add_argument('--nodefaults', dest='nodefaults',
                                    action='store_true')
                parser.add_argument('--optional', dest='optional', action='store_true')
                parser.add_argument('--nobase', dest='nobase', action='store_true')
                args = clean_args(vars(parser.parse_args(opts)))
                ks_opts['packages']['options'] = args

                continue

            if line.startswith('%pre'):
                mode = 'pre'

                parser = argparse.ArgumentParser()
                opts = shlex.split(line)
                opts.pop(0)
                parser.add_argument('--interpreter', dest='interpreter',
                                    action='store')
                parser.add_argument('--erroronfail', dest='erroronfail',
                                    action='store_true')
                parser.add_argument('--log', dest='log', action='store')
                args = clean_args(vars(parser.parse_args(opts)))
                ks_opts['pre'] = {'options': args, 'script': ''}

                continue

            if line.startswith('%post'):
                mode = 'post'

                parser = argparse.ArgumentParser()
                opts = shlex.split(line)
                opts.pop(0)
                parser.add_argument('--nochroot', dest='nochroot', action='store_true')
                parser.add_argument('--interpreter', dest='interpreter',
                                    action='store')
                parser.add_argument('--erroronfail', dest='erroronfail',
                                    action='store_true')
                parser.add_argument('--log', dest='log', action='store')
                args = clean_args(vars(parser.parse_args(opts)))
                ks_opts['post'] = {'options': args, 'script': ''}

                continue

            if line.startswith('%end'):
                mode = None

            if mode == 'packages':
                if line.startswith('-'):
                    package = line.replace('-', '', 1).strip()
                    ks_opts['packages']['packages'][package] = False
                else:
                    ks_opts['packages']['packages'][line.strip()] = True

            if mode == 'pre':
                ks_opts['pre']['script'] += line

            if mode == 'post':
                ks_opts['post']['script'] += line

    # Set language
    sls[ks_opts['lang']['lang']] = {'locale': ['system']}

    # Set keyboard
    sls[ks_opts['keyboard']['xlayouts']] = {'keyboard': ['system']}

    # Set timezone
    sls[ks_opts['timezone']['timezone']] = {'timezone': ['system']}
    if 'utc' in ks_opts['timezone'].keys():
        sls[ks_opts['timezone']['timezone']]['timezone'].append('utc')

    # Set network
    if 'network' in ks_opts.keys():
        for interface in ks_opts['network']:
            device = interface.get('device', None)
            if device is not None:
                del interface['device']
                sls[device] = {'proto': interface['bootproto']}
                del interface['bootproto']

                if 'onboot' in interface.keys():
                    if 'no' in interface['onboot']:
                        sls[device]['enabled'] = False
                    else:
                        sls[device]['enabled'] = True
                    del interface['onboot']

                if 'noipv4' in interface.keys():
                    sls[device]['ipv4'] = {'enabled': False}
                    del interface['noipv4']
                if 'noipv6' in interface.keys():
                    sls[device]['ipv6'] = {'enabled': False}
                    del interface['noipv6']

                for option in interface:
                    if type(interface[option]) is bool:
                        sls[device][option] = {'enabled': [interface[option]]}
                    else:
                        sls[device][option] = interface[option]
            if 'hostname' in interface:
                sls['system'] = {
                    'network.system': {
                        'enabled': True,
                        'hostname': interface['hostname'],
                        'apply_hostname': True,
                    }
                }

    # Set selinux
    if 'selinux' in ks_opts.keys():
        for mode in ks_opts['selinux']:
            sls[mode] = {'selinux': ['mode']}

    # Get package data together
    if 'nobase' not in ks_opts['packages']['options']:
        sls['base'] = {'pkg_group': ['installed']}

    packages = ks_opts['packages']['packages']
    for package in packages:
        if not packages[package]:
            continue
        if package and packages[package] is True:
            if package.startswith('@'):
                pkg_group = package.replace('@', '', 1)
                sls[pkg_group] = {'pkg_group': ['installed']}
            else:
                sls[package] = {'pkg': ['installed']}
        elif packages[package] is False:
            sls[package] = {'pkg': ['absent']}

    if dst:
        with salt.utils.files.fopen(dst, 'w') as fp_:
            salt.utils.yaml.safe_dump(sls, fp_, default_flow_style=False)
    else:
        return salt.utils.yaml.safe_dump(sls, default_flow_style=False)
