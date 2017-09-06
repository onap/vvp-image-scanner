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
import re
import hashlib
import datetime
from subprocess import run
from celery import Celery
import requests
from . import STATUSFILE, LOGS_PATH
from .in_temp_dir import in_temp_dir


celery_app = Celery(
    broker='redis://redis',
    backend='redis://redis',
    )
repo_re = re.compile(r'.*\.git$')
direct_re = re.compile(r'http.*\.(?:img|iso|qcow2)(?:\.gz)?$')
image_re = re.compile(r'.*\.(?:img|iso|qcow2)(?:\.gz)?$')
SLACK_TOKEN = os.getenv('SLACK_TOKEN')
DOMAIN = os.getenv('DOMAIN')


def sha256(path):
    """Return the SHA256 checksum of the file at path"""
    h = hashlib.new('sha256')
    with open(path, 'rb') as fd:
        for chunk in iter((lambda: fd.read(4096)), b''):
            h.update(chunk)
    return h.hexdigest()


@celery_app.task(queue='scans', ignore_result=True)
@in_temp_dir()
def request_scan(source, path, recipients):
    """Retrieve and scan all partitions of (an) image(s), and notify of the
    results.

    source:
        A git URL referencing a repository containing one or more images, or an
        HTTP(S) URL referencing a single image.

    path:
        If source is a git url, this specifies a path within that repo to an
        image. If omitted, all images found in the repo will be scanned.
        If source is an http url, this is ignored.

    recipients:
        A list of places to deliver a notification when the image scan is
        complete. Currently, this may include Slack usernames and Slack
        channels.

    This function assumes the current working directory is a safe workarea for
    retrieving and manipulating images, but is decorated with in_temp_dir which
    changes to a new temporary directory upon invocation.

    """

    # TODO printing to a status file is archaic and messy; let's use the python
    # logging framework or storing status in redis instead.
    with STATUSFILE.open('w') as statusfile:

        print(
            "Processing request {source} {path} in {workspace}".format(
                source=source, path=path, workspace=os.getcwd()),
            file=statusfile,
            flush=True)

        for image in retrieve_images(source, path):
            print("- Image file: {}...".format(image),
                file=statusfile, flush=True)
            if not os.path.exists(image):
                raise ValueError("Path not found: {}".format(image))

            print("-- Checksumming...", file=statusfile, flush=True)
            checksum = sha256(image)

            print("-- Scanning...",
                file=statusfile, flush=True)
            logfile = LOGS_PATH / 'SecurityValidation-{}.txt'.format(checksum)

            #for partition in image_partitions():
            #    result = scan_partition(partition)
            with open(logfile, 'w') as fd:
                print(datetime.datetime.utcnow().ctime(), "UTC", file=fd)
                print("Launching image scan for {} from {} {}".format(
                    image, source, path), file=fd)
                print("SHA256 checksum:", checksum, file=fd, flush=True)
                result = run(
                    ['/usr/local/bin/imagescanner-image', image],
                    stdout=fd,
                    stderr=fd,
                    )

            print("-- Scheduling notification (exit code:{})...".format(result.returncode),
                file=statusfile, flush=True)

            slack_notify.delay(
                status="Success" if result.returncode == 0 else "Failure",
                source=source,
                filename=image,
                checksum=checksum,
                recipients=recipients,
                )

            print("-- Done.", file=statusfile, flush=True)

        print("- All images processed.", file=statusfile, flush=True)

def retrieve_images(source, path):
    """Generate the filenames of one or multiple disk images as they are
    retrieved from _source_.

    See the docstring for request_scan for documentation of the source and path
    arguments.

    This function assumes the current working directory is a safe workarea for
    retrieving and manipulating images.

    """
    if repo_re.match(source):
        return retrieve_images_git(source, path)
    elif direct_re.match(source):
        return retrieve_image_direct(source)
    else:
        raise ValueError("Unknown source format {}".format(source))


def retrieve_images_git(source, path):
    run(['/usr/bin/git', 'clone',
         '--depth', '1',
         '--single-branch',
         '--recursive',
         source,
         'repo/'],
        env={"GIT_SSH_COMMAND": " ".join([
             "ssh",
             "-i /root/.ssh/id_ed25519",
             "-o StrictHostKeyChecking=no"])},
        check=True,
        )

    if path:
        yield os.path.join("repo", path)
        return

    for root, dirs, files in os.walk('repo'):
        for name in files:
            if image_re.match(name):
                yield os.path.join(root, name)


def retrieve_image_direct(source):
    filename = re.search(r'[^/]*$', source).group(0)
    with open(filename, 'wb') as fd:
        r = requests.get(source, stream=True)
        for chunk in r.iter_content(chunk_size=4096):
            fd.write(chunk)
    yield filename


# FIXME the slack notification should go into a different queue than the image
# requests so they don't get blocked by the scans.
@celery_app.task(ignore_result=True)
def slack_notify(status, source, filename, checksum, recipients):
    if not SLACK_TOKEN:
        print("No Slack token defined; skipping notification.")
        return

    # TODO replace this handrolled code with a nice slack client library

    link = "http://{}/imagescanner/result/{}".format(DOMAIN, checksum)

    if filename.startswith('repo/'):
        filename = filename[5:]

    payload = {
        "username": "Disk Image Scanning Robot",
        "icon_emoji": ":robot_face:",
        "attachments": [{
            "fallback": "Image scan log: {}".format(link),
            "pretext": "Disk image scan completed",
            "color": "#00ff00" if status.lower() == 'success' else "#ff0000",
            "title": "Scan {} for {}".format(status, filename),
            "title_link": link,
            "fields": [{"title": t, "value": v, "short": s} for t, v, s in [
                ("Source", source, True),
                ("Filename", filename, True),
                ("Checksum", checksum, False),
                ]]
            }]
        }

    for recipient in recipients:
        requests.post(
            "https://hooks.slack.com/services/%s" % SLACK_TOKEN,
            json=dict(payload, channel=recipient),
            )
