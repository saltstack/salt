# -*- coding: utf-8 -*-
'''
Direct call executor module

@author: Dmitry Kuzmenko <dmitry.kuzmenko@dsr-company.com>
'''
from __future__ import absolute_import
from salt.executors import ModuleExecutorBase


def get(*args, **kwargs):
    return DirectCallExecutor(*args, **kwargs)


class DirectCallExecutor(ModuleExecutorBase):
    '''
    Directly calls the given function with arguments
    '''

    def __init__(self, opts, data, func, args, kwargs):
        '''
        Constructor
        '''
        super(DirectCallExecutor, self).__init__()
        self.func, self.args, self.kwargs = func, args, kwargs

    def execute(self):
        return self.func(*self.args, **self.kwargs)
