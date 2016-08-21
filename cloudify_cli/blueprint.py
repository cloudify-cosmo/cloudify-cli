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

from . import utils
from .exceptions import CloudifyCliError
from .constants import DEFAULT_BLUEPRINT_PATH


def get(source, blueprint_filename=DEFAULT_BLUEPRINT_PATH):
    """Get a source and return a directory containing the blueprint

    if it's a URL of an archive, download and extract it.
    if it's a local archive, extract it.
    if it's a local yaml, return it.
    else turn to github and try to get it.
    else should implicitly fail.
    """
    def get_blueprint_file(final_source):
        archive_root = utils.extract_archive(final_source)
        blueprint = os.path.join(archive_root, os.listdir(archive_root)[0])
        blueprint_file = os.path.join(blueprint, blueprint_filename)
        if not os.path.isfile(blueprint_file):
            raise CloudifyCliError(
                'Could not find `{0}`. Please provide the name of the main '
                'blueprint file by using the `-n/--blueprint-filename` flag'
                .format(blueprint_filename))
        return blueprint_file

    if '://' in source:
        downloaded_source = utils.download_file(source)
        return get_blueprint_file(downloaded_source)
    elif os.path.isfile(source):
        if utils.is_archive(source):
            return get_blueprint_file(source)
        else:
            # Maybe check if yaml. If not, verified by dsl parser
            return source
    elif len(source.split('/')) == 2:
        downloaded_source = _get_from_github(source)
        # GitHub archives provide an inner folder with each archive.
        return get_blueprint_file(downloaded_source)
    else:
        raise CloudifyCliError(
            'You must provide either a path to a local file, a remote URL '
            'or a GitHub `organization/repository[:tag/branch]`')


def _get_from_github(source):
    """Returns a path to a downloaded github archive.

    Source to download should be in the format of `org/repo[:tag/branch]`.
    """
    source_parts = source.split(':', 1)
    repo = source_parts[0]
    tag = source_parts[1] if len(source_parts) == 2 else 'master'
    url = 'https://github.com/{0}/archive/{1}.tar.gz'.format(repo, tag)
    return utils.download_file(url)


def generate_id(blueprint_folder, blueprint_filename=DEFAULT_BLUEPRINT_PATH):
    """The name of the blueprint will be the name of the folder.
    If blueprint_filename is provided, it will be appended to the
    folder.
    """
    blueprint_id = os.path.dirname(blueprint_folder).split('/')[-1]
    if not blueprint_filename == DEFAULT_BLUEPRINT_PATH:
        filename, _ = os.path.splitext(os.path.basename(blueprint_filename))
        blueprint_id = (blueprint_id + '.' + filename)
    return blueprint_id.replace('_', '-')
