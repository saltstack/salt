# -*- coding: utf-8 -*-
'''
Look for binaries in the default $PATH
======================================

This module searches the $PATH as seen by the minion process for a binary.

'''
from __future__ import absolute_import

import salt.utils

def find(binary_name):
    '''
    Try to find the specified binary in $PATH

    CLI Example::

        salt '*' which.find dig
    '''
    return salt.utils.which(binary_name)

def missing(binary_name):
   '''
   Try to prove that the specified binary is _not_ in $PATH

   CLI Example::

       salt '*' which.missing brew
   '''
   return not bool(salt.utils.which(binary_name))

