'''
Helpful decorators module writing
'''

import logging
from collections import defaultdict
import inspect

class Depends(object):
    '''
    This decorator will check the module when it is loaded and check that the dependancies passed in
        are in the globals of the module. If not, it will cause the function to be unloaded (or replaced)
    '''
    # Dependancy -> list of things that depend on it
    dependancy_dict = defaultdict(set)
    def __init__(self, *dependancies, **kwargs):
        '''
        The decorator is instantiated with a list of dependancies (string of global name)

            an example use of this would be:

            @depends('modulename')
            def test():
                return 'foo'

            OR

            @depends('modulename', fallback_funcion=function)
            def test():
                return 'foo'
        '''
        logging.debug('Depends decorator instantiated with dep list of {0}'.format(dependancies))
        self.depencancies = dependancies
        self.fallback_funcion = kwargs.get('fallback_funcion')

    def __call__(self, function):
        '''
        The decorator is "__call__"d with the function, we take that function and
            determine which module and function name it is to store in the class wide
            depandancy_dict
        '''
        module = inspect.getmodule(inspect.stack()[1][0])
        for dep in self.depencancies:
            self.dependancy_dict[dep].add((module, function, self.fallback_funcion))
        return function

    @classmethod
    def enforce_dependancies(self, functions):
        '''
        This is a class global method to enforce the dependancies that you currently know about

        It will modify the "functions" dict and remove/replace modules that are missing dependancies
        '''
        for dependancy, dependant_set in self.dependancy_dict.iteritems():
            # check if dependancy is loaded
            for module, func, fallback_funcion in dependant_set:
                # check if you have the dependancy
                if dependancy in dir(module):
                    logging.debug('Dependancy ({0}) already loaded inside {1}, skipping'.format(dependancy, module.__name__.split('.')[-1]))
                    continue
                logging.debug('Unloading {0}.{1} because dependancy ({2}) is not imported'.format(module, func, dependancy))
                # if not, unload dependand_set
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

