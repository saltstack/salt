# Copyright (c) 2010 Mitch Garnaat http://garnaat.org/
# Copyright (c) 2010, Eucalyptus Systems, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish, dis-
# tribute, sublicense, and/or sell copies of the Software, and to permit
# persons to whom the Software is furnished to do so, subject to the fol-
# lowing conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABIL-
# ITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT
# SHALL THE AUTHOR BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.


def __virtual__():
    return True


def get_tag_descriptions():
    class TagDescriptions(dict):
        """
        A TagDescriptions is used to collect the tags associated with ELB
        resources.
        See :class:`boto.ec2.elb.LoadBalancer` for more details.
        """

        def __init__(self, connection=None):
            dict.__init__(self)
            self.connection = connection
            self._load_balancer_name = None
            self._tags = None

        def startElement(self, name, attrs, connection):
            if name == "member":
                self.load_balancer_name = None
                self.tags = None
            if name == "Tags":
                self._tags = TagSet()
                return self._tags
            return None

        def endElement(self, name, value, connection):
            if name == "LoadBalancerName":
                self._load_balancer_name = value
            elif name == "member":
                self[self._load_balancer_name] = self._tags

    class TagSet(dict):
        """
        A TagSet is used to collect the tags associated with a particular
        ELB resource.  See :class:`boto.ec2.elb.LoadBalancer` for more
        details.
        """

        def __init__(self, connection=None):
            dict.__init__(self)
            self.connection = connection
            self._current_key = None
            self._current_value = None

        def startElement(self, name, attrs, connection):
            if name == "member":
                self._current_key = None
                self._current_value = None
            return None

        def endElement(self, name, value, connection):
            if name == "Key":
                self._current_key = value
            elif name == "Value":
                self._current_value = value
            elif name == "member":
                self[self._current_key] = self._current_value

    return TagDescriptions
