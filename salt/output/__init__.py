'''
Used to manage the outputter system. This package is the modular system used
for managing outputters.
'''

# Import salt utils
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

def get_printout(out, opts=None, **kwargs):
    '''
    Return a printer function
    '''
    if opts is None:
        opts = {}
    opts.update(kwargs)
    outputters = salt.loader.outputters(opts)
    if not out in outputters:
        return outputters['pprint']
    return outputters[out]

