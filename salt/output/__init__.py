'''
Used to manage the outputter system. This package is the modular system used
for managing outputters.
'''

# Import salt utils
import salt.loader


STATIC = (
          'yaml_out',
          'text_out',
          'raw_out',
          'json_out',
          )


def display_output(data, out, opts=None):
    '''
    Print the passed data using the desired output
    '''
    print(get_printout(out, opts)(data).rstrip())


def get_printout(out, opts=None, **kwargs):
    '''
    Return a printer function
    '''
    if opts is None:
        opts = {}
    for outputter in STATIC:
        if outputter in opts:
            if opts[outputter]:
                if outputter == 'text_out':
                    out = 'txt'
                else:
                    out = outputter
    if out is None:
        out = 'pprint'
    if out.endswith('_out'):
        out = out[:-4]
    if opts is None:
        opts = {}
    opts.update(kwargs)
    if not 'color' in opts:
        opts['color'] = not bool(opts.get('no_color', False))
    outputters = salt.loader.outputters(opts)
    if not out in outputters:
        return outputters['pprint']
    return outputters[out]


def out_format(data, out, opts=None):
    '''
    Return the formatted outputter string for the passed data
    '''
    return get_printout(out, opts)(data).rstrip()

