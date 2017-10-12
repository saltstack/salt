def test_formula(salt):
    formulas = {'wordpress',}
    dirs = salt('cp.list_master_dirs')
    assert all([formula in dirs for formula in formulas])

def test_wordpress_module(salt):
    wordpressdir = salt('grains.get', 'wordpressdir')
    assert salt('wordpress.is_installed', path=wordpressdir)
