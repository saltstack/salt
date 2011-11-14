'''
Specialized routines used by the butter cloud component
'''

import copy
import os
import shutil
import subprocess
import tempfile


def _place_image(image, vda):
    '''
    Moves the image file from the image pool into the final destination.
    '''
    image_d = image + '.d'
    vda_dir = os.path.dirname(vda)
    if not os.path.isdir(vda_dir):
        os.makedirs(vda_dir)
    if not os.path.isdir(image_d):
        # No available images in the pool, copying fresh image
        shutil.copy(image, vda)
        return
    images = os.listdir(image_d)
    if not images:
        # No available images in the pool, copying fresh image
        shutil.copy(image, vda)
        return
    shutil.move(os.path.join(image_d, images[0]), vda)

    creds = libvirt_creds()
    if not os.path.isdir(vda_dir):
        os.makedirs(vda_dir)
        tdir = copy.deepcopy(vda_dir)
        while not tdir == '/':
            os.chmod(tdir, 493)
            tdir = os.path.dirname(tdir)
    ch_cmd = 'chown ' + creds['user'] + ':' + creds['group'] + ' '\
           + vda
    subprocess.call(ch_cmd, shell=True)


def _gen_pin_drives(pins):
    '''
    Generate the "pinned" vm image
    '''
    creds = libvirt_creds()
    for pin in pins:
        dirname = os.path.dirname(pin['path'])
        if os.path.exists(pin['path']):
            continue
        if not os.path.isdir(dirname):
            os.makedirs(dirname)
            tdir = copy.deepcopy(dirname)
            while not tdir == '/':
                os.chmod(tdir, 493)
                tdir = os.path.dirname(tdir)

        i_cmd = 'qemu-img create ' + pin['path'] + ' ' + pin['size'] + 'G'
        f_cmd = 'yes | mkfs.' + pin['filesystem'] + ' ' + pin['path']
        ch_cmd = 'chown ' + creds['user'] + ':' + creds['group'] + ' '\
               + pin['path']
        subprocess.call(i_cmd, shell=True)
        subprocess.call(f_cmd, shell=True)
        if pin['filesystem'].startswith('ext'):
            t_cmd = 'tune2fs -c 0 -i 0 ' + pin['filesystem']
            subprocess.call(t_cmd, shell=True)
        if pin['format'] == 'qcow2':
            q_cmd = 'qemu-img convert -O qcow2 ' + pin['path'] + ' '\
                  + pin['path'] + '.tmp'
            subprocess.call(q_cmd, shell=True)
            shutil.move(pin['path'] + '.tmp', pin['path'])
        subprocess.call(ch_cmd, shell=True)
    return True


def _apply_overlay(vda, instance):
    '''
    Use libguestfs to apply the overlay under the specified instance to the
    specified vda
    '''
    overlay = os.path.join(instance, 'overlay')
    if not os.path.isdir(overlay):
        return False
    tmp = tempfile.mkdtemp()
    tar = os.path.join(tmp, 'host.tgz')
    cwd = os.getcwd()
    os.chdir(overlay)
    t_cmd = 'tar cvzf ' + tar + ' *'
    subprocess.call(t_cmd, shell=True)
    os.chdir(cwd)
    g_cmd = 'guestfish -i -a ' + vda + ' tgz-in ' + tar + ' /'
    subprocess.call(g_cmd, shell=True)
    shutil.rmtree(tmp)
    return True


def libvirt_creds():
    '''
    Returns the user and group that the disk images should be owned by

    CLI Example::

        salt '*' butterkvm.libvirt_creds
    '''
    g_cmd = 'grep group /etc/libvirt/qemu.conf'
    u_cmd = 'grep user /etc/libvirt/qemu.conf'
    group = subprocess.Popen(g_cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0].split('"')[1]
    user = subprocess.Popen(u_cmd,
            shell=True,
            stdout=subprocess.PIPE).communicate()[0].split('"')[1]
    return {'user': user, 'group': group}


def local_images(local_path):
    '''
    return the virtual machine names for all of the images located in the
    butter cloud's local_path in a list::

        ['vm1.boo.com', 'vm2.foo.com']

    CLI Example::

        salt '*' buttervm.local_images <image_path>
    '''
    if not os.path.isdir(local_path):
        return []
    images = os.listdir(local_path)
    images.sort()
    return images


def full_butter_data(local_path):
    '''
    Return the full virt info, but add butter data!

    CLI Example::

        salt '*' buttervm.full_butter_data <image_path>
    '''
    info = __salt__['virt.full_info']()
    info['local_images'] = local_images(local_path)
    return info


def create(instance, vda, image, pin):
    '''
    Create a virtual machine, this is part of the butter vm system and assumes
    that the files prepared by butter are available via shared storage.
    AKA - don't call this from the command line!

    instance : string
        The path to the instance directory for the given vm on shared storage
    vda
        The location where the virtual machine image needs to be placed
    image
        The image to move into place
    pin
        A "pin" data structure defining the myriad of possible vdb-vbz disk
        images to generate

    CLI Example::

        salt '*' butterkvm.create <instance dir> <root image location>\\
            <Destination> <pin data>
    '''
    if not os.path.isfile(vda):
        # Check that this is a fresh vm image, if so, copy it into place any
        # apply the overlay, otherwise, just start the vm
        _place_image(image, vda)
        _gen_pin_drives(pin)
        _apply_overlay(vda, instance)
    __salt__['virt.create_xml_path'](os.path.join(instance, 'config.xml'))
