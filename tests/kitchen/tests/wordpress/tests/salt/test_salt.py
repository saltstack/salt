def test_formula(salt):
    '''
    Test that the states are synced to minion
    '''
    dirs = salt('cp.list_master_dirs')
    assert 'states' in dirs

def test_wordpress_module(salt):
    '''
    Test that the wordpress dir grain was set on the minion
    '''
    wordpressdir = salt('grains.get', 'wordpressdir')
    assert salt('wordpress.is_installed', wordpressdir)
