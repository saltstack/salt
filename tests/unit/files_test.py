# -*- coding: utf-8 -*-
'''
    tests.unit.file_test
    ~~~~~~~~~~~~~~~~~~~~
'''
import copy
import os
import shutil
import tempfile
import salt.utils
from salt.utils import files as util_files
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')


class FilesTestCase(TestCase):

    STRUCTURE = {
        'foo': {
            'foofile.txt': 'fooSTRUCTURE'
        },
        'bar': {
            'barfile.txt': 'barSTRUCTURE'
        }
    }

    def _create_temp_structure(self, temp_directory, structure):
        for folder, files in structure.items():
            current_directory = os.path.join(temp_directory, folder)
            os.makedirs(current_directory)
            for name, content in files.items():
                path = os.path.join(temp_directory, folder, name)
                with salt.utils.fopen(path, 'w+') as fh:
                    fh.write(content)

    def _validate_folder_structure_and_contents(self, target_directory,
                                                desired_structure):
        for folder, files in desired_structure.items():
            for name, content in files.items():
                path = os.path.join(target_directory, folder, name)
                with salt.utils.fopen(path) as fh:
                    assert fh.read().strip() == content

    def setUp(self):
        super(FilesTestCase, self).setUp()
        self.temp_dir = tempfile.mkdtemp()
        self._create_temp_structure(self.temp_dir,
                                    self.STRUCTURE)

    def tearDown(self):
        super(FilesTestCase, self).tearDown()
        shutil.rmtree(self.temp_dir)

    def test_recursive_copy(self):
        test_target_directory = tempfile.mkdtemp()
        TARGET_STRUCTURE = {
            'foo': {
                'foo.txt': 'fooTARGET_STRUCTURE'
            },
            'baz': {
                'baz.txt': 'bazTARGET_STRUCTURE'
            }
        }
        self._create_temp_structure(test_target_directory, TARGET_STRUCTURE)
        try:
            util_files.recursive_copy(self.temp_dir, test_target_directory)
            DESIRED_STRUCTURE = copy.copy(TARGET_STRUCTURE)
            DESIRED_STRUCTURE.update(self.STRUCTURE)
            self._validate_folder_structure_and_contents(
                test_target_directory,
                DESIRED_STRUCTURE
            )
        finally:
            shutil.rmtree(test_target_directory)
