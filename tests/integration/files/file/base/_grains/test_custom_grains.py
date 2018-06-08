def test(grains):
    if 'os' in grains:
        return {'custom_grain_test': 'itworked'}
    return {'custom_grain_test': 'itdidntwork'}
