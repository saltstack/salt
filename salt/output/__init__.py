'''
Used to manage the outputter system. This package is the modular system used
for managing outputters.
'''

import salt.loader

def display_output(data, out, opts=None):
    '''
    Print the passed data using the desired output
    '''
    if opts is None:
        opts = {}
    outputters = salt.loader.outputters(opts)
    if not out in outputters:
        outputters['pprint'](data)
    outputters[out](data)
