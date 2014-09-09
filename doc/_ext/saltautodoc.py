# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    saltautodoc.py
    ~~~~~~~~~~~~~~

    Properly handle ``__func_alias__``
'''

# Import Sphinx libs
from sphinx.ext.autodoc import FunctionDocumenter as FunctionDocumenter


class SaltFunctionDocumenter(FunctionDocumenter):
    '''
    Simple override of sphinx.ext.autodoc.FunctionDocumenter to properly render
    salt's aliased function names.
    '''

    def format_name(self):
        '''
        Format the function name
        '''
        if not hasattr(self.module, '__func_alias__'):
            # Resume normal sphinx.ext.autodoc operation
            return super(FunctionDocumenter, self).format_name()

        if not self.objpath:
            # Resume normal sphinx.ext.autodoc operation
            return super(FunctionDocumenter, self).format_name()

        if len(self.objpath) > 1:
            # Resume normal sphinx.ext.autodoc operation
            return super(FunctionDocumenter, self).format_name()

        # Use the salt func aliased name instead of the real name
        return self.module.__func_alias__.get(self.objpath[0], self.objpath[0])


def setup(app):
    app.add_autodocumenter(SaltFunctionDocumenter)
