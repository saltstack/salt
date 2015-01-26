import salt.utils.event

event = salt.utils.event.MasterEvent('/var/run/salt/master')

for data in event.iter_events(full=True):
    print(data)
