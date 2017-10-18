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
from xml.etree import ElementTree
from celery import Celery
import requests
from . import config
from .in_temp_dir import in_temp_dir
from .regexdispatch import regexdispatch

celery_app = Celery(
    broker='redis://redis',
    backend='redis://redis',
    )

# direct_re will match URLs pointing directly to an image to download, over
# http and https connections, and will capture the hostname and filename in
# named groups. This includes URLs to S3 and RadosGW endpoints.
#
image_re = re.compile(r'.*\.(?:img|iso|qcow2?)(?:\.gz)?$')
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
def request_scan(source, path, recipients=None, jenkins_job_name=None,
                 checklist_uuid=None):
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

    jenkins_job_name:
        The name of the jenkins job that should be built to process the scan
        results.

    checklist_uuid:
        The UUID of the checklist that should be passed to the jenkins job.

    This function assumes the current working directory is a safe workarea for
    retrieving and manipulating images, but is decorated with in_temp_dir which
    changes to a new temporary directory upon invocation.

    """

    # TODO printing to a status file is archaic and messy; let's use the python
    # logging framework or storing status in redis instead.
    with config.STATUSFILE.open('w') as statusfile:

        print(
            "Processing request {source} {path} in {workspace}".format(
                source=source, path=path, workspace=os.getcwd()),
            file=statusfile,
            flush=True)

        for image in retrieve_images(source, path):
            print(
                "- Image file: {}...".format(image),
                file=statusfile, flush=True)
            if not os.path.exists(image):
                raise ValueError("Path not found: {}".format(image))

            print("-- Checksumming...", file=statusfile, flush=True)
            checksum = sha256(image)

            print("-- Scanning...", file=statusfile, flush=True)
            logfile = config.LOGS_PATH / 'SecurityValidation-{}.txt'.format(
                checksum)

            # for partition in image_partitions():
            #     result = scan_partition(partition)
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

            if recipients:
                print(
                    "-- Scheduling notification (exit code: {})..."
                    .format(result.returncode), file=statusfile, flush=True)

                slack_notify.delay(
                    status="Success" if result.returncode == 0 else "Failure",
                    source=source,
                    filename=image,
                    checksum=checksum,
                    recipients=recipients,
                    )

            elif checklist_uuid and jenkins_job_name:
                print(
                    "-- Triggering Jenkins job {} for checklist {}"
                    .format(jenkins_job_name, checklist_uuid), file=statusfile,
                    flush=True)

                jenkins_notify.delay(
                    jenkins_job_name,
                    status=result.returncode,
                    checksum=checksum,
                    checklist_uuid=checklist_uuid,
                    )

            else:
                print(
                    "-- Skipping notification (exit code was: {})."
                    .format(result.returncode), file=statusfile, flush=True)

            print("-- Done.", file=statusfile, flush=True)

        print("- All images processed.", file=statusfile, flush=True)


@regexdispatch
def retrieve_images(source, path):
    """Generate the filenames of one or multiple disk images as they are
    retrieved from _source_.

    Source may be one of several types of source, so we dispatch to an
    appropriate function to deal with it:

    - a git url to a repo containing disk images
    - a normal https url directly to a single disk image
    - an https url directly to a single disk image in a radosgw (s3) bucket
    - an https url to a radosgw (s3) bucket containing disk images

    See the docstring for request_scan for documentation of the source and path
    arguments.

    This function assumes the current working directory is a safe workarea for
    retrieving and manipulating images.

    """
    raise ValueError("Unknown source type %s" % source)


@retrieve_images.register(r'.*\.git$')
def _ri_git(source, path, **kwargs):
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


# FIXME this regex won't properly detect URLs with query-strings.
@retrieve_images.register(r'''(?x)  # this is a "verbose" regex
    https?://                   # match an http or https url
    (?P<hostname>               # capture the hostname:
        [^/:]*                  #   anything up to the first / or :
    )
    .*                          # any number of path components
    /(?P<filename>              # capture the filename after the last /
        [^/]*                   #   anything not a /
        \.(?:img|iso|qcow2?)    #   with one of these three extensions
        (?:\.gz)?               #   optionally also compressed
    )$''')
def _ri_direct(source, path=None, hostname=None, filename=None, **kwargs):
    auth = config.AUTHS.get(hostname)
    with open(filename, 'wb') as fd:
        r = requests.get(source, stream=True, auth=auth)
        for chunk in r.iter_content(chunk_size=4096):
            fd.write(chunk)
    yield filename


@retrieve_images.register(r'''(?x)  # this is a "verbose" regex
    https?://                   # match an http or https url
    (?P<hostname>               # capture the hostname:
        [^/:]*                  #   anything up to the first / or :
    )
    .*                          # any number of path components
    /$                          # ending with a slash
    ''')
def _ri_bucket(source, path=None, hostname=None, filename=None, **kwargs):
    """We assume that an HTTP(s) URL ending in / is a radosgw bucket."""
    auth = config.AUTHS.get(hostname)
    # We could request ?format=json but the output is malformed; all but one
    # filename is truncated.
    response = requests.get(source, {'format': 'xml'}, auth=auth)
    keys = ElementTree.fromstring(response.text).iter(
        '{http://s3.amazonaws.com/doc/2006-03-01/}Key')
    filenames = [x.text for x in keys]
    for filename in filenames:
        if image_re.match(filename):
            yield from retrieve_images(source + filename)


@celery_app.task(ignore_result=True)
def slack_notify(status, source, filename, checksum, recipients):
    if not SLACK_TOKEN:
        print("No Slack token defined; skipping notification.")
        return
    if not recipients:
        print("No recipients specified; skipping notification.")
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


@celery_app.task(ignore_result=True)
def jenkins_notify(name, status, checksum, checklist_uuid):
    # The frontend does not need the jenkins library, so we perform the import
    # it from within the worker task.
    from jenkins import Jenkins
    server = Jenkins(**config.JENKINS)
    logurl = "http://{}/imagescanner/result/{}".format(DOMAIN, checksum)
    server.build_job(name, {
        "checklist_uuid": checklist_uuid,
        "status": status,
        "logurl": logurl,
        })
