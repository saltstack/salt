# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import logging
import textwrap

# Import salt libs
import salt.utils.files

# Import 3rd-party libs
import pytest

log = logging.getLogger(__name__)


def test_issue_1896_file_append_source(states, grains):
    '''
    Verify that we can append a file's contents
    '''
    firstif_contents = textwrap.dedent('''\
    # set variable identifying the chroot you work in (used in the prompt below)
    if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then
        debian_chroot=$(cat /etc/debian_chroot)
    fi

    ''')
    secondif_contents = textwrap.dedent('''\
    # enable bash completion in interactive shells
    if [ -f /etc/bash_completion ] && ! shopt -oq posix; then
        . /etc/bash_completion
    fi
    ''')
    with pytest.helpers.temp_file('test.append', '') as testfile, \
            pytest.helpers.temp_state_file('firstif', firstif_contents), \
            pytest.helpers.temp_state_file('secondif', secondif_contents):

        ret = states.file.append(name=testfile, source='salt://firstif')
        assert ret.result is True

        ret = states.file.append(name=testfile, source='salt://secondif')
        assert ret.result is True

        with salt.utils.files.fopen(testfile, 'r') as fp_:
            testfile_contents = salt.utils.stringutils.to_unicode(fp_.read())

        contents = textwrap.dedent(firstif_contents + secondif_contents)
        if grains.get('os_family', '') == 'Windows':
            contents = os.linesep.join(contents.splitlines())

        assert testfile_contents == contents

        # If we run it again, nothing should change, even if the order is inverted
        ret = states.file.append(name=testfile, source='salt://secondif')
        assert ret.result is True

        ret = states.file.append(name=testfile, source='salt://firstif')
        assert ret.result is True

        with salt.utils.files.fopen(testfile, 'r') as fp_:
            testfile_contents = salt.utils.stringutils.to_unicode(fp_.read())

        assert testfile_contents == contents
