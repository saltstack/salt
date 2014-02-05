#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
ioflo CLI

Runs ioflo plan from command line shell

example:

ioflo -v verbose -n raet -p 0.0625 -f raet.flo -b raet
ioflo -v concise -n raet -p 0.0625 -f road/raet.flo -b road.raet.packeting road.raet.stacking
'''

# Import python libs
import sys

# Import ioflo libs
import ioflo.app.run


def main():
    '''
    Main entry point for ioflo CLI
    '''
    args = ioflo.app.run.parseArgs()

    if args.version:
        print 'ioflo version {0}'.format(ioflo.__version__)
        sys.exit(0)

    ioflo.app.run.run(name=args.name,
                      filename=args.filename,
                      period=float(args.period),
                      verbose=args.verbose,
                      realtime=args.realtime,
                      behaviors=args.behaviors,
                      username=args.username,
                      password=args.password,)

if __name__ == '__main__':
    main()
