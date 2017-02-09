# -*- coding: utf-8 -*-
#
# Copyright 2016 SUSE LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import types
from abc import ABCMeta, abstractmethod
import os


class SchemaMethods(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def mod_repo(self, data):
        '''
        Structure returned for mod_repo method call. Should be implemented
        :return:
        '''
        return {}


class SchemaBase(object):
    '''
    Schema base class.
    '''

    def __init__(self, cls, ident):
        # This loads the corresponding unifier to the caller module
        self.unifier = cls.__dict__.get(os.path.basename(ident).split(".")[0].title(), Stub)()

    def __getattr__(self, item):
        '''
        Load only what is really needed at the very moment.

        :param item:
        :return:
        '''
        # When this class is initialized, an unifier is set according to the module name.
        # Example: for modules/zypper.py class is Zypper. For modules/yumpkg is Yumpkg etc.
        # The usage of this class is simple:
        #
        #    foo = Package(__file__)     <-- this sets what module is calling it
        #    return foo.mod_repo(output) <-- this wraps the output to the certain function

        return getattr(self.unifier, item)

    def __call__(self, function):
        '''
        Call as decorator.

        :param args:
        :param kwargs:
        :return:
        '''
        def formatter(*args, **kwargs):
            '''
            Formatter function that wraps the output.

            :param args:
            :param kwargs:
            :return:
            '''
            for k_arg in kwargs.copy().keys():
                if k_arg.startswith('__'):
                    kwargs.pop(k_arg)
            return getattr(self.unifier, function.func_name)(function(*args, **kwargs))

        return formatter


class Stub(object):
    '''
    Class that returns stub message on anything.
    This shouldn't be happening to the end-user
    and indicates always a programming error.
    '''

    def __getattr__(self, item):
        def stub(*args, **kwargs):
            return {'error': 'If you got here, your method is missing and you are in nowhere. :)'}

        return stub


def bypass_decorator(func):
    '''
    Remove a decorators from the function, if any.

    :param func:
    :return:
    '''

    for obj in func.__dict__.values():
        if isinstance(obj, types.FunctionType):
            func = obj

    return func
