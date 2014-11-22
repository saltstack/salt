# -*- coding: utf-8 -*-


try:
    import progressbar
    HAS_PROGRESSBAR = True
except ImportError:
    HAS_PROGRESSBAR = False


def __virtual__():
    return True if HAS_PROGRESSBAR else False


def output(ret, bar):
    if 'return_count' in ret:
        bar.update(ret['return_count'])
        return ''
    else:
        return ''


def progress_iter(progress):
    widgets = [progressbar.Percentage(), ' ', progressbar.Bar(), ' ', progressbar.Timer(), ' Returns: ', progressbar.Counter()]
    bar = progressbar.ProgressBar(widgets=widgets, maxval=progress['minion_count'])
    bar.start()
    return bar
