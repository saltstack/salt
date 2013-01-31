'''
Utility functions for saltcloud
'''

# Import python libs
import os
import sys
import shutil
import socket
import tempfile
import time
import subprocess
import salt.utils.event
import multiprocessing
import logging
import types
import re

# Get logging started
log = logging.getLogger(__name__)

try:
    import paramiko
except:
    raise ImportError(
        'Cannot import paramiko. Please make sure it is correctly installed.'
    )

# Import salt libs
import salt.crypt
import salt.client
from salt.exceptions import SaltException

# Import third party libs
from jinja2 import Template
import yaml

NSTATES = {
    0: 'running',
    1: 'rebooting',
    2: 'terminated',
    3: 'pending',
}


def os_script(os_, vm_=None, opts=None, minion=''):
    '''
    Return the script as a string for the specific os
    '''
    deploy_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'deploy'
    )
    for fn_ in os.listdir(deploy_path):
        full = os.path.join(deploy_path, fn_)
        if not os.path.isfile(full):
            continue
        if os_.lower() == fn_.split('.')[0].lower():
            # found the right script to embed, go for it
            try:
                with open(full, 'r') as fp_:
                    template = Template(fp_.read())
                return str(template.render(opts=opts, vm=vm_, minion=minion))
            except AttributeError:
                # Specified renderer was not found
                continue
    # No deploy script was found, return an empy string
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
    with open(priv_path) as fp_:
        priv = fp_.read()
    with open(pub_path) as fp_:
        pub = fp_.read()
    shutil.rmtree(tdir)
    return priv, pub


def accept_key(pki_dir, pub, id_):
    '''
    If the master config was available then we will have a pki_dir key in
    the opts directory, this method places the pub key in the accepted
    keys dir and removes it from the unaccepted keys dir if that is the case.
    '''
    if not os.path.exists(pki_dir):
        os.makedirs(pki_dir)

    key = os.path.join(
        pki_dir,
        'minions/{0}'.format(id_)
    )
    with open(key, 'w+') as fp_:
        fp_.write(pub)

    oldkey = os.path.join(
        pki_dir,
        'minions_pre/{0}'.format(id_)
    )
    if os.path.isfile(oldkey):
        with open(oldkey) as fp_:
            if fp_.read() == pub:
                os.remove(oldkey)


def remove_key(pki_dir, id_):
    '''
    This method removes a specified key from the accepted keys dir
    '''
    key = os.path.join(
        pki_dir,
        'minions/{0}'.format(id_)
    )
    if os.path.isfile(key):
        os.remove(key)


def rename_key(pki_dir, id_, new_id):
    '''
    Rename a key, when an instance has also been renamed
    '''
    oldkey = os.path.join(pki_dir, 'minions/{0}'.format(id_))
    newkey = os.path.join(pki_dir, 'minions/{0}'.format(new_id))
    if os.path.isfile(oldkey):
        os.rename(oldkey, newkey)


def get_option(option, opts, vm_):
    '''
    Convenience function to return the dominant option to be used. Always
    default to options set in the VM structure, but if the option is not
    present there look for it in the main config file
    '''
    if option in vm_:
        return vm_[option]
    if option in opts:
        return opts[option]


def minion_conf_string(opts, vm_):
    '''
    Return a string to be passed into the deployment script for the minion
    configuration file
    '''
    minion = {'id': vm_['name']}
    if 'master_finger' in vm_:
        minion['master_finger'] = vm_['master_finger']
    minion.update(opts.get('minion', {}))
    minion.update(vm_.get('minion', {}))
    if 'master' not in minion:
        raise ValueError("A master was not defined.")
    minion.update(opts.get('map_minion', {}))
    minion.update(vm_.get('map_minion', {}))
    optsgrains = opts.get('map_grains', {})
    if optsgrains:
        minion.setdefault('grains', {}).update(optsgrains)
    vmgrains = vm_.get('map_grains', {})
    if vmgrains:
        minion.setdefault('grains', {}).update(vmgrains)
    return yaml.safe_dump(minion, default_flow_style=False)


def master_conf_string(opts, vm_):
    '''
    Return a string to be passed into the deployment script for the master
    configuration file
    '''
    master = {}

    master.update(opts.get('master', {}))
    master.update(vm_.get('master', {}))

    master.update(opts.get('map_master', {}))
    master.update(vm_.get('map_master', {}))

    return yaml.safe_dump(master, default_flow_style=False)


def wait_for_ssh(host, port=22, timeout=900):
    '''
    Wait until an ssh connection can be made on a specified host
    '''
    start = time.time()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    trycount = 0
    while True:
        trycount += 1
        try:
            sock.connect((host, port))
            sock.shutdown(2)
            return True
        except Exception:
            time.sleep(1)
            log.debug('Retrying SSH connection (try {0})'.format(trycount))
            if time.time() - start > timeout:
                log.error('SSH connection timed out: {0}'.format(timeout))
                return False


def wait_for_passwd(host, port=22, timeout=900, username='root',
                    password=None, key_filename=None, maxtries=50,
                    trysleep=1):
    '''
    Wait until ssh connection can be accessed via password or ssh key
    '''
    trycount = 0
    while trycount < maxtries:
        connectfail = False
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            kwargs = {'hostname': host,
                      'port': 22,
                      'username': username,
                      'timeout': 15}
            if password and not key_filename:
                kwargs['password'] = password
            if key_filename:
                kwargs['key_filename'] = key_filename
            try:
                ssh.connect(**kwargs)
            except (paramiko.AuthenticationException,
                    paramiko.SSHException) as authexc:
                connectfail = True
                ssh.close()
                trycount += 1
                log.debug(
                    'Attempting to authenticate (try {0} of {1}): {2}'.format(
                        trycount, maxtries, authexc
                    )
                )
                if trycount < maxtries:
                    time.sleep(trysleep)
                    continue
                else:
                    log.error('Authentication failed: {0}'.format(authexc))
                    return False
            except Exception as exc:
                log.error(
                    'There was an error in wait_for_passwd: {0}'.format(exc)
                )
            if connectfail is False:
                return True
            return False
        except Exception:
            time.sleep(trysleep)
            if trycount >= maxtries:
                return False


def deploy_script(host, port=22, timeout=900, username='root',
                  password=None, key_filename=None, script=None,
                  deploy_command='/tmp/deploy.sh', sudo=False, tty=None,
                  name=None, pub_key=None, sock_dir=None, provider=None,
                  conf_file=None, start_action=None, make_master=False,
                  master_pub=None, master_pem=None, master_conf=None,
                  minion_pub=None, minion_pem=None, minion_conf=None,
                  keep_tmp=False):
    '''
    Copy a deploy script to a remote server, execute it, and remove it
    '''
    starttime = time.mktime(time.localtime())
    log.debug('Deploying {0} at {1}'.format(host, starttime))
    if wait_for_ssh(host=host, port=port, timeout=timeout):
        log.debug('SSH port {0} on {1} is available'.format(port, host))
        newtimeout = timeout - (time.mktime(time.localtime()) - starttime)
        if wait_for_passwd(host, port=port, username=username,
                           password=password, key_filename=key_filename,
                           timeout=newtimeout):
            log.debug(
                'Logging into {0}:{1} as {2}'.format(
                    host, port, username
                )
            )
            newtimeout = timeout - (time.mktime(time.localtime()) - starttime)
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            kwargs = {'hostname': host,
                      'port': 22,
                      'username': username,
                      'timeout': 15}
            if password and not key_filename:
                log.debug('Using {0} as the password'.format(password))
                kwargs['password'] = password
            if key_filename:
                log.debug('Using {0} as the key_filename'.format(key_filename))
                kwargs['key_filename'] = key_filename
            try:
                ssh.connect(**kwargs)
                log.debug('SSH connection to {0} successful'.format(host))
            except Exception as exc:
                log.error(
                    'There was an error in deploy_script: {0}'.format(exc)
                )
            if provider == 'ibmsce':
                ssh.exec_command(
                    'sudo sed -i "s/#Subsystem/Subsystem/" '
                    '/etc/ssh/sshd_config'
                )
                stdin, stdout, stderr = ssh.exec_command(
                    'sudo service sshd restart'
                )
                for line in stdout:
                    sys.stdout.write(line)
                ssh.connect(**kwargs)
            sftp = ssh.get_transport()
            sftp.open_session()
            sftp = paramiko.SFTPClient.from_transport(sftp)

            # Minion configuration
            if minion_pem:
                sftp_file(sftp, host, '/tmp/minion.pem', minion_pem)
                ssh.exec_command('chmod 600 /tmp/minion.pem')
            if minion_pub:
                sftp_file(sftp, host, '/tmp/minion.pub', minion_pub)
            if minion_conf:
                sftp_file(sftp, host, '/tmp/minion', minion_conf)

            # Master configuration
            if master_pem:
                sftp_file(sftp, host, '/tmp/master.pem', master_pem)
                ssh.exec_command('chmod 600 /tmp/master.pem')
            if master_pub:
                sftp_file(sftp, host, '/tmp/master.pub', master_pub)
            if master_conf:
                sftp_file(sftp, host, '/tmp/master', master_conf)

            # The actual deploy script
            if script:
                sftp_file(sftp, host, '/tmp/deploy.sh', script)
            ssh.exec_command('chmod +x /tmp/deploy.sh')

            newtimeout = timeout - (time.mktime(time.localtime()) - starttime)
            queue = None
            process = None
            # Consider this code experimental. It causes Salt Cloud to wait
            # for the minion to check in, and then fire a startup event.
            # Unfortunately, it doesn't currently work with Paramiko.
            if start_action:
                queue = multiprocessing.Queue()
                process = multiprocessing.Process(
                    target=lambda: check_auth(name=name, pub_key=pub_key,
                                              sock_dir=sock_dir,
                                              timeout=newtimeout, queue=queue)
                )
                log.debug('Starting new process to wait for salt-minion')
                process.start()

            # Run the deploy script
            if script:
                log.debug('Executing /tmp/deploy.sh')
                if make_master:
                    deploy_command += ' -m'
                if 'bootstrap-salt-minion' in script:
                    deploy_command += ' -c /tmp/'
                root_cmd(deploy_command, tty, sudo, **kwargs)
                log.debug('Executed /tmp/deploy.sh')

                # Remove the deploy script
                if not keep_tmp:
                    ssh.exec_command('rm /tmp/deploy.sh')
                    log.debug('Removed /tmp/deploy.sh')

            if keep_tmp:
                log.debug('Not removing deloyment files from /tmp/')

            # Remove minion configuration
            if not keep_tmp:
                if minion_pub:
                    ssh.exec_command('rm /tmp/minion.pub')
                    log.debug('Removed /tmp/minion.pub')
                if minion_pem:
                    ssh.exec_command('rm /tmp/minion.pem')
                    log.debug('Removed /tmp/minion.pem')
                if minion_conf:
                    ssh.exec_command('rm /tmp/minion')
                    log.debug('Removed /tmp/minion')

            # Remove master configuration
            if not keep_tmp:
                if master_pub:
                    ssh.exec_command('rm /tmp/master.pub')
                    log.debug('Removed /tmp/master.pub')
                if master_pem:
                    ssh.exec_command('rm /tmp/master.pem')
                    log.debug('Removed /tmp/master.pem')
                if master_conf:
                    ssh.exec_command('rm /tmp/master')
                    log.debug('Removed /tmp/master')

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


def sftp_file(transport, host, dest_path, contents):
    '''
    Given an established sftp session, this function will copy a file to a
    server using said sftp transport
    '''
    tmpfh, tmppath = tempfile.mkstemp()
    tmpfile = open(tmppath, 'w')
    tmpfile.write(contents)
    tmpfile.close()
    log.debug('Uploading {0} to {1}'.format(dest_path, host))
    transport.put(tmppath, dest_path)
    os.remove(tmppath)


def root_cmd(command, tty, sudo, **kwargs):
    '''
    Wrapper for commands to be run as root
    '''
    if sudo:
        command = 'sudo ' + command
        log.debug('Using sudo to run command')

    log.debug('Executing command: {0}'.format(command))
    if tty:
        # Tried this with paramiko's invoke_shell(), and got tired of
        # fighting with it
        log.debug(
            'Using ssh command to simulate tty session, to execute command'
        )
        cmd = 'ssh -oStrictHostKeyChecking=no -t -i {0} {1}@{2} "{3}"'.format(
            kwargs['key_filename'],
            kwargs['username'],
            kwargs['hostname'],
            command
        )
        subprocess.call(cmd, shell=True)
    else:
        log.debug('Using paramiko to execute command')
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(**kwargs)
        stdin, stdout, stderr = ssh.exec_command(command)
        for line in stdout:
            sys.stdout.write(line)


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


def check_name(name, pattern):
    '''
    Check whether the specified name contains invalid characters
    '''
    regexp = re.compile(pattern)
    if not regexp.match(name):
        raise SaltException(
            '{0} contains characters not supported by this cloud provider. '
            'Valid characters are: {1}'.format(
                name, pattern
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
