# -*- coding: utf-8 -*-
'''
Display Pony output data structure
=================================

Display output from a pony. Ponies are better than cows
because everybody wants a pony.

Example output::
 _________________ 
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
           █▄▄██████   █▄▄██████    ▀        
             █▄▄▄▄█       █▄▄▄▄█       

'''

# Import Python libs
from __future__ import absolute_import

# Import Salt libs
import salt.utils.locales
import subprocess

def output(data):
    '''
    Rather basic....
    '''
    return(subprocess.check_output(['ponysay', salt.utils.locales.sdecode(data)]))
