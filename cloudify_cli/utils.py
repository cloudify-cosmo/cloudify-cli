########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
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
import tarfile
import zipfile
import tempfile
from shutil import copy
from urlparse import urlparse
from contextlib import closing, contextmanager
from backports.shutil_get_terminal_size import get_terminal_size

import requests

from .logger import get_logger
from .exceptions import CloudifyCliError
from .constants import SUPPORTED_ARCHIVE_TYPES

from cloudify_rest_client.constants import VisibilityState
from cloudify_rest_client.exceptions import CloudifyClientError


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
        'Unsupported archive type provided or archive is not valid: {0}.'
        ' Supported archive types are: {1}'
        .format(source, SUPPORTED_ARCHIVE_TYPES)
    )


def tar(source, destination):
    logger = get_logger()
    logger.debug('Creating tgz archive: {0}...'.format(destination))
    with closing(tarfile.open(destination, 'w:gz')) as tar:
        tar.add(source, arcname=os.path.basename(source))


def untar(archive, destination=None):
    if not destination:
        destination = tempfile.mkdtemp()
    logger = get_logger()
    logger.debug('Extracting tar archive {0} to {1}...'
                 .format(archive, destination))
    with closing(tarfile.open(name=archive)) as tar:
        tar.extractall(path=destination, members=tar.getmembers())
    return destination


def zip_files(files):
    source_folder = tempfile.mkdtemp()
    destination_zip = source_folder + '.zip'
    for path in files:
        copy(path, source_folder)
    zip(source_folder, destination_zip, include_folder=False)
    shutil.rmtree(source_folder)
    return destination_zip


def zip(source, destination, include_folder=True):
    logger = get_logger()

    logger.debug('Creating zip archive: {0}...'.format(destination))
    with closing(zipfile.ZipFile(destination, 'w')) as zip_file:
        for root, _, files in os.walk(source):
            for filename in files:
                file_path = os.path.join(root, filename)
                source_dir = os.path.dirname(source) if include_folder\
                    else source
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


def download_file(url, destination=None, keep_name=False):
    """Download file.

    :param url: Location of the file to download
    :type url: str
    :param destination:
        Location where the file should be saved (autogenerated by default)
    :param keep_name: use the filename from the url as destination filename
    :type destination: str | None
    :returns: Location where the file was saved
    :rtype: str

    """
    CHUNK_SIZE = 1024
    logger = get_logger()

    if not destination:
        if keep_name:
            path = urlparse(url).path
            name = os.path.basename(path)
            destination = os.path.join(tempfile.mkdtemp(), name)
        else:
            fd, destination = tempfile.mkstemp()
            os.close(fd)

    logger.info('Downloading {0} to {1}...'.format(url, destination))

    try:
        response = requests.get(url, stream=True)
    except requests.exceptions.RequestException as ex:
        raise CloudifyCliError(
            'Failed to download {0}. ({1})'.format(url, str(ex)))

    final_url = response.url
    if final_url != url:
        logger.debug('Redirected to {0}'.format(final_url))

    try:
        with open(destination, 'wb') as destination_file:
            for chunk in response.iter_content(CHUNK_SIZE):
                destination_file.write(chunk)
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
    terminal_width = terminal_width or max_bar_length
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
        sys.stdout.write('\r{0} {1} |{2}| {3}%'.format(
            action, file_name, bar, percents))
        if read_bytes >= total_bytes:
            sys.stdout.write('\n')

    return print_progress


@contextmanager
def handle_client_error(status_code, message, logger):
    """Gracefully handle client errors with specific status codes
    """
    try:
        yield
    except CloudifyClientError, e:
        if e.status_code != status_code:
            raise
        logger.info(message)


@contextmanager
def prettify_client_error(status_codes, logger):
    """Prettify client errors with specific status codes

    :param status_codes: List of status codes
    :param logger: Logger for writing the error
    """
    try:
        yield
    except CloudifyClientError, e:
        if e.status_code not in status_codes:
            raise
        logger.info(e.message)


def get_visibility(private_resource,
                   visibility,
                   logger,
                   valid_values=VisibilityState.STATES):
    # These arguments are mutually exclusive so only one can be used
    if private_resource:
        logger.info("The 'private_resource' argument will be deprecated soon, "
                    "please use the 'visibility' argument instead")
        return VisibilityState.PRIVATE

    validate_visibility(visibility, valid_values)
    return visibility


def validate_visibility(visibility, valid_values=VisibilityState.STATES):
    if visibility not in valid_values:
        raise CloudifyCliError(
            "Invalid visibility: `{0}`. Valid visibility's values are: "
            "{1}".format(visibility, valid_values)
        )


def get_local_path(source, destination=None, create_temp=False):
    allowed_schemes = ['http', 'https']
    if urlparse(source).scheme in allowed_schemes:
        downloaded_file = download_file(source, destination, keep_name=True)
        return downloaded_file
    elif os.path.isfile(source):
        if not destination and create_temp:
            source_name = os.path.basename(source)
            destination = os.path.join(tempfile.mkdtemp(), source_name)
        if destination:
            shutil.copy(source, destination)
            return destination
        else:
            return source
    else:
        raise CloudifyCliError(
            'You must provide either a path to a local file, or a remote URL '
            'using one of the allowed schemes: {0}'.format(allowed_schemes))
