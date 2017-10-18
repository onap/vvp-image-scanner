# ============LICENSE_START=======================================================
# org.onap.vvp/image-scanner
# ===================================================================
# Copyright © 2017 AT&T Intellectual Property. All rights reserved.
# ===================================================================
#
# Unless otherwise specified, all software contained herein is licensed
# under the Apache License, Version 2.0 (the “License”);
# you may not use this software except in compliance with the License.
# You may obtain a copy of the License at
#
#             http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
#
#
# Unless otherwise specified, all documentation contained herein is licensed
# under the Creative Commons License, Attribution 4.0 Intl. (the “License”);
# you may not use this documentation except in compliance with the License.
# You may obtain a copy of the License at
#
#             https://creativecommons.org/licenses/by/4.0/
#
# Unless required by applicable law or agreed to in writing, documentation
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# ============LICENSE_END============================================
#
# ECOMP is a trademark and service mark of AT&T Intellectual Property.
#

"""A single-dispatch mechanism using regular-expression matching.

This API intentionally apes that of functools.singledispatch, for consistency.
Where functools.singledispatch dispatches on the type of the first argument,
regexdispatch dispatches on regex matching against the first argument.

Match a given argument against a list of regular expressions; call the function
corresponding to the first one that matches. If none match, call the method
decorated with @regexdispatch.

    @regexdispatch
    def foo(bar, baz):
        '''A function that will dispatch among a list of functions.'''
        print("None of the regexes matched against bar")

    @foo.register(r'[a-z]')
    def _(bar, baz):
        print("bar contains letters")

    @foo.register(r'[0-9]')
    def _(bar, baz):
        print("bar contains numbers")

"""
import re
from functools import update_wrapper


class regexdispatch(object):

    def __init__(self, prototype):
        update_wrapper(self, prototype)
        self.prototype = prototype
        self.registry = []

    def register(self, regex, fn=None):
        def make_handler(fn):
            fn.regex = re.compile(regex)
            self.registry.append(fn)
            return fn

        if fn:
            return make_handler(fn)
        else:
            return make_handler

    def __call__(self, arg, *args, **kwargs):
        """Dispatch to first handler function whose regex matches arg.

        Pass through any extra provided arguments.
        Pass named groups from handler's regex as keyword arguments.
        Extra provided arguments override named groups from handler's regex.

        """
        for handler in self.registry:
            mo = handler.regex.match(arg)
            if mo is not None:
                return handler(arg, *args, **dict(mo.groupdict(), **kwargs))
        else:
            return self.prototype(arg, *args, **kwargs)
