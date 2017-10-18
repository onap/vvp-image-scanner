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
"""
To configure imagescanner for your environment, create a module named
imagescannerconfig containing overrides for the boilerplate settings listed
here and arrange for it to be accessible from your PYTHONPATH.

"""
import os
from pathlib import Path

# A mapping from host names to Requests Authentication Objects; see
# http://docs.python-requests.org/en/master/user/authentication/
AUTHS = {}
LOGS_PATH = Path(os.getenv('IMAGESCANNER_LOGS_PATH', '.'))
STATUSFILE = LOGS_PATH/'status.txt'
# A dict passed as kwargs to jenkins.Jenkins constructor.
JENKINS = {
    'url': 'http://jenkins:8080',
    'username': '',
    'password': '',
    }

try:
    from imagescannerconfig import * # noqa
except ImportError:
    import warnings
    warnings.warn(
        "Could not import imagescannerconfig; default settings are"
        " probably not what you want.")
