Developing Salt
===============

If you want to help develop Salt there is a great need and your patches are
welcome!

To assist in Salt development, you can help in a number of ways.

Posting patches to the mailing list
-----------------------------------

If you have a patch for Salt, please format it via :command:`git format-patch` and
send it to the Salt users mailing list. This allows the patch to give you the
contributor the credit for your patch, and gives the Salt community an archive
of the patch and a place for discussion.

Setting a Github pull request
-----------------------------

This is probably the preferred method for contributions, simply create a Github
fork, commit your changes to the fork, and then open up a pull request.

Contributions Welcome!
----------------------

The goal here it to make contributions clear, make sure there is a trail for
where the code has come from, but most importantly, to give credit where credit
is due!

The `Open Comparison Contributing Docs`__ has some good suggestions and tips for
those who are looking forward to contribute.

.. __: http://opencomparison.readthedocs.org/en/latest/contributing.html

Getting the tests running
-------------------------

Clone the repository using::

    git clone https://github.com/saltstack/salt

File descriptor limit
~~~~~~~~~~~~~~~~~~~~~

Check your file descriptor limit with::

    ulimit -n

If it is less than 1024, you should increase it with::

    ulimit -n 1024

Requirements
~~~~~~~~~~~~

First you'll want to create a `virtualenv`_. Once you've done that
install the requirements like so::

    pip install -r requirements.txt

You'll also need ``mock`` to run the tests::

    pip install mock

If you are on Python < 2.7 then you'll also need::

    pip install unittest2

.. _`virtualenv`: http://pypi.python.org/pypi/virtualenv

Run them
~~~~~~~~

Finally you use setup.py to run the tests with the following command::

    ./setup.py test
