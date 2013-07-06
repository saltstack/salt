'''
Helpful decorators module writing
'''

import logging
from collections import defaultdict
import inspect

class Depends(object):
    '''
    This decorator will check the module when it is loaded and check that the dependencies passed in
        are in the globals of the module. If not, it will cause the function to be unloaded (or replaced)
    '''
    # Dependency -> list of things that depend on it
    dependency_dict = defaultdict(set)
    def __init__(self, *dependencies, **kwargs):
        '''
        The decorator is instantiated with a list of dependencies (string of global name)

            an example use of this would be:

            @depends('modulename')
            def test():
                return 'foo'

            OR

            @depends('modulename', fallback_funcion=function)
            def test():
                return 'foo'
        '''
        logging.debug('Depends decorator instantiated with dep list of {0}'.format(dependencies))
        self.depencancies = dependencies
        self.fallback_funcion = kwargs.get('fallback_funcion')

    def __call__(self, function):
        '''
        The decorator is "__call__"d with the function, we take that function and
            determine which module and function name it is to store in the class wide
            depandancy_dict
        '''
        module = inspect.getmodule(inspect.stack()[1][0])
        for dep in self.depencancies:
            self.dependency_dict[dep].add((module, function, self.fallback_funcion))
        return function

    @classmethod
    def enforce_dependencies(cls, functions):
        '''
        This is a class global method to enforce the dependencies that you currently know about

        It will modify the "functions" dict and remove/replace modules that are missing dependencies
        '''
        for dependency, dependent_set in cls.dependency_dict.iteritems():
            # check if dependency is loaded
            for module, func, fallback_funcion in dependent_set:
                # check if you have the dependency
                if dependency in dir(module):
                    logging.debug('Dependency ({0}) already loaded inside {1}, skipping'.format(dependency, module.__name__.split('.')[-1]))
                    continue
                logging.debug('Unloading {0}.{1} because dependency ({2}) is not imported'.format(module, func, dependency))
                # if not, unload dependent_set
                mod_key = '{0}.{1}'.format(module.__name__.split('.')[-1],
                                           func.__name__)

                # if we don't have this module loaded, skip it!
                if mod_key not in functions:
                    continue

                try:
                    if fallback_funcion is not None:
                        functions[mod_key] = fallback_funcion
                    else:
                        del(functions[mod_key])
                except AttributeError:
                    # we already did???
                    logging.debug('{0} already removed, skipping'.format(mod_key))
                    continue


class depends(Depends):
    '''
    Wrapper of Depends for capitalization
    '''
    pass

