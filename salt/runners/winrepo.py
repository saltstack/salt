'''
Runner to manage Windows software repo
'''

# Import salt libs
import salt.output


def genrepo():
    '''
    Generate win_repo_cachefile based on sls files in the win_repo
    '''

    result = __opts__['win_repo']
    salt.output.display_output(result, 'pprint', __opts__)
    return result
