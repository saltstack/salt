# Import salt libs
import integration

from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')


BASE_IMAGE = 'ubuntu'
TEST_IMAGE = 'micahhausler/salt_int_test_container'
MULTIPLE_IMAGES = ['micahhausler/salt_int_test_2:p8080',
                   'micahhausler/salt_int_test_2:p9090']


class DockerModuleTest(integration.ModuleCase):
    '''
    Validate the lxc_docker module
    '''

    def __pull_test_image__(self):
        self.run_function('docker.pull', repository=TEST_IMAGE)

    def __pull_test_image_list__(self):
        for image in MULTIPLE_IMAGES:
            self.run_function('docker.pull', repository=image)

    def __remove_test_image_list__(self):
        for image in MULTIPLE_IMAGES:
            self.run_function('docker.remove_image', image=image)

    def __remove_test_image__(self):
        self.run_function('docker.remove_image', image=TEST_IMAGE)

    def setUp(self):
        super(DockerModuleTest, self).setUp()
        ret = self.run_function('cmd.has_exec', ['docker'])
        if not ret:
            self.skipTest('docker not installed')
        self.run_function('docker.pull', repository=BASE_IMAGE)

    def tearDown(self):
        self.__remove_test_image__()

    def test_pull_from_index(self):
        '''
        Tests that pulling an image works
        '''
        result = self.run_function('docker.pull', repository=TEST_IMAGE)

        if type(result) is not dict:
            print result
        self.assertTrue(type(result) is dict)
        self.assertTrue('progress' in result.keys())
        self.assertEqual(result['progress'], 'complete')
        self.tearDown()

    def test_pull_non_existant(self):
        '''
        Assert that APIError is handled properly
        '''
        bad_container = 'micahhausler/does_not_exist'

        result = self.run_funciton('docker.pull', repository=bad_container)

        self.assertTrue(type(result) is dict)
        self.assertTrue('error' in result.keys())

    def test_list_images(self):
        '''
        Test that image listing is handled properly
        '''
        self.__pull_test_image__()
        result = self.run_function('docker.images')
        self.assertTrue(type(result) is list)
        self.assertTrue(len(result) >= 2)
        self.assertTrue('error' not in result[0].keys())
        self.tearDown()

    def test_list_images_ids(self):
        '''
        Test that image ids are only returned
        '''
        self.__pull_test_image__()
        result = self.run_function('docker.images', ids_only=True)
        self.assertTrue(type(result) is list)
        self.assertTrue(len(result) > 0)
        self.assertTrue(type(result[0]) is str)
        self.tearDown()

    def tests_run_list_stop_start_restart_kill_container(self):
        '''
        Test that run, list, and stop, start, restart, & kill work
        '''
        self.__pull_test_image_list__
        result = self.run_function('docker.run', image=MULTIPLE_IMAGES[0])

        self.assertTrue(type(result) is str)

        cont_ids = [cont['Id'] for cont in self.run_function('cli.containers')]
        rs = [True for id in cont_ids if id.startswith(result)]
        self.assertTrue(len(rs) > 0)

        result_stop = self.run_function('docker.stop', result)
        self.assertEqual(result, result_stop.strip())

        result_start = self.run_function('docker.start', container=result)
        self.assertEqual(result, result_start.strip())

        result_restart = self.run_function('docker.restart', container=result)
        self.assertEqual(result, result_restart.strip())

        result_kill = self.run_function('docker.kill', container=result)
        self.assertEqual(result, result_kill.strip())

        # Tear down
        self.__remove_test_image_list__()
