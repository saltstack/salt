# -*- coding: utf-8 -*-
'''
Used to manage the outputter system. This package is the modular system used
for managing outputters.
'''

# Import python libs
import os
import sys
import errno

# Import salt libs
import salt.loader
import salt.utils


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
        display_data = get_printout(out, opts)(data).rstrip()
    except (KeyError, AttributeError):
        opts.pop('output', None)
        display_data = get_printout('nested', opts)(data).rstrip()

    output_filename = opts.get('output_file', None)
    try:
        if output_filename is not None:
            with salt.utils.fopen(output_filename, 'a') as ofh:
                ofh.write(display_data)
                ofh.write('\n')
            return
        if display_data:
            print(display_data)
    except IOError as exc:
        # Only raise if it's NOT a broken pipe
        if exc.errno != errno.EPIPE:
            raise exc


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

    if out is None:
        out = 'nested'

    opts.update(kwargs)
    if 'color' not in opts:
        def is_pipe():
            '''
            Check if sys.stdout is a pipe or not
            '''
            try:
                fileno = sys.stdout.fileno()
            except AttributeError:
                fileno = -1  # sys.stdout is StringIO or fake
            return not os.isatty(fileno)

        if opts.get('force_color', False):
            opts['color'] = True
        elif opts.get('no_color', False) or is_pipe():
            opts['color'] = False
        else:
            opts['color'] = True

    outputters = salt.loader.outputters(opts)
    if out not in outputters:
        return outputters['nested']
    return outputters[out]


def out_format(data, out, opts=None):
    '''
    Return the formatted outputter string for the passed data
    '''
    return get_printout(out, opts)(data).rstrip()
