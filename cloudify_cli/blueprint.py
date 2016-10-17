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
from urlparse import urlparse

from . import utils
from .exceptions import CloudifyCliError
from .constants import DEFAULT_BLUEPRINT_PATH


def get(source, blueprint_filename=DEFAULT_BLUEPRINT_PATH):
    """Get a source and return a directory containing the blueprint

    The behavior based on then source argument content is:
        - URL: return it (let the manager download the blueprint later)
        - local archive (.zip, .tar.gz): extract it and return blueprint file
        - local yaml file: return the file
        - github repo: map it to a URL and return it

    :param source: Path/URL/github repo to archive/blueprint file
    :type source: str
    :param blueprint_filename: Path to blueprint (if source is an archive file)
    :type blueprint_filename: str
    :return: Path to file (if archive/blueprint file passsed) or url
    :rtype: str

    """
    def get_blueprint_file(final_source):
        archive_root = utils.extract_archive(final_source)
        blueprint_directory = os.path.join(
            archive_root,
            os.listdir(archive_root)[0],
        )
        blueprint_file = os.path.join(blueprint_directory, blueprint_filename)
        if not os.path.isfile(blueprint_file):
            raise CloudifyCliError(
                'Could not find `{0}`. Please provide the name of the main '
                'blueprint file by using the `-n/--blueprint-filename` flag'
                .format(blueprint_filename))
        return blueprint_file

    if urlparse(source).scheme:
        return source
    elif os.path.isfile(source):
        if utils.is_archive(source):
            return get_blueprint_file(source)
        else:
            # Maybe check if yaml. If not, verified by dsl parser
            return source
    elif len(source.split('/')) == 2:
        return _map_to_github_url(source)
    else:
        raise CloudifyCliError(
            'You must provide either a path to a local file, a remote URL '
            'or a GitHub `organization/repository[:tag/branch]`')


def _map_to_github_url(source):
    """Returns a path to a downloaded github archive.

    Source to download should be in the format of `org/repo[:tag/branch]`.

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
