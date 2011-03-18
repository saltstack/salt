'''
Specilized routines used by the butter cloud component
'''
# Import salt modules
import virt

# Import python modules
import os

def local_images(local_path):
    '''
    return the virtual machine names for all of the images located in the
    butter cloud's local_path in a list:

    ['vm1.boo.com', 'vm2.foo.com']

    CLI Example:
    salt '*' buttervm.local_images <image_path>
    '''
    vms = os.listdir(local_path)

def full_butter_data(local_path):
    '''
    Return the full virt info, but add butter data!

    CLI Example:
    salt '*' buttervm.full_butter_data <image_path>
    '''
    info = virt.full_info()
    info['butter'] = {}
    info['butter']['local_images'] = local_images(local_path)
    return info

