# -*- coding: utf-8 -*-

import logging
log = logging.getLogger(__name__)

def test(grains):
    log.info('==== grains %s ===', grains)
    return {'custom_grain_test': 'itworked' if 'os' in grains else 'itdidntwork'}
