# -*- coding: utf-8 -*-
'''
Qemu-img Command Wrapper
========================

The qemu img command is wrapped for specific functions

:depends: qemu-img
'''
from __future__ import absolute_import

# Import python libs
import os

# Import salt libs
import salt.utils


def __virtual__():
    '''
    Only load if qemu-img is installed
    '''
    if salt.utils.which('qemu-img'):
        return 'qemu_img'
    return False


def make_image(location, size, fmt):
    '''
    Create a blank virtual machine image file of the specified size in
    megabytes. The image can be created in any format supported by qemu

    CLI Example:

    .. code-block:: bash

        salt '*' qemu_img.make_image /tmp/image.qcow 2048 qcow2
        salt '*' qemu_img.make_image /tmp/image.raw 10240 raw
    '''
    if not os.path.isabs(location):
        return ''
    if not os.path.isdir(os.path.dirname(location)):
        return ''
    if not __salt__['cmd.retcode'](
            'qemu-img create -f {0} {1} {2}M'.format(
                fmt,
                location,
                size),
                python_shell=False):
        return location
    return ''
