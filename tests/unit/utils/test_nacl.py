# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import

import os

# Import Salt libs
import salt.modules.config as config
import salt.utils.files
from tests.support.helpers import with_tempfile
from tests.support.mixins import LoaderModuleMockMixin

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf

try:
    import libnacl.secret  # pylint: disable=unused-import
    import libnacl.sealed  # pylint: disable=unused-import
    import salt.utils.nacl as nacl

    HAS_LIBNACL = True
except (ImportError, OSError, AttributeError):
    HAS_LIBNACL = False


@skipIf(not HAS_LIBNACL, "skipping test_nacl, libnacl is unavailable")
class NaclUtilsTests(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {
            nacl: {"__salt__": {"config.get": config.get}},
            config: {"__opts__": {}},
        }

    def setUp(self):
        self.key = "C16NxgBhw8cqbhvPCDAn2pirwW1A1WEVLUexCsoUD2Y="
        self.pub = "+XWFfZXnfItS++a4gQf8Adu1aUlTgHWyTfsglbTdXyg="

    def test_keygen(self):
        """
        test nacl.keygen function
        """
        ret = nacl.keygen()
        assert all(key in ret for key in ret.keys())

    @with_tempfile()
    def test_keygen_sk_file(self, fpath):
        """
        test nacl.keygen function
        with sk_file set
        """
        with salt.utils.files.fopen(fpath, "w") as wfh:
            wfh.write(self.key)
        # test sk_file
        ret = nacl.keygen(sk_file=fpath)
        assert "saved pk_file: {}.pub".format(fpath) == ret

    @with_tempfile()
    def test_keygen_keyfile(self, fpath):
        """
        test nacl.keygen function
        with keyfile set
        """
        with salt.utils.files.fopen(fpath, "w") as wfh:
            wfh.write(self.key)

        ret = nacl.keygen(keyfile=fpath)
        assert "saved pk_file: {}.pub".format(fpath) == ret

    @with_tempfile()
    def test_enc_keyfile(self, fpath):
        """
        test nacl.enc function
        with keyfile and pk_file set
        """
        with salt.utils.files.fopen(fpath, "w") as wfh:
            wfh.write(self.key)
        with salt.utils.files.fopen(fpath + ".pub", "w") as wfh:
            wfh.write(self.pub)

        kwargs = {
            "opts": {"pki_dir": os.path.dirname(fpath)},
            "keyfile": fpath,
            "pk_file": fpath + ".pub",
        }
        ret = nacl.enc("blah", **kwargs)
        assert isinstance(ret, bytes)

    @with_tempfile()
    def test_enc_sk_file(self, fpath):
        """
        test nacl.enc function
        with sk_file and pk_file set
        """
        with salt.utils.files.fopen(fpath, "w") as wfh:
            wfh.write(self.key)
        with salt.utils.files.fopen(fpath + ".pub", "w") as wfh:
            wfh.write(self.pub)

        kwargs = {
            "opts": {"pki_dir": os.path.dirname(fpath)},
            "sk_file": fpath,
            "pk_file": fpath + ".pub",
        }
        ret = nacl.enc("blah", **kwargs)
        assert isinstance(ret, bytes)

    @with_tempfile()
    def test_dec_keyfile(self, fpath):
        """
        test nacl.dec function
        with keyfile and pk_file set
        """
        with salt.utils.files.fopen(fpath, "w") as wfh:
            wfh.write(self.key)
        with salt.utils.files.fopen(fpath + ".pub", "w") as wfh:
            wfh.write(self.pub)

        kwargs = {
            "opts": {"pki_dir": os.path.dirname(fpath)},
            "keyfile": fpath,
            "pk_file": fpath + ".pub",
        }

        enc_data = nacl.enc("blah", **kwargs)
        ret = nacl.dec(enc_data, **kwargs)
        assert isinstance(ret, bytes)
        assert ret == b"blah"

    @with_tempfile()
    def test_dec_sk_file(self, fpath):
        """
        test nacl.dec function
        with sk_file and pk_file set
        """
        with salt.utils.files.fopen(fpath, "w") as wfh:
            wfh.write(self.key)
        with salt.utils.files.fopen(fpath + ".pub", "w") as wfh:
            wfh.write(self.pub)

        kwargs = {
            "opts": {"pki_dir": os.path.dirname(fpath)},
            "sk_file": fpath,
            "pk_file": fpath + ".pub",
        }

        enc_data = nacl.enc("blah", **kwargs)
        ret = nacl.dec(enc_data, **kwargs)
        assert isinstance(ret, bytes)
        assert ret == b"blah"
