# -*- coding: utf-8 -*-
'''
Used to manage the outputter system. This package is the modular system used
for managing outputters.
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import errno
import logging
import io
import os
import re
import sys
import traceback

# Import Salt libs
import salt.loader
import salt.utils.files
import salt.utils.platform
import salt.utils.stringutils

# Import 3rd-party libs
from salt.ext import six

# Are you really sure !!!
# dealing with unicode is not as simple as setting defaultencoding
# which can break other python modules imported by salt in bad ways...
# reloading sys is not either a good idea...
# reload(sys)
# sys.setdefaultencoding('utf-8')

log = logging.getLogger(__name__)


def try_printout(data, out, opts, **kwargs):
    '''
    Safely get the string to print out, try the configured outputter, then
    fall back to nested and then to raw
    '''
    try:
        printout = get_printout(out, opts)(data, **kwargs)
        if printout is not None:
            return printout.rstrip()
    except (KeyError, AttributeError, TypeError):
        log.debug(traceback.format_exc())
        try:
            printout = get_printout('nested', opts)(data, **kwargs)
            if printout is not None:
                return printout.rstrip()
        except (KeyError, AttributeError, TypeError):
            log.error('Nested output failed: ', exc_info=True)
            printout = get_printout('raw', opts)(data, **kwargs)
            if printout is not None:
                return printout.rstrip()


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


def display_output(data, out=None, opts=None, **kwargs):
    '''
    Print the passed data using the desired output
    '''
    if opts is None:
        opts = {}
    display_data = try_printout(data, out, opts, **kwargs)

    output_filename = opts.get('output_file', None)
    log.trace('data = %s', data)
    try:
        # output filename can be either '' or None
        if output_filename:
            if not hasattr(output_filename, 'write'):
                ofh = salt.utils.files.fopen(output_filename, 'a')  # pylint: disable=resource-leakage
                fh_opened = True
            else:
                # Filehandle/file-like object
                ofh = output_filename
                fh_opened = False

            try:
                fdata = display_data
                if isinstance(fdata, six.text_type):
                    try:
                        fdata = fdata.encode('utf-8')
                    except (UnicodeDecodeError, UnicodeEncodeError):
                        # try to let the stream write
                        # even if we didn't encode it
                        pass
                if fdata:
                    ofh.write(salt.utils.stringutils.to_str(fdata))
                    ofh.write('\n')
            finally:
                if fh_opened:
                    ofh.close()
            return
        if display_data:
            salt.utils.stringutils.print_cli(display_data)
    except IOError as exc:
        # Only raise if it's NOT a broken pipe
        if exc.errno != errno.EPIPE:
            six.reraise(*sys.exc_info())


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

    # Handle setting the output when --static is passed.
    if not out and opts.get('static'):
        if opts.get('output'):
            out = opts['output']
        elif opts.get('fun', '').split('.')[0] == 'state':
            # --static doesn't have an output set at this point, but if we're
            # running a state function and "out" hasn't already been set, we
            # should set the out variable to "highstate". Otherwise state runs
            # are set to "nested" below. See Issue #44556 for more information.
            out = 'highstate'

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
            except (AttributeError, io.UnsupportedOperation):
                fileno = -1  # sys.stdout is StringIO or fake
            return not os.isatty(fileno)

        if opts.get('force_color', False):
            opts['color'] = True
        elif opts.get('no_color', False) or is_pipe() or salt.utils.platform.is_windows():
            opts['color'] = False
        else:
            opts['color'] = True
    else:
        if opts.get('force_color', False):
            opts['color'] = True
        elif opts.get('no_color', False) or salt.utils.platform.is_windows():
            opts['color'] = False
        else:
            pass

    outputters = salt.loader.outputters(opts)
    if out not in outputters:
        # Since the grains outputter was removed we don't need to fire this
        # error when old minions are asking for it
        if out != 'grains':
            log.error(
                'Invalid outputter %s specified, fall back to nested',
                out,
            )
        return outputters['nested']
    return outputters[out]


def out_format(data, out, opts=None, **kwargs):
    '''
    Return the formatted outputter string for the passed data
    '''
    return try_printout(data, out, opts, **kwargs)


def string_format(data, out, opts=None, **kwargs):
    '''
    Return the formatted outputter string, removing the ANSI escape sequences.
    '''
    raw_output = try_printout(data, out, opts, **kwargs)
    ansi_escape = re.compile(r'\x1b[^m]*m')
    return ansi_escape.sub('', raw_output)


def html_format(data, out, opts=None, **kwargs):
    '''
    Return the formatted string as HTML.
    '''
    ansi_escaped_string = string_format(data, out, opts, **kwargs)
    return ansi_escaped_string.replace(' ', '&nbsp;').replace('\n', '<br />')


def strip_esc_sequence(txt):
    '''
    Replace ESC (ASCII 27/Oct 33) to prevent unsafe strings
    from writing their own terminal manipulation commands
    '''
    if isinstance(txt, six.string_types):
        try:
            return txt.replace('\033', '?')
        except UnicodeDecodeError:
            return txt.replace(str('\033'), str('?'))  # future lint: disable=blacklisted-function
    else:
        return txt
