'''
Utility functions for saltcloud
'''

# Import python libs
import os
import pwd
import shutil
import socket
import tempfile
import time
import subprocess
import multiprocessing
import logging
import pipes
import types
import re
import warnings

# Get logging started
log = logging.getLogger(__name__)

# Import salt libs
import salt.crypt
import salt.client
import salt.config
import salt.utils
import salt.utils.event

# Import salt cloud libs
import saltcloud.config as config
from saltcloud.utils.nb_popen import NonBlockingPopen
from saltcloud.exceptions import (
    SaltCloudConfigError,
    SaltCloudException,
    SaltCloudSystemExit,
    SaltCloudExecutionTimeout,
    SaltCloudExecutionFailure
)

# Import third party libs
from jinja2 import Template
import yaml

NSTATES = {
    0: 'running',
    1: 'rebooting',
    2: 'terminated',
    3: 'pending',
}


def __render_script(path, vm_=None, opts=None, minion=''):
    '''
    Return the rendered script
    '''
    log.info('Rendering deploy script: {0}'.format(path))
    try:
        with salt.utils.fopen(path, 'r') as fp_:
            template = Template(fp_.read())
            return str(template.render(opts=opts, vm=vm_, minion=minion))
    except AttributeError:
        # Specified renderer was not found
        with salt.utils.fopen(path, 'r') as fp_:
            return fp_.read()


def os_script(os_, vm_=None, opts=None, minion=''):
    '''
    Return the script as a string for the specific os
    '''
    if os.path.isabs(os_):
        # The user provided an absolute path to the deploy script, let's use it
        return __render_script(os_, vm_, opts, minion)

    if os.path.isabs('{0}.sh'.format(os_)):
        # The user provided an absolute path to the deploy script, although no
        # extension was provided. Let's use it anyway.
        return __render_script('{0}.sh'.format(os_), vm_, opts, minion)

    for search_path in opts['deploy_scripts_search_path']:
        if os.path.isfile(os.path.join(search_path, os_)):
            return __render_script(
                os.path.join(search_path, os_), vm_, opts, minion
            )

        if os.path.isfile(os.path.join(search_path, '{0}.sh'.format(os_))):
            return __render_script(
                os.path.join(search_path, '{0}.sh'.format(os_)),
                vm_, opts, minion
            )
    # No deploy script was found, return an empty string
    return ''


def gen_keys(keysize=2048):
    '''
    Generate Salt minion keys and return them as PEM file strings
    '''
    # Mandate that keys are at least 2048 in size
    if keysize < 2048:
        keysize = 2048
    tdir = tempfile.mkdtemp()

    salt.crypt.gen_keys(tdir, 'minion', keysize)
    priv_path = os.path.join(tdir, 'minion.pem')
    pub_path = os.path.join(tdir, 'minion.pub')
    with salt.utils.fopen(priv_path) as fp_:
        priv = fp_.read()
    with salt.utils.fopen(pub_path) as fp_:
        pub = fp_.read()
    shutil.rmtree(tdir)
    return priv, pub


def accept_key(pki_dir, pub, id_):
    '''
    If the master config was available then we will have a pki_dir key in
    the opts directory, this method places the pub key in the accepted
    keys dir and removes it from the unaccepted keys dir if that is the case.
    '''
    for key_dir in ('minions', 'minions_pre', 'minions_rejected'):
        key_path = os.path.join(pki_dir, key_dir)
        if not os.path.exists(key_path):
            os.makedirs(key_path)

    key = os.path.join(pki_dir, 'minions', id_)
    with salt.utils.fopen(key, 'w+') as fp_:
        fp_.write(pub)

    oldkey = os.path.join(pki_dir, 'minions_pre', id_)
    if os.path.isfile(oldkey):
        with salt.utils.fopen(oldkey) as fp_:
            if fp_.read() == pub:
                os.remove(oldkey)


def remove_key(pki_dir, id_):
    '''
    This method removes a specified key from the accepted keys dir
    '''
    key = os.path.join(pki_dir, 'minions', id_)
    if os.path.isfile(key):
        os.remove(key)
        log.debug('Deleted {0!r}'.format(key))


def rename_key(pki_dir, id_, new_id):
    '''
    Rename a key, when an instance has also been renamed
    '''
    oldkey = os.path.join(pki_dir, 'minions', id_)
    newkey = os.path.join(pki_dir, 'minions', new_id)
    if os.path.isfile(oldkey):
        os.rename(oldkey, newkey)


def get_option(option, opts, vm_):
    '''
    Convenience function to return the dominant option to be used. Always
    default to options set in the VM structure, but if the option is not
    present there look for it in the main configuration file
    '''
    # Make the next warning visible at least once.
    warnings.filterwarnings(
        'once', category=DeprecationWarning, module='saltcloud'
    )
    warnings.warn(
        '`saltcloud.utils.get_option() was deprecated in favour of '
        '`saltcloud.config.get_config_value()`. Please stop using it '
        'since it will be removed in version 0.8.8.',
        DeprecationWarning,
        stacklevel=2
    )

    if option in vm_:
        return vm_[option]
    if option in opts:
        return opts[option]


def minion_config(opts, vm_):
    '''
    Return a minion's configuration for the provided options and VM
    '''

    # Let's get a copy of the salt minion default options
    minion = salt.config.DEFAULT_MINION_OPTS.copy()
    # Some default options are Null, let's set a reasonable default
    minion.update(
        log_level='info',
        log_level_logfile='info'
    )

    # Now, let's update it to our needs
    minion['id'] = vm_['name']
    master_finger = config.get_config_value('master_finger', vm_, opts)
    if master_finger is not None:
        minion['master_finger'] = master_finger
    minion.update(
        # Get ANY defined minion settings, merging data, in the following order
        # 1. VM config
        # 2. Profile config
        # 3. Global configuration
        config.get_config_value(
            'minion', vm_, opts, default={}, search_global=True
        )
    )

    make_master = config.get_config_value('make_master', vm_, opts)
    if 'master' not in minion and make_master is not True:
        raise SaltCloudConfigError(
            'A master setting was not defined in the minion\'s configuration.'
        )

    # Get ANY defined grains settings, merging data, in the following order
    # 1. VM config
    # 2. Profile config
    # 3. Global configuration
    minion.setdefault('grains', {}).update(
        config.get_config_value(
            'grains', vm_, opts, default={}, search_global=True
        )
    )
    return minion


def minion_conf_string(opts, vm_):
    '''
    Return a string to be passed into the deployment script for the minion
    configuration file
    '''
    return salt_config_to_yaml(minion_config(opts, vm_))


def master_config(opts, vm_):
    '''
    Return a master's configuration for the provided options and VM
    '''
    # Let's get a copy of the salt master default options
    master = salt.config.DEFAULT_MASTER_OPTS.copy()
    # Some default options are Null, let's set a reasonable default
    master.update(
        log_level='info',
        log_level_logfile='info'
    )

    # Get ANY defined master setting, merging data, in the following order
    # 1. VM config
    # 2. Profile config
    # 3. Global configuration
    master.update(
        config.get_config_value(
            'master', vm_, opts, default={}, search_global=True
        )
    )
    return master


def master_conf_string(opts, vm_):
    '''
    Return a string to be passed into the deployment script for the master
    configuration file
    '''
    return salt_config_to_yaml(master_config(opts, vm_))


def salt_config_to_yaml(configuration):
    '''
    Return a salt configuration dictionary, master or minion, as a yaml dump
    '''
    return yaml.safe_dump(configuration, default_flow_style=False)


def wait_for_ssh(host, port=22, timeout=900):
    '''
    Wait until an ssh connection can be made on a specified host
    '''
    start = time.time()
    log.debug(
        'Attempting SSH connection to host {0} on port {1}'.format(
            host, port
        )
    )
    trycount = 0
    while True:
        trycount += 1
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, port))
            # Stop any remaining reads/writes on the socket
            sock.shutdown(socket.SHUT_RDWR)
            # Close it!
            sock.close()
            return True
        except socket.error as exc:
            log.debug('Caught exception in wait_for_ssh: {0}'.format(exc))
            time.sleep(1)
            if time.time() - start > timeout:
                log.error('SSH connection timed out: {0}'.format(timeout))
                return False

            log.debug(
                'Retrying SSH connection to host {0} on port {1} '
                '(try {2})'.format(
                    host, port, trycount
                )
            )


def wait_for_passwd(host, port=22, ssh_timeout=15, username='root',
                    password=None, key_filename=None, maxtries=15,
                    trysleep=1, display_ssh_output=True):
    '''
    Wait until ssh connection can be accessed via password or ssh key
    '''
    trycount = 0
    while trycount < maxtries:
        connectfail = False
        try:
            kwargs = {'hostname': host,
                      'port': port,
                      'username': username,
                      'timeout': ssh_timeout,
                      'display_ssh_output': display_ssh_output}
            if key_filename:
                if not os.path.isfile(key_filename):
                    raise SaltCloudConfigError(
                        'The defined key_filename {0!r} does not exist'.format(
                            key_filename
                        )
                    )
                kwargs['key_filename'] = key_filename
                log.debug('Using {0} as the key_filename'.format(key_filename))
            elif password:
                kwargs['password'] = password
                log.debug('Using {0} as the password'.format(password))

            trycount += 1
            log.debug(
                'Attempting to authenticate as {0} (try {1} of {2})'.format(
                    username, trycount, maxtries
                )
            )

            status = root_cmd('date', tty=False, sudo=False, **kwargs)
            if status != 0:
                connectfail = True
                if trycount < maxtries:
                    time.sleep(trysleep)
                    continue

                log.error(
                    'Authentication failed: status code {0}'.format(
                        status
                    )
                )
                return False
            if connectfail is False:
                return True
            return False
        except Exception:
            if trycount >= maxtries:
                return False
            time.sleep(trysleep)


def deploy_script(host, port=22, timeout=900, username='root',
                  password=None, key_filename=None, script=None,
                  deploy_command='/tmp/deploy.sh', sudo=False, tty=None,
                  name=None, pub_key=None, sock_dir=None, provider=None,
                  conf_file=None, start_action=None, make_master=False,
                  master_pub=None, master_pem=None, master_conf=None,
                  minion_pub=None, minion_pem=None, minion_conf=None,
                  keep_tmp=False, script_args=None, script_env=None,
                  ssh_timeout=15, make_syndic=False, make_minion=True,
                  display_ssh_output=True, preseed_minion_keys=None):
    '''
    Copy a deploy script to a remote server, execute it, and remove it
    '''
    if key_filename is not None and not os.path.isfile(key_filename):
        raise SaltCloudConfigError(
            'The defined key_filename {0!r} does not exist'.format(
                key_filename
            )
        )
    starttime = time.mktime(time.localtime())
    log.debug('Deploying {0} at {1}'.format(host, starttime))
    if wait_for_ssh(host=host, port=port, timeout=timeout):
        log.debug('SSH port {0} on {1} is available'.format(port, host))
        newtimeout = timeout - (time.mktime(time.localtime()) - starttime)
        if wait_for_passwd(host, port=port, username=username,
                           password=password, key_filename=key_filename,
                           ssh_timeout=ssh_timeout,
                           display_ssh_output=display_ssh_output):
            log.debug(
                'Logging into {0}:{1} as {2}'.format(
                    host, port, username
                )
            )
            newtimeout = timeout - (time.mktime(time.localtime()) - starttime)
            kwargs = {'hostname': host,
                      'port': port,
                      'username': username,
                      'timeout': ssh_timeout,
                      'display_ssh_output': display_ssh_output}
            if key_filename:
                log.debug('Using {0} as the key_filename'.format(key_filename))
                kwargs['key_filename'] = key_filename
            elif password:
                log.debug('Using {0} as the password'.format(password))
                kwargs['password'] = password

            #FIXME: this try-except doesn't make sense! Something is missing...
            try:
                log.debug('SSH connection to {0} successful'.format(host))
            except Exception as exc:
                log.error(
                    'There was an error in deploy_script: {0}'.format(exc)
                )

            if provider == 'ibmsce':
                subsys_command = (
                    'sed -i "s/#Subsystem/Subsystem/" '
                    '/etc/ssh/sshd_config'
                )
                root_cmd(subsys_command, tty, sudo, **kwargs)
                root_cmd('service sshd restart', tty, sudo, **kwargs)

            # Minion configuration
            if minion_pem:
                scp_file('/tmp/minion.pem', minion_pem, kwargs)
                root_cmd('chmod 600 /tmp/minion.pem', tty, sudo, **kwargs)
            if minion_pub:
                scp_file('/tmp/minion.pub', minion_pub, kwargs)
            if minion_conf:
                scp_file('/tmp/minion', minion_conf, kwargs)

            # Master configuration
            if master_pem:
                scp_file('/tmp/master.pem', master_pem, kwargs)
                root_cmd('chmod 600 /tmp/master.pem', tty, sudo, **kwargs)
            if master_pub:
                scp_file('/tmp/master.pub', master_pub, kwargs)
            if master_conf:
                scp_file('/tmp/master', master_conf, kwargs)

            # XXX: We need to make these paths configurable
            preseed_minion_keys_tempdir = '/tmp/preseed-minion-keys'
            if preseed_minion_keys is not None:
                # Create remote temp dir
                root_cmd(
                    'mkdir "{0}"'.format(preseed_minion_keys_tempdir),
                    tty, sudo, **kwargs
                )
                root_cmd(
                    'chmod 700 "{0}"'.format(preseed_minion_keys_tempdir),
                    tty, sudo, **kwargs
                )
                if kwargs['username'] != 'root':
                    root_cmd(
                        'chown {0} "{1}"'.format(
                            kwargs['username'], preseed_minion_keys_tempdir
                        ),
                        tty, sudo, **kwargs
                    )

                # Copy pre-seed minion keys
                for minion_id, minion_key in preseed_minion_keys.iteritems():
                    rpath = os.path.join(
                        preseed_minion_keys_tempdir, minion_id
                    )
                    scp_file(rpath, minion_key, kwargs)

                if kwargs['username'] != 'root':
                    root_cmd(
                        'chown -R root "{0}"'.format(
                            preseed_minion_keys_tempdir
                        ),
                        tty, sudo, **kwargs
                    )

            # The actual deploy script
            if script:
                scp_file('/tmp/deploy.sh', script, kwargs)
                root_cmd('chmod +x /tmp/deploy.sh', tty, sudo, **kwargs)

            newtimeout = timeout - (time.mktime(time.localtime()) - starttime)
            queue = None
            process = None
            # Consider this code experimental. It causes Salt Cloud to wait
            # for the minion to check in, and then fire a startup event.
            if start_action:
                queue = multiprocessing.Queue()
                process = multiprocessing.Process(
                    target=check_auth, kwargs=dict(
                        name=name, pub_key=pub_key, sock_dir=sock_dir,
                        timeout=newtimeout, queue=queue
                    )
                )
                log.debug('Starting new process to wait for salt-minion')
                process.start()

            # Run the deploy script
            if script:
                if 'bootstrap-salt' in script:
                    deploy_command += ' -c /tmp/'
                    if make_syndic is True:
                        deploy_command += ' -S'
                    if make_master is True:
                        deploy_command += ' -M'
                    if make_minion is False:
                        deploy_command += ' -N'
                    if preseed_minion_keys is not None:
                        deploy_command += ' -k {0}'.format(
                            preseed_minion_keys_tempdir
                        )
                if script_args:
                    deploy_command += ' {0}'.format(script_args)

                if script_env:
                    if not isinstance(script_env, dict):
                        raise SaltCloudSystemExit(
                            'The \'script_env\' configuration setting NEEDS '
                            'to be a dictionary not a {0}'.format(
                                type(script_env)
                            )
                        )
                    environ_script_contents = ['#!/bin/sh']
                    for key, value in script_env.iteritems():
                        environ_script_contents.append(
                            'setenv {0} \'{1}\' >/dev/null 2>&1 || '
                            'export {0}=\'{1}\''.format(key, value)
                        )
                    environ_script_contents.append(deploy_command)

                    # Upload our environ setter wrapper
                    scp_file(
                        '/tmp/environ-deploy-wrapper.sh',
                        '\n'.join(environ_script_contents),
                        kwargs
                    )
                    root_cmd(
                        'chmod +x /tmp/environ-deploy-wrapper.sh',
                        tty, sudo, **kwargs
                    )
                    # The deploy command is now our wrapper
                    deploy_command = '/tmp/environ-deploy-wrapper.sh'

                if root_cmd(deploy_command, tty, sudo, **kwargs) != 0:
                    raise SaltCloudSystemExit(
                        'Executing the command {0!r} failed'.format(
                            deploy_command
                        )
                    )
                log.debug('Executed command {0!r}'.format(deploy_command))

                # Remove the deploy script
                if not keep_tmp:
                    root_cmd('rm /tmp/deploy.sh', tty, sudo, **kwargs)
                    log.debug('Removed /tmp/deploy.sh')
                    if script_env:
                        root_cmd(
                            'rm /tmp/environ-deploy-wrapper.sh',
                            tty, sudo, **kwargs
                        )
                        log.debug('Removed /tmp/environ-deploy-wrapper.sh')

            if keep_tmp:
                log.debug('Not removing deployment files from /tmp/')

            # Remove minion configuration
            if not keep_tmp:
                if minion_pub:
                    root_cmd('rm /tmp/minion.pub', tty, sudo, **kwargs)
                    log.debug('Removed /tmp/minion.pub')
                if minion_pem:
                    root_cmd('rm /tmp/minion.pem', tty, sudo, **kwargs)
                    log.debug('Removed /tmp/minion.pem')
                if minion_conf:
                    root_cmd('rm /tmp/minion', tty, sudo, **kwargs)
                    log.debug('Removed /tmp/minion')

                # Remove master configuration
                if master_pub:
                    root_cmd('rm /tmp/master.pub', tty, sudo, **kwargs)
                    log.debug('Removed /tmp/master.pub')
                if master_pem:
                    root_cmd('rm /tmp/master.pem', tty, sudo, **kwargs)
                    log.debug('Removed /tmp/master.pem')
                if master_conf:
                    root_cmd('rm /tmp/master', tty, sudo, **kwargs)
                    log.debug('Removed /tmp/master')

                # Remove pre-seed keys directory
                if preseed_minion_keys is not None:
                    root_cmd(
                        'rm -rf {0}'.format(
                            preseed_minion_keys_tempdir
                        ), tty, sudo, **kwargs
                    )
                    log.debug(
                        'Removed {0}'.format(preseed_minion_keys_tempdir)
                    )

            if start_action:
                queuereturn = queue.get()
                process.join()
                if queuereturn and start_action:
                    #client = salt.client.LocalClient(conf_file)
                    #output = client.cmd_iter(
                    #    host, 'state.highstate', timeout=timeout
                    #)
                    #for line in output:
                    #    print(line)
                    log.info(
                        'Executing {0} on the salt-minion'.format(
                            start_action
                        )
                    )
                    root_cmd(
                        'salt-call {0}'.format(start_action),
                        tty, sudo, **kwargs
                    )
                    log.info(
                        'Finished executing {0} on the salt-minion'.format(
                            start_action
                        )
                    )
            #Fire deploy action
            event = salt.utils.event.SaltEvent(
                'master',
                sock_dir
            )
            event.fire_event(
                '{0} has been created at {1}'.format(name, host), 'salt-cloud'
            )
            return True
    return False


def scp_file(dest_path, contents, kwargs):
    '''
    Use scp to copy a file to a server
    '''
    tmpfh, tmppath = tempfile.mkstemp()
    with salt.utils.fopen(tmppath, 'w') as tmpfile:
        tmpfile.write(contents)

    log.debug('Uploading {0} to {1}'.format(dest_path, kwargs['hostname']))

    ssh_args = [
        # Don't add new hosts to the host key database
        '-oStrictHostKeyChecking=no',
        # Set hosts key database path to /dev/null, ie, non-existing
        '-oUserKnownHostsFile=/dev/null',
        # Don't re-use the SSH connection. Less failures.
        '-oControlPath=none'
    ]
    if 'key_filename' in kwargs:
        # There should never be both a password and an ssh key passed in, so
        ssh_args.extend([
            # tell SSH to skip password authentication
            '-oPasswordAuthentication=no',
            '-oChallengeResponseAuthentication=no',
            # Make sure public key authentication is enabled
            '-oPubkeyAuthentication=yes',
            # No Keyboard interaction!
            '-oKbdInteractiveAuthentication=no',
            # Also, specify the location of the key file
            '-i {0}'.format(kwargs['key_filename'])
        ])

    cmd = 'scp {0} {1} {2[username]}@{2[hostname]}:{3}'.format(
        ' '.join(ssh_args), tmppath, kwargs, dest_path
    )
    log.debug('SCP command: {0!r}'.format(cmd))

    if 'password' in kwargs:
        cmd = 'sshpass -p {0} {1}'.format(kwargs['password'], cmd)

    try:
        proc = NonBlockingPopen(
            cmd,
            shell=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stream_stds=kwargs.get('display_ssh_output', True),
        )
        log.debug(
            'Uploading file(PID {0}): {1!r}'.format(
                proc.pid, dest_path
            )
        )
        while proc.poll() is None:
            time.sleep(0.25)

        proc.communicate()
        return proc.returncode
    except Exception as err:
        log.error(
            'Failed to upload file {0!r}: {1}\n'.format(
                dest_path, err
            ),
            exc_info=True
        )
    # Signal an error
    return 1


def root_cmd(command, tty, sudo, **kwargs):
    '''
    Wrapper for commands to be run as root
    '''
    if sudo:
        command = 'sudo {0}'.format(command)
        log.debug('Using sudo to run command {0}'.format(command))

    ssh_args = []

    if tty:
        # Use double `-t` on the `ssh` command, it's necessary when `sudo` has
        # `requiretty` enforced.
        ssh_args.extend(['-t', '-t'])

    ssh_args.extend([
        # Don't add new hosts to the host key database
        '-oStrictHostKeyChecking=no',
        # Set hosts key database path to /dev/null, ie, non-existing
        '-oUserKnownHostsFile=/dev/null',
        # Don't re-use the SSH connection. Less failures.
        '-oControlPath=none'
    ])

    if 'key_filename' in kwargs:
        # There should never be both a password and an ssh key passed in, so
        ssh_args.extend([
            # tell SSH to skip password authentication
            '-oPasswordAuthentication=no',
            '-oChallengeResponseAuthentication=no',
            # Make sure public key authentication is enabled
            '-oPubkeyAuthentication=yes',
            # No Keyboard interaction!
            '-oKbdInteractiveAuthentication=no',
            # Also, specify the location of the key file
            '-i {0}'.format(kwargs['key_filename'])
        ])

    cmd = 'ssh {0} {1[username]}@{1[hostname]} {2}'.format(
        ' '.join(ssh_args), kwargs, pipes.quote(command)
    )
    log.debug('SSH command: {0!r}'.format(cmd))

    if 'password' in kwargs:
        cmd = 'sshpass -p {0} {1}'.format(kwargs['password'], cmd)

    try:
        proc = NonBlockingPopen(
            cmd,
            shell=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stream_stds=kwargs.get('display_ssh_output', True),
        )
        log.debug(
            'Executing command(PID {0}): {1!r}'.format(
                proc.pid, command
            )
        )
        while proc.poll() is None:
            time.sleep(0.25)

        proc.communicate()
        return proc.returncode
    except Exception as err:
        log.error(
            'Failed to execute command {0!r}: {1}\n'.format(
                command, err
            ),
            exc_info=True
        )
    # Signal an error
    return 1


def check_auth(name, pub_key=None, sock_dir=None, queue=None, timeout=300):
    '''
    This function is called from a multiprocess instance, to wait for a minion
    to become available to receive salt commands
    '''
    event = salt.utils.event.SaltEvent('master', sock_dir)
    starttime = time.mktime(time.localtime())
    newtimeout = timeout
    log.debug(
        'In check_auth, waiting for {0} to become available'.format(
            name
        )
    )
    while newtimeout > 0:
        newtimeout = timeout - (time.mktime(time.localtime()) - starttime)
        ret = event.get_event(full=True)
        if ret is None:
            continue
        if ret['tag'] == 'minion_start' and ret['data']['id'] == name:
            queue.put(name)
            newtimeout = 0
            log.debug('Minion {0} is ready to receive commands'.format(name))


def ip_to_int(ip):
    '''
    Converts an IP address to an integer
    '''
    ret = 0
    for octet in ip.split('.'):
        ret = ret * 256 + int(octet)
    return ret


def is_public_ip(ip):
    '''
    Determines whether an IP address falls within one of the private IP ranges
    '''
    addr = ip_to_int(ip)
    if addr > 167772160 and addr < 184549375:
        # 10.0.0.0/24
        return False
    elif addr > 3232235520 and addr < 3232301055:
        # 192.168.0.0/16
        return False
    elif addr > 2886729728 and addr < 2887778303:
        # 172.16.0.0/12
        return False
    return True


def check_name(name, safe_chars):
    '''
    Check whether the specified name contains invalid characters
    '''
    regexp = re.compile('[^{0}]'.format(safe_chars))
    if regexp.search(name):
        raise SaltCloudException(
            '{0} contains characters not supported by this cloud provider. '
            'Valid characters are: {1}'.format(
                name, safe_chars
            )
        )


def namespaced_function(function, global_dict, defaults=None):
    '''
    Redefine(clone) a function under a different globals() namespace scope
    '''
    if defaults is None:
        defaults = function.__defaults__

    new_namespaced_function = types.FunctionType(
        function.__code__,
        global_dict,
        name=function.__name__,
        argdefs=defaults
    )
    new_namespaced_function.__dict__.update(function.__dict__)
    return new_namespaced_function


def remove_sshkey(host, known_hosts=None):
    '''
    Remove a host from the known_hosts file
    '''
    if known_hosts is None:
        if 'HOME' in os.environ:
            known_hosts = '{0}/.ssh/known_hosts'.format(os.environ['HOME'])
        else:
            try:
                known_hosts = '{0}/.ssh/known_hosts'.format(
                    pwd.getpwuid(os.getuid()).pwd_dir
                )
            except:
                pass

    if known_hosts is not None:
        log.debug(
            'Removing ssh key for {0} from known hosts file {1}'.format(
                host, known_hosts
            )
        )
    else:
        log.debug(
            'Removing ssh key for {0} from known hosts file'.format(host)
        )

    cmd = 'ssh-keygen -R {0}'.format(host)
    subprocess.call(cmd, shell=True)


def wait_for_ip(update_callback,
                update_args=None,
                update_kwargs=None,
                timeout=5 * 60,
                interval=5,
                max_failures=10):
    '''
    Helper function that waits for an IP address for a specific maximum amount
    of time.

    :param update_callback: callback function which queries the cloud provider
                            for the VM ip address. It must return None if the
                            required data, IP included, is not available yet.
    :param update_args: Arguments to pass to update_callback
    :param update_kwargs: Keyword arguments to pass to update_callback
    :param timeout: The maximum amount of time(in seconds) to wait for the IP
                    address.
    :param interval: The looping interval, ie, the amount of time to sleep
                     before the next iteration.
    :param max_failures: If update_callback returns ``False`` it's considered
                         query failure. This value is the amount of failures
                         accepted before giving up.
    :returns: The update_callback returned data
    :raises: SaltCloudExecutionTimeout

    '''
    if update_args is None:
        update_args = ()
    if update_kwargs is None:
        update_kwargs = {}

    duration = timeout
    while True:
        log.debug(
            'Waiting for VM IP. Giving up in 00:{0:02d}:{1:02d}'.format(
                int(timeout // 60),
                int(timeout % 60)
            )
        )
        data = update_callback(*update_args, **update_kwargs)
        if data is False:
            log.debug(
                'update_callback has returned False which is considered a '
                'failure. Remaining Failures: {0}'.format(max_failures)
            )
            max_failures -= 1
            if max_failures <= 0:
                raise SaltCloudExecutionFailure(
                    'Too much failures occurred while waiting for '
                    'the IP address'
                )
        elif data is not None:
            return data

        if timeout < 0:
            raise SaltCloudExecutionTimeout(
                'Unable to get IP for 00:{0:02d}:{1:02d}'.format(
                    int(duration // 60),
                    int(duration % 60)
                )
            )
        time.sleep(interval)
        timeout -= interval


def simple_types_filter(datadict):
    '''
    Convert the data dictionary into simple types, ie, int, float, string,
    bool, etc.
    '''
    simpletypes = (str, unicode, int, long, float, bool)
    simpledict = {}
    for key, value in datadict.iteritems():
        if key is not None and not isinstance(key, simpletypes):
            key = repr(key)
        if isinstance(value, dict):
            value = simple_types_filter(value)
        elif value is not None and not isinstance(value, simpletypes):
            value = repr(value)
        simpledict[key] = value
    return simpledict
