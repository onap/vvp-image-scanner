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
import os
from ..in_temp_dir import in_temp_dir


def test_in_temp_dir():
    with in_temp_dir() as workspace:
        with open("temporary.txt", "w") as junkfile:
            junkfile.write('')
            assert os.path.exists(os.path.join(workspace, junkfile.name))
    assert not os.path.exists(os.path.join(workspace, junkfile.name))


@in_temp_dir()
def make_some_junk():
    with open("temporary.txt", "w") as junkfile:
        junkfile.write('')
    return os.path.join(os.getcwd(), junkfile.name)


def test_method_in_temp_dir():
    junkfile = make_some_junk()
    assert not os.path.exists(junkfile)
