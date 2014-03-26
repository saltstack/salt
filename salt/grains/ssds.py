# -*- coding: utf-8 -*-
'''
    Detect SSDs
'''
import os
import salt.utils
import logging

log = logging.getLogger(__name__)

def ssds():
    '''
    Return list of disk devices that are SSD (non-rotational)
    '''

    SSDs = []
    for subdir, dirs, files in os.walk('/sys/block'):
        for dir in dirs:
            flagfile = subdir + '/' + dir + '/queue/rotational'
            if os.path.isfile(flagfile):
                with salt.utils.fopen(flagfile, 'r') as _fp:
                    flag = _fp.read(1)
                    if flag == '0':
                        SSDs.append(dir)
                        log.info(dir + ' is a SSD')
                    elif flag == '1':
                        log.info(dir + ' is no SSD')
                    else:
                        log.warning(flagfile + ' does not report 0 or 1')
                log.debug(flagfile + ' reports ' + flag)
            else:
                log.warning(flagfile + ' does not exist for ' + dir)
            
    return {'SSDs': SSDs}
