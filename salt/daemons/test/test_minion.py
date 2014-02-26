#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Runs minion floscript


"""
# pylint: skip-file
import os
import salt.daemons.flo
import ioflo.app.run

FLO_DIR_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    , 'flo')


def test():
    """ Execute run.start """
    filepath = os.path.join(FLO_DIR_PATH, 'minion.flo')
    opts = dict(
            id="MinionTest",
            ioflo_period=0.1,
            ioflo_realtime=True,
            minion_floscript=filepath,
            ioflo_verbose=2,
            raet_port=7531, )

    minion = salt.daemons.flo.IofloMinion(opts=opts)
    minion.start()

if __name__ == '__main__':
    test()
