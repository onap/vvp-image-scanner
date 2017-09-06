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
from flask import (
    Flask, request, redirect, send_from_directory, url_for, render_template,
    )
import re
from . import STATUSFILE, LOGS_PATH
from .tasks import celery_app, request_scan

app = Flask(__name__)
# app.config['TRAP_HTTP_EXCEPTIONS'] = True
# app.config['TRAP_BAD_REQUEST_ERRORS'] = True
celery_inspect = celery_app.control.inspect()


@app.route('/imagescanner')
def show_form():
    # TODO: consider storing worker status/state directly in redis
    try:
        with STATUSFILE.open() as fp:
            status = fp.read()
    except FileNotFoundError:
        status = '(No status information available)'

    return render_template(
        'form.html',
        channel=os.getenv('DEFAULT_SLACK_CHANNEL', ''),
        status=status,
        active=(job
            for worker, jobs in (celery_inspect.active() or {}).items()
            for job in jobs),
        reserved=(job
            for worker, jobs in (celery_inspect.reserved() or {}).items()
            for job in jobs),
        )


@app.route('/imagescanner', methods=['POST'])
def process_form():
    # TODO: better sanitize form input
    request_scan.delay(
        request.form['repo'],
        request.form['path'],
        re.split(r'[\s,]+', request.form['notify']),
        )
    return redirect(url_for('show_form'))


@app.route('/imagescanner/result/<string(length=64):hashval>')
def show_result_log(hashval):
    if '/' in hashval:
        raise ValueError("Invalid character in hashval")
    return send_from_directory(
        LOGS_PATH,
        "SecurityValidation-%s.txt" % hashval,
        )
