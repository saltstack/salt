#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
Runs all the example FloScripts


'''
# pylint: disable=3rd-party-module-not-gated

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import 3rd-party libs
import ioflo.app.run
from ioflo.base.consoling import getConsole

console = getConsole()

PLAN_DIR_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'plan'
)


def getPlanFiles(planDirPath=PLAN_DIR_PATH):
    planFiles = []
    for fname in os.listdir(os.path.abspath(planDirPath)):
        root, ext = os.path.splitext(fname)
        if ext != '.flo' or root.startswith('__'):
            continue

        planFiles.append(os.path.abspath(os.path.join(planDirPath, fname)))
    return planFiles


def main():
    '''
    Run example scripts
    '''
    console.concise('Test started')
    behaviors = ['salt.daemons.flo', 'salt.daemons.test.plan']
    failedCount = 0
    plans = getPlanFiles()
    for plan in plans:
        name, ext = os.path.splitext(os.path.basename(plan))
        skeddar = ioflo.app.run.run(name=name,
                            filepath=plan,
                            behaviors=behaviors,
                            period=0.0625,
                            verbose=1,
                            real=False,)

        print('Plan {0}\n  Skeddar {1}\n'.format(plan, skeddar.name))
        failed = False
        for house in skeddar.houses:
            failure = house.metas['failure'].value
            if failure:
                failed = True
                print('**** Failed in House = {0}. '
                      'Failure = {1}.\n'.format(house.name, failure))
            else:
                print('**** Succeeded in House = {0}.\n'.format(house.name))
        if failed:
            failedCount += 1

    print('{0} failed out of {1}.\n'.format(failedCount, len(plans)))


if __name__ == '__main__':
    console.reinit(verbosity=console.Wordage.profuse)
    main()
