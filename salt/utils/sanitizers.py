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
from __future__ import absolute_import
import re
import os.path

# Import Salt libs
from salt.ext.six import text_type as text
from salt.exceptions import CommandExecutionError


class InputSanitizer(object):
    @staticmethod
    def trim(value):
        '''
        Raise an exception if value is empty. Otherwise strip it down.
        :param value:
        :return:
        '''
        value = (value or '').strip()
        if not value:
            raise CommandExecutionError("Empty value during sanitation")

        return text(value)

    @staticmethod
    def filename(value):
        '''
        Remove everything that would affect paths in the filename

        :param value:
        :return:
        '''
        return re.sub('[^a-zA-Z0-9.-_ ]', '', os.path.basename(InputSanitizer.trim(value)))

    @staticmethod
    def hostname(value):
        '''
        Clean value for RFC1123.

        :param value:
        :return:
        '''
        return re.sub(r'[^a-zA-Z0-9.-]', '', InputSanitizer.trim(value)).strip('.')

    id = hostname


clean = InputSanitizer()
