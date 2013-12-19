# -*- coding: utf-8 -*-
'''
    :codauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import MagicMock, patch, call

from salt import utils

ensure_in_syspath('../../')

LORUM_IPSUM = 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque eget urna a arcu lacinia sagittis. \n' \
              'Sed scelerisque, lacus eget malesuada vestibulum, justo diam facilisis tortor, in sodales dolor \n' \
              'nibh eu urna. Aliquam iaculis massa risus, sed elementum risus accumsan id. Suspendisse mattis, \n'\
              'metus sed lacinia dictum, leo orci dapibus sapien, at porttitor sapien nulla ac velit. \n'\
              'Duis ac cursus leo, non varius metus. Sed laoreet felis magna, vel tempor diam malesuada nec. \n'\
              'Quisque cursus odio tortor. In consequat augue nisl, eget lacinia odio vestibulum eget. \n'\
              'Donec venenatis elementum arcu at rhoncus. Nunc pharetra erat in lacinia convallis. Ut condimentum \n'\
              'eu mauris sit amet convallis. Morbi vulputate vel odio non laoreet. Nullam in suscipit tellus. \n'\
              'Sed quis posuere urna.'


class UtilsTestCase(TestCase):
    def test_get_context(self):
        ret = utils.get_context(LORUM_IPSUM, 3)
        print ret