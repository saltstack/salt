==========================
Running States in Parallel
==========================

Introduced in Salt version ``2017.7.0`` it is now possible to run select states
in parallel. This is accomplished very easily by adding the ``parallel: True``
option to your state declaration:

.. code-block:: yaml

    nginx:
      service.running:
        - parallel: True

Now ``nginx`` will be started in a separate process from the normal state run
and will therefore not block additional states.

Parallel States and Requisites
==============================

Parallel States still honor requisites. If a given state requires another state
that has been run in parallel then the state runtime will wait for the required
state to finish.

Given this example:

.. code-block:: yaml

    sleep 10:
      cmd.run:
        - parallel: True

    nginx:
      service.running:
        - parallel: True
        - require:
          - cmd: sleep 10

    sleep 5:
      cmd.run:
        - parallel: True

The ``sleep 10`` will be started first, then the state system will block on
starting nginx until the ``sleep 10`` completes. Once nginx has been ensured to
be running then the ``sleep 5`` will start.

This means that the order of evaluation of Salt States and requisites are
still honored, and given that in the above case, ``parallel: True`` does not
actually speed things up.

To run the above state much faster make sure that the ``sleep 5`` is evaluated
before the ``nginx`` state

.. code-block:: yaml

    sleep 10:
      cmd.run:
        - parallel: True

    sleep 5:
      cmd.run:
        - parallel: True

    nginx:
      service.running:
        - parallel: True
        - require:
          - cmd: sleep 10

Now both of the sleep calls will be started in parallel and ``nginx`` will still
wait for the state it requires, but while it waits the ``sleep 5`` state will
also complete.

Things to be Careful of
=======================

Parallel States do not prevent you from creating parallel conflicts on your
system. This means that if you start multiple package installs using Salt then
the package manager will block or fail. If you attempt to manage the same file
with multiple states in parallel then the result can produce an unexpected
file.

Make sure that the states you choose to run in parallel do not conflict, or
else, like in any parallel programming environment, the outcome may not be
what you expect. Doing things like just making all states run in parallel
will almost certainly result in unexpected behavior.

With that said, running states in parallel should be safe the vast majority
of the time and the most likely culprit for unexpected behavior is running
multiple package installs in parallel.
