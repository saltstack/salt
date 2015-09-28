import unittest

if __name__ == '__main__':
    suite = unittest.defaultTestLoader.discover("tests")
    runner = unittest.TextTestRunner()
    runner.run(suite)
