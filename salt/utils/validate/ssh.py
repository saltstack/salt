# -*- coding: utf-8 -*-
'''
Library for checking SSH options. This library primarily exists for purposes of
sanitizing options passed into SSH, than for checking to see whether those
options actually work.
'''

# Import python libs
import logging

# Import salt libs
import salt.utils.validate.net as suvn
import salt.utils.validate.user as suvu

log = logging.getLogger(__name__)


def is_clean(options):
    '''
    Returns True if the string of options passed in does not contain any
    injections
    '''
    opts = options.split()
    mode = None
    for opt in opts:
        if not mode:
            if opt.startswith('-'):
                # Is an option or group of options, the next string may be an
                # argument for this option
                for arg in opt.replace('-', ''):
                    if not allowed_opt(arg):
                        return False
                    if uses_path(opt):
                        mode = 'path'
                        continue
                    elif uses_bind(opt):
                        mode = 'bind'
                        continue
                    elif opt == 'I':
                        mode = 'pkcs11'
                        continue
                    elif opt == 'e':
                        mode = 'escape'
                        continue
                    elif opt == 'l':
                        mode = 'login'
                        continue
                    elif opt == 't':
                        mode = 'tun'
                        continue
                    elif opt == 'o':
                        mode = 'option'
                        continue
                    elif opt == 'O':
                        mode = 'control'
                        continue
        if mode == 'path':
            # TODO: Need to put a path checker in here
            mode = None
        elif mode == 'bind':
            if not clean_bind(opt):
                return False
            mode = None
        elif mode == 'pkcs11':
            # TODO: Need code to validate PKCS#11 lib, check ssh(1)
            pass
        elif mode == 'escape':
            # Just in case the escape character is in quotes
            if len(opt) == 3:
                if opt.startswith("'") and opt.endswith("'"):
                    opt = opt.replace("'", '')
                if opt.startswith('"') and opt.endswith('"'):
                    opt = opt.replace('"', '')
            if len(opt) > 1:
                return False
            mode = None
        elif mode == 'login':
            if not suvu.valid_username(opt):
                return False
            mode = None
        elif mode == 'tun':
            # TODO: What does a tun device look like?
            pass
        elif mode == 'control':
            if not valid_control(opt):
                return False
            mode = None
        elif mode == 'cypher':
            if not allowed_cypher(opt) and not allowed_cyphers(opt):
                return False
            mode = None
        elif mode == 'option':
            # TODO: Lots of gaps to fill in here
            if allowed_config(opt):
                # This is an allowed configuration option, let's check to see
                # if something specific should follow it
                if opt not in ('Cypher', 'Ciphers'):
                    mode = 'cypher'
                    continue


def allowed_opt(opt):
    '''
    Returns True if an option is valid to the `ssh` command
    '''
    if opt in '1246ACDEFIKLMNOQRSTVWXYabcefgiklmnopqstvwxy':
        return True
    return False


def allowed_config(conf):
    '''
    Returns True if a config option is valid to OpenSSH
    '''
    if conf in (
        # 'yes' or 'no'
        'BatchMode',
        'CheckHostIP',
        'ChallengeResponseAuthentication',
        'ClearAllForwardings',
        'Compression',
        'ControlPersist',
        'EnableSSHKeysign',
        'ExitOnForwardFailure',
        'ForwardAgent',
        'ForwardX11',
        'ForwardX11Trusted',
        'GatewayPorts',
        'GSSAPIAuthentication',
        'GSSAPIDelegateCredentials',
        'HashKnownHosts',
        'HostbasedAuthentication',
        'IdentitiesOnly',
        'KbdInteractiveAuthentication',
        'NoHostAuthenticationForLocalhost',
        'PasswordAuthentication',
        'PermitLocalCommand',
        'PubkeyAuthentication',
        'RhostsRSAAuthentication',
        'RSAAuthentication',
        'TCPKeepAlive',
        'UsePrivilegedPort',
        'VisualHostKey',

        # 'yes', 'no' or other
        'ControlMaster',  # 'yes', 'no', 'ask', 'auto', 'autoask'
        'RequestTTY',  # 'no', 'yes', 'auto', 'forward'
        'StrictHostKeyChecking',  # 'yes', 'no', 'ask'
        'Tunnel',  # 'yes', 'point-to-point', 'ethernet', 'no'
        'VerifyHostKeyDNS',  # 'yes', 'no', 'ask'

        # int
        'CompressionLevel',
        'ConnectionAttempts',
        'ConnectTimeout',
        'NumberOfPasswordPrompts',
        'Port',
        'ServerAliveCountMax',
        'ServerAliveInterval',

        # One or more filenames
        'ControlPath',  # pathname
        'GlobalKnownHostsFile',  # one or more filenames
        'IdentityFile',  # filename
        'UserKnownHostsFile',  # one or more filenames
        'XAuthLocation',  # filename

        # Some amount of pre-defined text
        'AddressFamily',  # 'any', 'inet', 'inet6'
        'IPQoS',  # 'af11', 'af12', 'af13', 'af21', 'af22', 'af23', 'af31',
                  # 'af32', 'af33', 'af41', 'af42', 'af43', 'cs0', 'cs1',
                  # 'cs2', 'cs3', 'cs4', 'cs5', 'cs6', 'cs7', 'ef', 'lowdelay',
                  # 'throughput', 'reliability'
        'KbdInteractiveDevices',  # 'bsdauth', 'pam', and/or 'skey'
        'LogLevel',  # 'QUIET', 'FATAL', 'ERROR', 'INFO', 'VERBOSE', 'DEBUG',
                     # 'DEBUG1', 'DEBUG2', 'DEBUG3'
        'Protocol',  # '2', '1'

        # Host, port, IP or device
        'BindAddress',  # IP addrs
        'DynamicForward',  # bind_address:port
        'Host',  # Host names, IP addrs
        'HostName',  # hostname, IP addr, or '%h'
        'LocalForward',  # [bind_address:]port host :hostport
        'RemoteForward',  # [bind_address:]port host :hostport
        'TunnelDevice',  # local_tun[:remote_tun]

        # Crypto
        'Cipher',  # DONE
        'Ciphers',  # DONE
        'HostKeyAlgorithms',  # TODO: Find out what is valid here
        'KexAlgorithms',  # TODO: Find out what is valid here
        'MACs',  # TODO: Find out what is valid here
        'PKCS11Provider',  # TODO: Find out what is valid here
        'PreferredAuthentications',  # TODO: Find out what is valid here

        # Username
        'User',  # username

        'EscapeChar',  # single character + letter, or 'none' TODO, check this
        'ForwardX11Timeout',  # TIME FORMAT
        'HostKeyAlias',  # TODO: Find out what is valid here
        'IgnoreUnknown',  # TODO: Find out what is not invalid here
        'LocalCommand',  # TODO: Find out how to validate this
        'ProxyCommand',  # TODO: Find out what is valid here
        'RekeyLimit',  # '<x>[K|M|G]', optionally followed by int
        'SendEnv',  # TODO: Find out what is valid here
    ):
        return True
    return False


def allowed_cypher(spec):
    '''
    Returns True if the cypher spec is allowed (SSH 1)
    '''
    if spec in ('3des', 'blowfish', 'des'):
        return True
    return False


def allowed_cyphers(spec):
    '''
    Returns True if the cypher spec is allowed (SSH 2)
    '''
    if spec in (
        '3des-cbc',
        'aes128-cbc',
        'aes192-cbc',
        'aes256-cbc',
        'aes128-ctr',
        'aes192-ctr',
        'aes256-ctr',
        'aes128-gcm@openssh.com',
        'aes256-gcm@openssh.com',
        'arcfour128',
        'arcfour256',
        'arcfour',
        'blowfish-cbc',
        'cast128-cbc',
    ):
        return True
    return False


def uses_path(opt):
    '''
    Returns True if an option makes use of a file path
    '''
    if opt in 'EFiS':
        return True
    return False


def uses_bind(opt):
    '''
    Returns True if an option makes use of an Internet address
    '''
    if opt in 'bDLRW':
        return True
    return False


def clean_bind(addr):
    '''
    Splits a bind address on ':', and checks each part to make sure it is either
    a valid port (an int) or a valid IPv4 address. This is more for sanitization
    purposes than for validity checking.

    SSH options that will use this are -b, -D, -L, -R and -W
    '''
    comps = addr.split()
    for part in comps:
        try:
            int(part)
            if not suvn.ipv4_addr(part):
                return False
        except ValueError:
            return False
    return True


def valid_control(control):
    '''
    Checks to see if a multiplex control is valid
    '''
    if control in ('check', 'forward', 'cancel', 'exit', 'stop'):
        return True
    return False


# ssh  [-1246AaCfgKkMNnqsTtVvXxYy]  [-b  bind_address]  [-c  cipher_spec]
#      [-D[bind_address :]port] [-E log_file] [-e escape_char] [-F configfile]
#      [-I pkcs11] [-i  identity_file]
#      [-L[bind_address :]port  :host  :hostport]  [-l  login_name]
#      [-m  mac_spec]  [-O  ctl_cmd]  [-o  option]  [-p  port]
#      [-R[bind_address :]port :host :hostport] [-S ctl_path] [-W host :port]
#      [-w local_tun[:remote_tun] [user@]hostname [command]
# ssh -Q protocol_feature
