#!py
import importlib

def run():
    config = {}
    for test_import in [
        'templates', 'platform', 'cli', 'executors', 'config', 'wheel', 'netapi',
        'cache', 'proxy', 'transport', 'metaproxy', 'modules', 'tokens', 'matchers',
        'acl', 'auth', 'log', 'engines', 'client', 'returners', 'runners', 'tops',
        'output', 'daemons', 'thorium', 'renderers', 'states', 'cloud', 'roster',
        'beacons', 'pillar', 'spm', 'utils', 'sdb', 'fileserver', 'defaults',
        'ext', 'queues', 'grains', 'serializers'
    ]:
        try:
            import_name = "salt.{}".format(test_import)
            importlib.import_module(import_name)
            config['test_imports_succeeded'] = {
                'test.succeed_without_changes': [
                    {
                        'name': import_name
                    },
                ],
            }
        except ModuleNotFoundError as err:
            config['test_imports_failed'] = {
                'test.fail_without_changes': [
                    {
                        'name': import_name,
                        'comment': "The imports test failed. The error was: {}".format(err)
                    },
                ],
            }

    for stdlib_import in ["telnetlib"]:
        try:
            importlib.import_module(stdlib_import)
            config['stdlib_imports_succeeded'] = {
                'test.succeed_without_changes': [
                    {
                        'name': stdlib_import
                    },
                ],
            }
        except ModuleNotFoundError as err:
            config['stdlib_imports_failed'] = {
                'test.fail_without_changes': [
                    {
                        'name': stdlib_import,
                        'comment': "The stdlib imports test failed. The error was: {}".format(err)
                    },
                ],
            }
    return config
