'''
Utility functions for saltcloud
'''

# Import python libs
import os
import sys

def os_script(os_):
    '''
    Return the script as a string for the specific os
    '''
    deploy_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'deploy')
    for fn_ in os.listdir(deploy_path):
        full = os.path.join(deploy_path, fn_)
        if not os.path.isfile(full):
            continue
        if os.lower() == fn_.split('.')[0].lower():
            # found the right script to embed, go for it
            try:
                with open(full, 'r') as fp_:
                    data = fp_.read()
                return data
            except (OSError, IOError):
                continue
