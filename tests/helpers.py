import virtualbox


def list_machines():
    vbox = virtualbox.vb_get_manager()
    for machine in vbox.getArray(vbox, "Machines"):
        print "Machine '%s' logs in '%s'" % (
            machine.name,
            machine.logFolder
        )
