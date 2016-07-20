# -*- coding: utf-8 -*-
'''
Used to manage the outputter system. This package is the modular system used
for managing outputters.
'''

# Import python libs
from __future__ import print_function
from __future__ import absolute_import
import os
import sys
import errno
import logging
import traceback
from salt.ext.six import string_types

# Import salt libs
import salt.loader
import salt.utils
from salt.utils import print_cli
import salt.ext.six as six

# Are you really sure !!!
# dealing with unicode is not as simple as setting defaultencoding
# which can break other python modules imported by salt in bad ways...
# reloading sys is not either a good idea...
# reload(sys)
# sys.setdefaultencoding('utf-8')

log = logging.getLogger(__name__)


def try_printout(data, out, opts):
    '''
    Safely get the string to print out, try the configured outputter, then
    fall back to nested and then to raw
    '''
    try:
        return get_printout(out, opts)(data).rstrip()
    except (KeyError, AttributeError):
        log.debug(traceback.format_exc())
        try:
            return get_printout('nested', opts)(data).rstrip()
        except (KeyError, AttributeError):
            log.error('Nested output failed: ', exc_info=True)
            return get_printout('raw', opts)(data).rstrip()


def get_progress(opts, out, progress):
    '''
    Get the progress bar from the given outputter
    '''
    return salt.loader.raw_mod(opts,
                                out,
                                'rawmodule',
                                mod='output')['{0}.progress_iter'.format(out)](progress)


def update_progress(opts, progress, progress_iter, out):
    '''
    Update the progress iterator for the given outputter
    '''
    # Look up the outputter
    try:
        progress_outputter = salt.loader.outputters(opts)[out]
    except KeyError:  # Outputter is not loaded
        log.warning('Progress outputter not available.')
        return False
    progress_outputter(progress, progress_iter)


def progress_end(progress_iter):
    try:
        progress_iter.stop()
    except Exception:
        pass
    return None


def display_output(data, out=None, opts=None):
    '''
    Print the passed data using the desired output
    '''
    if opts is None:
        opts = {}
    display_data = try_printout(data, out, opts)

    output_filename = opts.get('output_file', None)
    log.trace('data = {0}'.format(data))
    try:
        # output filename can be either '' or None
        if output_filename:
            with salt.utils.fopen(output_filename, 'a') as ofh:
                fdata = display_data
                if isinstance(fdata, six.text_type):
                    try:
                        fdata = fdata.encode('utf-8')
                    except (UnicodeDecodeError, UnicodeEncodeError):
                        # try to let the stream write
                        # even if we didn't encode it
                        pass
                ofh.write(fdata)
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

    if 'output' in opts and opts['output'] != 'highstate':
        # new --out option, but don't choke when using --out=highstate at CLI
        # See Issue #29796 for more information.
        out = opts['output']

    if out == 'text':
        out = 'txt'
    elif out is None or out == '':
        out = 'nested'
    if opts.get('progress', False):
        out = 'progress'

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
    if out not in outputters:
        # Since the grains outputter was removed we don't need to fire this
        # error when old minions are asking for it
        if out != 'grains':
            log.error('Invalid outputter {0} specified, fall back to nested'.format(out))
        return outputters['nested']
    return outputters[out]


def out_format(data, out, opts=None):
    '''
    Return the formatted outputter string for the passed data
    '''
    return try_printout(data, out, opts)


def strip_esc_sequence(txt):
    '''
    Replace ESC (ASCII 27/Oct 33) to prevent unsafe strings
    from writing their own terminal manipulation commands
    '''
    if isinstance(txt, six.string_types):
        return txt.replace('\033', '?')
    else:
        return txt
