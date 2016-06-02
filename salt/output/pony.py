# -*- coding: utf-8 -*-
'''
Display Pony output data structure
=================================

Display output from a pony. Ponies are better than cows
because everybody wants a pony.

Example output::

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
from __future__ import absolute_import
import os
import subprocess

# Import Salt libs
import salt.utils.locales


def __virtual__():
    return os.path.isfile('/usr/bin/ponysay')


def output(data):
    '''
    Mane function
    '''
    high_out = __salt__['highstate'](data)
    return subprocess.check_output(['ponysay', salt.utils.locales.sdecode(high_out)])  # pylint: disable=E0598
