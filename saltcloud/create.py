'''
The generic libcloud template used to create the connections and deploy the
cloud virtual machines
'''

# Import python libs
import os
import tempfile
import shutil

#
# Import libcloud
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.deployment import MultiStepDeployment, ScriptDeployment, SSHKeyDeployment

# Import salt libs
import saltcloud.utils
import salt.crypt


class Create(object):
    '''
    An object for the creation of new inages
    '''
    def __init__(self, opts):
        self.opts = opts

    def conn(self, vm_):
        '''
        Return a conn object for the passed vm data
        '''
        prov = ''
        if 'provider' in vm_:
            prov = vm_['provider']
            if 'location' in vm_:
                prov += '_{0}'.format(vm_['location'])
        if not prov:
            if 'provider' in self.opts:
                prov = self.opts['provider']
                if 'location' in self.opts:
                    if self.opts['location']:
                        prov += '_{0}'.format(self.opts['location'])
        if not hasattr(Provider, prov):
            return None
        driver = get_driver(getattr(Provider, prov.split('_')[0]))
        return driver(
                self.opts['{0}_user'.format(prov.split('_')[0])],
                self.opts['{0}_key'.format(prov.split('_')[0])])

    def ssh_pub(self, vm_):
        '''
        Deploy the primary ssh authentication key
        '''
        ssh = ''
        if 'ssh_auth' in vm_:
            if not os.path.isfile(vm_['ssh_auth']):
                return None
            ssh = vm_['ssh_auth']
        if not ssh:
            if not os.path.isfile(self.opts['ssh_auth']):
                return None
            ssh = self.opts['ssh_auth']

        return SSHKeyDeployment(open(os.path.expanduser(ssh)).read())

    def script(self, vm_):
        '''
        Return the deployment object for managing a script
        '''
        os_ = ''
        if 'os' in vm_:
            os_ = vm_['os']
        if not os_:
            os_ = self.opts['os']
        return ScriptDeployment(saltcloud.utils.os_script(os_))

    def image(self, conn, vm_):
        '''
        Return the image object to use
        '''
        images = conn.list_images()
        if not 'image' in vm_:
            return images[0]
        if isinstance(vm_['image'], int):
            return images[vm_['image']]
        for img in images:
            if img.id == vm_['image']:
                return img

    def size(self, conn, vm_):
        '''
        Return the vm's size object
        '''
        sizes = conn.list_sizes()
        if not 'size' in vm_:
            return sizes[0]
        if isinstance(vm_['size'], int):
            return sizes[vm_['size']]
        for size in sizes:
            if size.id == vm_['size']:
                return size
            if size.name == vm_['size']:
                return size

    def create(self, vm_):
        '''
        Create a single vm from a data dict
        '''
        conn = self.conn(vm_)
        msd = MultiStepDeployment([self.ssh_pub(vm_), self.script(vm_)])
        image = self.image(conn, vm_)
        size = self.size(conn, vm_)
        return conn.deploy_node(
                name=vm_['name'],
                image=image,
                size=size,
                deploy=msd)

    def gen_keys(self):
        '''
        Generate the minion keys and return them as strings
        '''
        tdir = tempfile.mkdtemp()
        salt.crypt.gen_keys(
                tdir,
                'minion',
                self.opts['keysize'])
        priv_path = os.path.join(tdir, 'minion.pem')
        pup_path = os.path.join(tdir, 'minion.pub')
        with open(priv_path) as fp_:
            priv = fp_.read()
        with open(pub_path) as fp_:
            pub = fp_.read()
        shutil.rmtree(tdir)
        return priv, pub

    def accept_key(self, pub, id_):
        '''
        If the master config was available then we will have a pki_dir key in
        the opts directory, this method places the pub key in the accepted
        keys dir if that is the case.
        '''
        if not 'pki_dir' in self.opts:
            return False
        key = os.path.join(
                self.opts['pki_dir'],
                'minions/{0}.pub'.format(id_)
                )
        with open(key, 'w+') as fp_:
            fp_.write(pub)

    def run_data(self):
        '''
        Create/Verify the vms in the vm data
        '''
        for vm_ in self.opts['vm']:
            self.create(vm_)


