#!pydsl

#__pydsl__.set(ordered=True)

state('{0}'.format(__salt__['runtests_helpers.get_salt_temp_dir_for_path']('test-pydev'))).file('touch')
