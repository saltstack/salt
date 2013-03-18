'''
Used to manage the outputter system. This package is the modular system used
for managing outputters.
'''

# Import salt libs
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
    try:
        print(get_printout(out, opts)(data).rstrip())
    except Exception:
        opts.pop('output', None)
        print(get_printout('nested', opts)(data).rstrip())


def get_printout(out, opts=None, **kwargs):
    '''
    Return a printer function
    '''
    if opts is None:
        opts = {}

    if 'output' in opts:
        # new --out option
        out = opts['output']
        if out == 'text':
            out = 'txt'
    else:
        # XXX: This should be removed before 0.10.8 comes out
        for outputter in STATIC:
            if outputter in opts:
                if opts[outputter]:
                    if outputter == 'text_out':
                        out = 'txt'
                    else:
                        out = outputter
        if out and out.endswith('_out'):
            out = out[:-4]

    if out is None:
        out = 'nested'

    opts.update(kwargs)
    if not 'color' in opts:
        opts['color'] = not bool(opts.get('no_color', False))
    outputters = salt.loader.outputters(opts)
    if not out in outputters:
        return outputters['nested']
    return outputters[out]


def out_format(data, out, opts=None):
    '''
    Return the formatted outputter string for the passed data
    '''
    return get_printout(out, opts)(data).rstrip()
