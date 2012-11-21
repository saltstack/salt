'''
Runner frontend to search system
'''

# Import salt libs
import salt.search
import salt.output

def query(term):
    '''
    Query the search system
    '''
    search = salt.search.Search(__opts__)
    result = search.query(term)
    salt.output.display_output(result, 'pprint', __opts__)
    return result
