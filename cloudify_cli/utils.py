########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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
############

import os
import sys
import errno
import string
import random
import shutil
import urllib
import tarfile
import zipfile
import tempfile
from contextlib import closing

from prettytable import PrettyTable

from .logger import get_logger
from .exceptions import CloudifyCliError


def dump_to_file(collection, file_path):
    with open(file_path, 'a') as f:
        f.write(os.linesep.join(collection))
        f.write(os.linesep)


def is_virtual_env():
    return hasattr(sys, 'real_prefix')


# TODO: Really? Remove!
def get_cwd():
    """Allows use to patch the cwd when needed.
    """
    return os.getcwd()


def decode_list(data):
    rv = []
    for item in data:
        if isinstance(item, unicode):
            item = item.encode('utf-8')
        elif isinstance(item, list):
            item = decode_list(item)
        elif isinstance(item, dict):
            item = decode_dict(item)
        rv.append(item)
    return rv


def decode_dict(data):
    rv = {}
    for key, value in data.iteritems():
        if isinstance(key, unicode):
            key = key.encode('utf-8')
        if isinstance(value, unicode):
            value = value.encode('utf-8')
        elif isinstance(value, list):
            value = decode_list(value)
        elif isinstance(value, dict):
            value = decode_dict(value)
        rv[key] = value
    return rv


def table(cols, data, defaults=None):
    """
    Return a new PrettyTable instance representing the list.

    Arguments:

        cols - An iterable of strings that specify what
               are the columns of the table.

               for example: ['id','name']

        data - An iterable of dictionaries, each dictionary must
               have key's corresponding to the cols items.

               for example: [{'id':'123', 'name':'Pete']

        defaults - A dictionary specifying default values for
                   key's that don't exist in the data itself.

                   for example: {'deploymentId':'123'} will set the
                   deploymentId value for all rows to '123'.

    """

    pt = PrettyTable([col for col in cols])

    for d in data:
        pt.add_row(map(lambda c: d[c] if c in d else defaults[c], cols))

    return pt


def remove_if_exists(path):

    try:
        if os.path.isfile(path):
            os.remove(path)
        if os.path.isdir(path):
            shutil.rmtree(path)

    except OSError as e:
        if e.errno != errno.ENOENT:  # errno.ENOENT = no such file or directory
            raise  # re-raise exception if a different error occurred


def generate_random_string(size=6,
                           chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


def generate_suffixed_id(id):
    return '{0}_{1}'.format(id, generate_random_string())


def is_archive(source):
    if tarfile.is_tarfile(source) or zipfile.is_zipfile(source):
        return True
    return False


def extract_archive(source):
    if tarfile.is_tarfile(source):
        return untar(source)
    elif zipfile.is_zipfile(source):
        return unzip(source)
    raise CloudifyCliError(
        'Unsupported archive type provided or archive is not valid.')


def tar(source, destination):
    logger = get_logger()
    logger.debug('Creating tgz archive: {0}...'.format(destination))
    with closing(tarfile.open(destination, 'w:gz')) as tar:
        tar.add(source, arcname=os.path.basename(source))


def untar(archive, destination=None):
    if not destination:
        destination = tempfile.mkdtemp()
    logger = get_logger()
    logger.debug('Extracting tgz {0} to {1}...'.format(archive, destination))
    with closing(tarfile.open(name=archive)) as tar:
        tar.extractall(path=destination, members=tar.getmembers())
    return destination


def unzip(archive, destination=None):
    if not destination:
        destination = tempfile.mkdtemp()
    logger = get_logger()
    logger.debug('Extracting zip {0} to {1}...'.format(archive, destination))
    with closing(zipfile.ZipFile(archive, 'r')) as zip_file:
        zip_file.extractall(destination)
    return destination


def download_file(url, destination=None):
    if not destination:
        fd, destination = tempfile.mkstemp()
        os.close(fd)
    logger = get_logger()
    logger.info('Downloading {0} to {1}...'.format(url, destination))
    final_url = urllib.urlopen(url).geturl()
    if final_url != url:
        logger.debug('Redirected to {0}'.format(final_url))
    f = urllib.URLopener()
    f.retrieve(final_url, destination)
    return destination
