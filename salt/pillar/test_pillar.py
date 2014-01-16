# -*- coding: utf-8 -*-
'''
Dumb test pillar module
'''

# Import python libs
import logging
import re
    
def __virtual__():
    return 'test_pillar'

# Set up logging
log = logging.getLogger(__name__)

def ext_pillar(minion_id,
               pillar,
               collection='pillar',
               id_field='_id',
               re_pattern=None,
               re_replace='',
               fields=None):

    my_pillar = { 'junos_hosts':
                  {
                      'junos' : {
                          'user' : 'cro',
                          'passwd': 'croldham123'
                      },
                      'junos1' : {
                          'user' : 'cro',
                          'passwd' : 'croldham123'
                      }
                  }
                }
    return my_pillar
