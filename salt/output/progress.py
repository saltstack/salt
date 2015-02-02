# -*- coding: utf-8 -*-
'''
Display return data as a progress bar
'''

# Import Python libs
from __future__ import absolute_import

# Import 3rd-party libs
try:
    import progressbar
    HAS_PROGRESSBAR = True
except ImportError:
    HAS_PROGRESSBAR = False


def __virtual__():
    return True if HAS_PROGRESSBAR else False


def output(ret, bar):
    '''
    Update the progress bar
    '''
    if 'return_count' in ret:
        bar.update(ret['return_count'])
    return ''


def progress_iter(progress):
    '''
    Initialize and return a progress bar iter
    '''
    widgets = [progressbar.Percentage(), ' ', progressbar.Bar(), ' ', progressbar.Timer(), ' Returns: [', progressbar.Counter(), '/{0}]'.format(progress['minion_count'])]
    bar = progressbar.ProgressBar(widgets=widgets, maxval=progress['minion_count'])
    bar.start()
    return bar
