#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Runs minion floscript

'''
# pylint: skip-file
import os
import salt.daemons.flo

FLO_DIR_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'flo'
)


def test():
    """ Execute run.start """
    filepath = os.path.join(FLO_DIR_PATH, 'master.flo')
    opts = dict(
            ioflo_period=0.1,
            ioflo_realtime=True,
            master_floscript=filepath,
            ioflo_verbose=2,
            raet_port=7530)

    master = salt.daemons.flo.IofloMaster(opts=opts)
    master.start()

if __name__ == '__main__':
    test()
