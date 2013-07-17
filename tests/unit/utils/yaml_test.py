# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

from salt.utils.yamlutil import anchored_dump
import yaml

class YAMLTestCase(TestCase):
    def test_anchored(self):
        top_anchor = "TEST"

        main_basic = "\nbar: baz\n"
        main_aliased = "\nbar: *{}__foo\n".format(top_anchor)

        include = {
            "foo": {
                "bar": "qux"
            }
        }
        include_basic = yaml.dump(include)
        include_anchored = anchored_dump(include, top_anchor=top_anchor)
        self.assertNotEqual(include_basic, include_anchored)

        #
        # test main_basic + include_basic
        #

        result = yaml.load(main_basic + include_basic)
        self.assertEquals(result, {'foo': {'bar': 'qux'}, 'bar': 'baz'})

        result = yaml.load(include_basic + main_basic)
        self.assertEquals(result, {'foo': {'bar': 'qux'}, 'bar': 'baz'})

        #
        # test main_basic + include_anchored
        #

        result = yaml.load(main_basic + include_anchored)
        self.assertEquals(result, {'foo': {'bar': 'qux'}, 'bar': 'baz'})

        result = yaml.load(include_anchored + main_basic)
        self.assertEquals(result, {'foo': {'bar': 'qux'}, 'bar': 'baz'})

        #
        # test main_aliased + include_basic
        #

        with self.assertRaises(yaml.composer.ComposerError):
            result = yaml.load(main_aliased + include_basic)

        with self.assertRaises(yaml.composer.ComposerError):
            result = yaml.load(main_aliased + include_basic)

        #
        # test main_aliased + include_anchored
        #

        result = yaml.load(include_anchored + main_aliased)
        self.assertEquals(result, {'bar': {'bar': 'qux'}, 'foo': {'bar': 'qux'}})

        with self.assertRaises(yaml.composer.ComposerError):
            result = yaml.load(main_aliased + include_anchored)

    def test_anchored_clash(self):
        top_anchor1 = "TEST"
        top_anchor2 = "YRDY"
        document = {
            "foo": {
                "bar": "qux"
            }
        }
        anchor_1 = anchored_dump(document, top_anchor=top_anchor1)
        anchor_2 = anchored_dump(document, top_anchor=top_anchor2)
        result = yaml.load(anchor_1 + anchor_2)
        self.assertEquals(result, {'foo': {'bar': 'qux'}})

        # duplicates anchors
        with self.assertRaises(yaml.composer.ComposerError):
            result = yaml.load(anchor_1 + anchor_1)

        # duplicates anchors
        with self.assertRaises(yaml.composer.ComposerError):
            result = yaml.load(anchor_2 + anchor_2)

        anchor_3 = anchored_dump(document, top_anchor=top_anchor1, include_document=True)
        result = yaml.load(anchor_3)

        # mix of nested and extended flow styles
        with self.assertRaises(yaml.scanner.ScannerError):
            result = yaml.load(anchor_1 + anchor_3)

        # mix of nested and extended flow styles
        with self.assertRaises(yaml.parser.ParserError):
            result = yaml.load(anchor_3 + anchor_1)

        # mix of 2 nested flow styles
        with self.assertRaises(yaml.parser.ParserError):
            result = yaml.load(anchor_3 + anchor_3)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(YAMLTestCase, needs_daemon=False)
