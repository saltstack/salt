# -*- coding: utf-8 -*-
import progressbar


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
