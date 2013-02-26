'''
Interact with virtual machine images via libguestfs

:depends:   - libguestfs
'''

# Import Salt libs
import salt.utils

def __virtual__():
    '''
    Only load if libguestfs python bindings are installed
    '''
    if salt.utils.which('guestmount'):
        return 'guestfs'
    return False


def seed(location, id_='', config=None):
    '''
    Seed a vm image before booting it

    CLI Example::

        salt '*' guestfs.seed /tmp/image.qcow2
    '''
    if config is None:
        config = {}
    
    
