# -*- coding: utf-8 -*-
'''
Module to return data fetched using the Liquid system
=====================================================
'''
from __future__ import absolute_import

# Import salt libs
import salt.utils.args
import salt.utils.liquid


def fetch(**kwargs):
    '''
    '''
    clean_kwargs = salt.utils.args.clean_kwargs(**kwargs)
    return salt.utils.liquid.fetch(__opts__, utils=__utils__, **clean_kwargs)
