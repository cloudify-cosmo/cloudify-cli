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
import tempfile
from shutil import copy, copytree
from urllib.parse import urlparse

from cloudify_cli import utils
from cloudify_cli.exceptions import CloudifyCliError
from cloudify_cli.constants import DEFAULT_BLUEPRINT_PATH


ICON_FILENAME = 'icon.png'


def get(source, blueprint_filename=DEFAULT_BLUEPRINT_PATH, icon_path=None,
        download=False):
    """Get a source and return a directory containing the blueprint

    The behavior based on then source argument content is:
        - local archive:
            extract it locally and return path blueprint file
        - local yaml file: return the file
        - URL:
            - return it (download=False)
            - download and get blueprint from downloaded file (download=True)
        - github repo:
            - map it to a URL and return it (download=False)
            - download and get blueprint from downloaded file (download=True)

    Supported archive types are: zip, tar, tar.gz and tar.bz2

    :param source: Path/URL/github repo to archive/blueprint file
    :type source: str
    :param blueprint_filename: Path to blueprint (if source is an archive file)
    :type blueprint_filename: str
    :param icon_path: Path to blueprint's icon file
    :type icon_path: str
    :param download: Download blueprint file if source is URL/github repo
    :type download: bool
    :return: Path to file (if archive/blueprint file passsed) or url
    :rtype: str

    """
    # Cope with windows (where paths always have a scheme)
    if urlparse(source).scheme and not os.path.exists(source):
        if download:
            downloaded_file = utils.download_file(source)
            return _get_blueprint_file_from_archive(
                downloaded_file, blueprint_filename, icon_path)
        return source
    elif os.path.isfile(source):
        if utils.is_archive(source):
            return _get_blueprint_file_from_archive(
                source, blueprint_filename, icon_path)
        elif icon_path:
            return _get_blueprint_file_with_icon(source, icon_path)
        else:
            # Maybe check if yaml. If not, verified by dsl parser
            return source
    elif len(source.split('/')) == 2:
        url = _map_to_github_url(source)
        if download:
            downloaded_file = utils.download_file(url)
            return _get_blueprint_file_from_archive(
                downloaded_file, blueprint_filename, icon_path)
        return url
    else:
        raise CloudifyCliError(
            'You must provide either a path to a local file, a remote URL '
            'or a GitHub `organization/repository[:tag/branch]`')


def _get_blueprint_file_from_archive(archive, blueprint_filename, icon_path):
    """Extract archive to temporary location and get path to blueprint file.

    :param archive: Path to archive file
    :type archive: str
    :param blueprint_filename: Path to blueprint file relative to archive
    :type blueprint_filename: str
    :param icon_path: Absolute path to blueprint's icon
    :type icon_path: str
    :return: Absolute path to blueprint file
    :rtype: str

    """
    extract_directory = utils.extract_archive(archive)
    blueprint_directory = os.path.join(
        extract_directory,
        os.listdir(extract_directory)[0],
    )
    blueprint_file = os.path.join(blueprint_directory, blueprint_filename)
    if not os.path.isfile(blueprint_file):
        raise CloudifyCliError(
            'Could not find `{0}`. Please provide the name of the main '
            'blueprint file by using the `-n/--blueprint-filename` flag'
            .format(blueprint_filename))
    if icon_path:
        icon_file = os.path.join(blueprint_directory, ICON_FILENAME)
        copy(icon_path, icon_file)

    return blueprint_file


def _get_blueprint_file_with_icon(blueprint_path, icon_path):
    """Create a temporary directory with a blueprint file and its icon.

    :param blueprint_path: Absolute path to the blueprint file
    :type blueprint_path: str
    :param icon_path: Absolute path to blueprint's icon
    :type icon_path: str
    :return: Absolute path to blueprint file
    :rtype: str

    """
    source, blueprint_filename = os.path.split(blueprint_path)
    source = source or os.curdir
    blueprint_directory = os.path.join(tempfile.mkdtemp(),
                                       blueprint_filename.rpartition('.')[0])
    copytree(source, blueprint_directory)
    copy(icon_path, os.path.join(blueprint_directory, ICON_FILENAME))
    return os.path.join(blueprint_directory, blueprint_filename)


def _map_to_github_url(source):
    """Returns a path to a downloaded github archive.

    :param source: github repo in the format of `org/repo[:tag/branch]`.
    :type source: str
    :return: URL to the archive file for the given repo in github
    :rtype: str

    """
    source_parts = source.split(':', 1)
    repo = source_parts[0]
    tag = source_parts[1] if len(source_parts) == 2 else 'master'
    url = 'https://github.com/{0}/archive/{1}.tar.gz'.format(repo, tag)
    return url


def generate_id(blueprint_path, blueprint_filename=DEFAULT_BLUEPRINT_PATH):
    """The name of the blueprint will be the name of the folder.
    If blueprint_filename is provided, it will be appended to the
    folder.
    """
    blueprint_id = os.path.split(os.path.dirname(os.path.abspath(
        blueprint_path)))[-1]
    if not blueprint_filename == DEFAULT_BLUEPRINT_PATH:
        filename, _ = os.path.splitext(os.path.basename(blueprint_filename))
        blueprint_id = (blueprint_id + '.' + filename)
    return blueprint_id.replace('_', '-')


def get_blueprint_path_and_id(blueprint_path,
                              blueprint_filename,
                              blueprint_id):
    processed_blueprint_path = get(blueprint_path,
                                   blueprint_filename,
                                   download=True)
    blueprint_id = blueprint_id or generate_id(processed_blueprint_path,
                                               blueprint_filename)
    return processed_blueprint_path, blueprint_id
