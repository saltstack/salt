# -*- coding: utf-8 -*-
import os
import time
import salt.auth
import salt.config
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase



class AuthTest(TestCase):

    def test_cve_2021_3244(self):
        opts = {
            "extension_modules": "",
            "optimization_order": [0, 1, 2],
            "token_expire": 1,
            "keep_acl_in_token": False,
            "eauth_tokens": "localfs",
            "token_dir": RUNTIME_VARS.TMP,
            "token_expire_user_override": True,
            "external_auth": {
                "auto": {
                    "foo": []
                }
            }
        }
        auth = salt.auth.LoadAuth(opts)
        load = {
            "eauth": "auto",
            "username": "foo",
            "password": "foo",
            "token_expire": -1}
        t_data = auth.mk_token(load)
        assert t_data['expire'] < time.time()
        token_file = os.path.join(RUNTIME_VARS.TMP, t_data['token'])
        assert os.path.exists(token_file)
        t_data = auth.get_tok(t_data['token'])
        assert not os.path.exists(token_file)
        assert t_data == {}
