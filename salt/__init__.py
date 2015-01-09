# -*- coding: utf-8 -*-
'''
Salt package
'''
import warnings
# All salt related deprecation warnings should be shown once each!
warnings.filterwarnings(
        'once',  # Show once
        '',  # No deprecation message match
        DeprecationWarning,  # This filter is for DeprecationWarnings
        r'^(salt|salt\.(.*))$'  # Match module(s) 'salt' and 'salt.<whatever>'
)

# While we are supporting Python2.6, hide nested with-statements warnings
warnings.filterwarnings(
 'ignore',
 'With-statements now directly support multiple context managers',
 DeprecationWarning
)

# Filter the backports package UserWarning about being re-imported
warnings.filterwarnings(
 'ignore',
 '^Module backports was already imported from (.*), but (.*) is being added to sys.path$',
 UserWarning
)
