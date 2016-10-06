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


class Stub(object):
    '''
    Class that returns stub message on anything.
    This shouldn't be happening to the end-user
    and indicates always a programming error.
    '''

    def __getattr__(self, item):
        def stub(*args, **kwargs):
            return {'error': 'If you got here, your method is missing and you are in nowhere. :)'}

        return stub
