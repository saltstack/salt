# -*- coding: utf-8 -*-
#
# Copyright 2016 SUSE LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import fnmatch
import os.path
import re

import salt.utils.stringutils
from salt.exceptions import CommandExecutionError

# Import Salt libs
from salt.ext import six


class InputSanitizer(object):
    @staticmethod
    def trim(value):
        """
        Raise an exception if value is empty. Otherwise strip it down.
        :param value:
        :return:
        """
        value = (value or "").strip()
        if not value:
            raise CommandExecutionError("Empty value during sanitation")

        return six.text_type(value)

    @staticmethod
    def filename(value):
        """
        Remove everything that would affect paths in the filename

        :param value:
        :return:
        """
        return re.sub(
            "[^a-zA-Z0-9.-_ ]", "", os.path.basename(InputSanitizer.trim(value))
        )

    @staticmethod
    def hostname(value):
        """
        Clean value for RFC1123.

        :param value:
        :return:
        """
        return re.sub(r"[^a-zA-Z0-9.-]", "", InputSanitizer.trim(value)).strip(".")

    id = hostname


clean = InputSanitizer()


def mask_args_value(data, mask):
    """
    Mask a line in the data, which matches "mask".

    This can be used for cases where values in your roster file may contain
    sensitive data such as IP addresses, passwords, user names, etc.

    Note that this works only when ``data`` is a single string (i.e. when the
    data in the roster is formatted as ``key: value`` pairs in YAML syntax).

    :param data: String data, already rendered.
    :param mask: Mask that matches a single line

    :return:
    """
    if not mask:
        return data

    out = []
    for line in data.split(os.linesep):
        if fnmatch.fnmatch(line.strip(), mask) and ":" in line:
            key, value = line.split(":", 1)
            out.append(
                "{}: {}".format(
                    salt.utils.stringutils.to_unicode(key.strip()), "** hidden **"
                )
            )
        else:
            out.append(line)

    return "\n".join(out)
