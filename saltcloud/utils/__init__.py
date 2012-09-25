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
import paramiko
import subprocess

# Import salt libs
import salt.crypt

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
            'deploy')
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
    salt.crypt.gen_keys(
            tdir,
            'minion',
            keysize)
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
    keys dir if that is the case.
    '''
    key = os.path.join(
            pki_dir,
            'minions/{0}'.format(id_)
            )
    with open(key, 'w+') as fp_:
        fp_.write(pub)


def get_option(option, opts, vm_):
    '''
    Convenience function to return the dominant option to be used. Always
    default to options set in the vm structure, but if the option is not
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
    minion.update(opts.get('map_minion', {}))
    minion.update(vm_.get('map_minion', {}))
    optsgrains = opts.get('map_grains', {})
    if optsgrains:
        minion['grains'].update(optsgrains)
    vmgrains = vm_.get('map_grains', {})
    if vmgrains:
        minion['grains'].update(vmgrains)
    return yaml.safe_dump(minion, default_flow_style=False)


def wait_for_ssh(host, port=22, timeout=900):
    '''
    Wait until an ssh connection can be made on a specified host
    '''
    start = time.time()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while True:
        try:
            sock.connect((host, port))
            sock.shutdown(2)
            return True
        except Exception:
            time.sleep(1)
            if time.time() - start > timeout:
                return False


def wait_for_passwd(host, port=22, timeout=900, username='root',
                    password=None, key_filename=None, maxtries=50,
                    trysleep=1):
    '''
    Wait until ssh connection can be accessed via password or ssh key
    '''
    start = time.time()
    trycount=0
    while True:
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
            except paramiko.AuthenticationException as authexc:
                trycount += 1
                print('Authentication error (try {0}  of {1}): {2}'.format(trycount, maxtries, authexc))
                if trycount < maxtries:
                    sleep(trysleep)
                    continue
                else:
                    print('Authencication failed: {0}'.format(authexec))
                    return False
            except Exception as exc:
                print('There was an error in wait_for_passwd: {0}'.format(exc))
            return True
        except Exception:
            time.sleep(1)
            if time.time() - start > timeout:
                return False

def deploy_script(host, port=22, timeout=900, username='root',
                  password=None, key_filename=None, script=None,
                  deploy_command='bash /tmp/deploy.sh', tty=None):
    '''
    Copy a deploy script to a remote server, execute it, and remove it
    '''
    if wait_for_ssh(host=host, port=port, timeout=timeout):
        if wait_for_passwd(host, port=port, username=username, password=password, key_filename=key_filename, timeout=timeout):
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
            except Exception as exc:
                print('There was an error in deploy_script: {0}'.format(exc))
            tmpfh, tmppath = tempfile.mkstemp()
            tmpfile = open(tmppath, 'w')
            tmpfile.write(script)
            tmpfile.close()
            sftp = ssh.get_transport()
            sftp.open_session()
            sftp = paramiko.SFTPClient.from_transport(sftp)
            sftp.put(tmppath, '/tmp/deploy.sh')
            os.remove(tmppath)
            ssh.exec_command('chmod +x /tmp/deploy.sh')
            if tty:
                # Tried this with paramiko's invoke_shell(), and got tired of
                # fighting with it
                cmd = ('ssh -oStrictHostKeyChecking=no -t -i {0} {1}@{2} "sudo bash /tmp/deploy.sh"').format(
                        key_filename,
                        username,
                        host
                        )
                subprocess.call(cmd, shell=True)
            else:
                stdin, stdout, stderr = ssh.exec_command(deploy_command)
                for line in stdout:
                    sys.stdout.write(line)
            ssh.exec_command('rm /tmp/deploy.sh')
            return True
    return False
