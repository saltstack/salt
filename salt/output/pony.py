# -*- coding: utf-8 -*-
r'''
Display Pony output data structure
==================================

:depends:   - ponysay CLI program

Display output from a pony. Ponies are better than cows
because everybody wants a pony.

Example output:

.. code-block:: cfg

    < {'local': True} >
     -----------------
     \
      \
       \
        ▄▄▄▄▄▄▄
        ▀▄▄████▄▄
      ▄▄▄█████▄█▄█▄█▄▄▄
     ██████▄▄▄█▄▄█████▄▄
     ▀▄▀ █████▄▄█▄▄█████
         ▄▄▄███████████▄▄▄
         ████▄▄▄▄▄▄███▄▄██           ▄▄▄▄▄▄▄
         ████▄████▄██▄▄███       ▄▄▄▄██▄▄▄▄▄▄
        █▄███▄▄█▄███▄▄██▄▀     ▄▄███████▄▄███▄▄
        ▀▄██████████████▄▄    ▄▄█▄▀▀▀▄▄█████▄▄██
           ▀▀▀▀▀█████▄█▄█▄▄▄▄▄▄▄█     ▀▄████▄████
                ████▄███▄▄▄▄▄▄▄▄▄     ▄▄█████▄███
                ▀▄█▄█▄▄▄██▄▄▄▄▄██    ▄▄██▄██████
                 ▀▄████████████▄▀  ▄▄█▄██████▄▀
                  ██▄██▄▄▄▄█▄███▄ ███▄▄▄▄▄██▄▀
                  ██████  ▀▄▄█████ ▀████████
                 ▄▄▄▄███   ███████ ██████▄█▄▄
                 ███████   ████████▀▄▀███▄▄█▄▄
               ▄██▄▄████   ████████   ▀▄██▀▄▄▀
               █▄▄██████   █▄▄██████
                 █▄▄▄▄█       █▄▄▄▄█

'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import subprocess

# Import Salt libs
import salt.utils.locales
import salt.utils.path


__virtualname__ = 'pony'


def __virtual__():
    if salt.utils.path.which('ponysay'):
        return __virtualname__
    return False


def output(data, **kwargs):  # pylint: disable=unused-argument
    '''
    Mane function
    '''
    high_out = __salt__['highstate'](data)
    return subprocess.check_output(['ponysay', salt.utils.locales.sdecode(high_out)])  # pylint: disable=E0598
