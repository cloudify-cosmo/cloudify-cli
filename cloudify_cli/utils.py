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
from backports.shutil_get_terminal_size import get_terminal_size

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

    def get_values_per_column(column, row_data):
        if column in row_data:
            if column == 'created_at':
                if row_data[column]:
                    row_data[column] = \
                        row_data[column].replace('T', ' ').replace('Z', ' ')
            return row_data[column]
        else:
            return defaults[column]

    pt = PrettyTable([col for col in cols])

    for d in data:
        values_row = []
        for c in cols:
            values_row.append(get_values_per_column(c, d))
        pt.add_row(values_row)

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
    return tarfile.is_tarfile(source) or zipfile.is_zipfile(source)


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


def zip(source, destination):
    logger = get_logger()

    logger.info('Creating zip archive: {0}...'.format(destination))
    with closing(zipfile.ZipFile(destination, 'w')) as zip_file:
        for root, _, files in os.walk(source):
            for filename in files:
                file_path = os.path.join(root, filename)
                source_dir = os.path.dirname(source)
                zip_file.write(
                    file_path, os.path.relpath(file_path, source_dir))
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
    try:
        f.retrieve(final_url, destination)
    except IOError as ex:
        raise CloudifyCliError(
            'Failed to download {0}. ({1})'.format(url, str(ex)))
    return destination


def generate_progress_handler(file_path, action='', max_bar_length=80):
    """Returns a function that prints a progress bar in the terminal

    :param file_path: The name of the file being transferred
    :param action: Uploading/Downloading
    :param max_bar_length: Maximum allowed length of the bar. Default: 80
    :return: The configured print_progress function
    """
    # We want to limit the maximum line length to 80, but allow for a smaller
    # terminal size. We also include the action string, and some extra chars
    terminal_width = get_terminal_size().columns

    # This takes care of the case where there is no terminal (e.g. unittest)
    terminal_width = terminal_width if terminal_width else max_bar_length
    bar_length = min(max_bar_length, terminal_width) - len(action) - 12

    # Shorten the file name if it's too long
    file_name = os.path.basename(file_path)
    if len(file_name) > (bar_length / 4) + 3:
        file_name = file_name[:bar_length / 4] + '...'

    bar_length -= len(file_name)

    def print_progress(read_bytes, total_bytes):
        """Print upload/download progress on a single line

        Call this function in a loop to create a progress bar in the terminal

        :param read_bytes: Number of bytes already processed
        :param total_bytes: Total number of bytes in the file
        """

        filled_length = min(bar_length, int(round(bar_length * read_bytes /
                                                  float(total_bytes))))
        percents = min(100.00, round(
            100.00 * (read_bytes / float(total_bytes)), 2))
        bar = '#' * filled_length + '-' * (bar_length - filled_length)

        # The \r caret makes sure the cursor moves back to the beginning of
        # the line
        sys.stdout.write('\r{0} {1} |{2}| {3}%'.format(action,
                                                       file_name,
                                                       bar,
                                                       percents))
        if read_bytes >= total_bytes:
            sys.stdout.write('\n')

    return print_progress
