import unittest

from cloud.clouds import virtualbox


class VirtualboxTestCase(unittest.TestCase):
    def setUp(self):
        self.vbox = virtualbox.vb_get_box()

    def assertMachineExists(self, name, msg=None):
        try:
            self.vbox.findMachine(name)
        except Exception as e:
            if msg:
                self.fail(msg)
            else:
                self.fail(e.message)

    def assertMachineDoesNotExist(self, name, msg=None):
        self.assertRaisesRegexp(Exception, "Could not find a registered machine", self.vbox.findMachine, name)


def list_machines():
    vbox = virtualbox.vb_get_box()
    for machine in vbox.getArray(vbox, "Machines"):
        print "Machine '%s' logs in '%s'" % (
            machine.name,
            machine.logFolder
        )
