# -*- coding: utf-8 -*-
'''
Used to manage the outputter system. This package is the modular system used
for managing outputters.
'''

# Import python libs
from __future__ import print_function
import os
import sys
import errno
import logging
import traceback

# Import salt libs
import salt.loader
import salt.utils
from salt.utils import print_cli


log = logging.getLogger(__name__)

STATIC = (
    'yaml_out',
    'text_out',
    'raw_out',
    'json_out',
)


def display_output(data, out=None, opts=None):
    '''
    Print the passed data using the desired output
    '''
    try:
        display_data = get_printout(out, opts)(data).rstrip()
    except (KeyError, AttributeError):
        log.debug(traceback.format_exc())
        opts.pop('output', None)
        display_data = get_printout('nested', opts)(data).rstrip()

    output_filename = opts.get('output_file', None)
    log.trace('data = {0}'.format(data))
    try:
        if output_filename is not None:
            with salt.utils.fopen(output_filename, 'a') as ofh:
                ofh.write(display_data)
                ofh.write('\n')
            return
        if display_data:
            print_cli(display_data)
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
        elif opts.get('no_color', False) or is_pipe() or salt.utils.is_windows():
            opts['color'] = False
        else:
            opts['color'] = True

    outputters = salt.loader.outputters(opts)
    # TODO: raise an exception? This means if you do --out foobar you get nested
    if out not in outputters:
        return outputters['nested']
    return outputters[out]


def out_format(data, out, opts=None):
    '''
    Return the formatted outputter string for the passed data
    '''
    return get_printout(out, opts)(data).rstrip()


def strip_esc_sequence(txt):
    '''
    Replace ESC (ASCII 27/Oct 33) to prevent unsafe strings
    from writing their own terminal manipulation commands
    '''
    if isinstance(txt, basestring):
        return txt.replace('\033', '?')
    else:
        return txt
