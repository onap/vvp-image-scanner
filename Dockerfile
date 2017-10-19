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
FROM alpine

RUN apk add --no-cache \
    clamav \
    clamav-libunrar \
    device-mapper \
    file \
    git \
    multipath-tools \
    openssh-client \
    qemu \
    rsyslog \
    uwsgi-python3 \
    wget \
    ; :

# Bootstrap the database since clamav is running for the first time
RUN freshclam -v

ENV IMAGESCANNER_LOGS_PATH=/var/log/imagescanner \
    IMAGESCANNER_MOUNTPOINT=/mnt/imagescanner

COPY imagescanner /opt/imagescanner
COPY bin/* /usr/local/bin/
RUN mkdir -p $IMAGESCANNER_MOUNTPOINT /run/clamav $IMAGESCANNER_LOGS_PATH; chown clamav /run/clamav
RUN pip3 install \
    /opt/imagescanner \
    celery[redis] \
    flask \
    requests \
    requests-aws \
    ; :
EXPOSE 80