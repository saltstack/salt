============================================
Running the Salt Master as Unprivileged User
============================================

While the default setup runs the Salt Master as the root user, it is generally
wise to run servers as an unprivileged user. In Salt 0.9.10 the management
of the running user was greatly improved, the only change needed is to alter
the option ``user`` in the master configuration file and all salt system
components will be updated to function under the new user when the master
is started.
