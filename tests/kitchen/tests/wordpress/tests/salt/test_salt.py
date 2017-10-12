def test_formula(salt):
    dirs = salt('cp.list_master_dirs')
    assert 'states' in dirs

def test_wordpress_module(salt):
    wordpressdir = salt('grains.get', 'wordpressdir')
    assert salt('wordpress.is_installed', wordpressdir)
