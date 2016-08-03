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
import tempfile


from cloudify.workflows import local
from cloudify.utils import LocalCommandRunner
from dsl_parser.parser import parse_from_path
from dsl_parser import constants as dsl_constants

from . import env
from . import utils
from . import constants
from . import exceptions
from .logger import get_logger
from .exceptions import CloudifyCliError
from .constants import DEFAULT_BLUEPRINT_PATH


_ENV_NAME = 'local'
_STORAGE_DIR_NAME = 'local-storage'


def initialize_blueprint(blueprint_path,
                         name,
                         storage,
                         install_plugins=False,
                         inputs=None,
                         resolver=None):
    logger = get_logger()

    logger.info('Initializing blueprint...')
    if install_plugins:
        install_blueprint_plugins(blueprint_path=blueprint_path)

    config = env.CloudifyConfig()
    return local.init_env(
        blueprint_path=blueprint_path,
        name=name,
        inputs=inputs,
        storage=storage,
        ignored_modules=constants.IGNORED_LOCAL_WORKFLOW_MODULES,
        provider_context=config.local_provider_context,
        resolver=resolver,
        validate_version=config.validate_definitions_version)


def install_blueprint_plugins(blueprint_path):

    requirements = create_requirements(blueprint_path=blueprint_path)

    if requirements:
        # Validate we are inside a virtual env
        if not utils.is_virtual_env():
            raise exceptions.CloudifyCliError(
                'You must be running inside a '
                'virtualenv to install blueprint plugins')

        runner = LocalCommandRunner(get_logger())
        # Dump the requirements to a file and let pip install it.
        # This will utilize pip's mechanism of cleanup in case an installation
        # fails.
        tmp_path = tempfile.mkstemp(suffix='.txt', prefix='requirements_')[1]
        utils.dump_to_file(collection=requirements, file_path=tmp_path)
        command_parts = [sys.executable, '-m', 'pip', 'install', '-r',
                         tmp_path]
        runner.run(command=' '.join(command_parts), stdout_pipe=False)
    else:
        logger = get_logger()
        logger.debug('There are no plugins to install')


def create_requirements(blueprint_path):

    parsed_dsl = parse_from_path(dsl_file_path=blueprint_path)

    requirements = _plugins_to_requirements(
        blueprint_path=blueprint_path,
        plugins=parsed_dsl[dsl_constants.DEPLOYMENT_PLUGINS_TO_INSTALL])

    for node in parsed_dsl['nodes']:
        requirements.update(_plugins_to_requirements(
            blueprint_path=blueprint_path,
            plugins=node['plugins']))
    return requirements


def _plugins_to_requirements(blueprint_path, plugins):

    sources = set()
    for plugin in plugins:
        if plugin[dsl_constants.PLUGIN_INSTALL_KEY]:
            source = plugin[dsl_constants.PLUGIN_SOURCE_KEY]
            if not source:
                continue
            if '://' in source:
                # URL
                sources.add(source)
            else:
                # Local plugin (should reside under the 'plugins' dir)
                plugin_path = os.path.join(
                    os.path.abspath(os.path.dirname(blueprint_path)),
                    'plugins',
                    source)
                sources.add(plugin_path)
    return sources


def add_ignore_bootstrap_validations_input(inputs):
    """This is used when passing the `--skip-validations` flag as we
    also want to skip bootstrap validations, not just `creation_validation`
    operations.
    """
    assert isinstance(inputs, dict)
    inputs.update({'ignore_bootstrap_validations': True})


def storage_dir():
    return os.path.join(env.PROFILES_DIR, _ENV_NAME, _STORAGE_DIR_NAME)


def storage():
    return local.FileStorage(storage_dir=storage_dir())


def load_env():
    if not os.path.isdir(storage_dir()):
        error = exceptions.CloudifyCliError('Please initialize a blueprint')
        error.possible_solutions = ["Run `cfy init BLUEPRINT_PATH`"]
        raise error
    return local.load_env(name=_ENV_NAME, storage=storage())


def print_table(title, tb):
    logger = get_logger()
    logger.info('{0}{1}{0}{2}{0}'.format(os.linesep, title, tb))


def get_blueprint(source, blueprint_filename):
    """Get a source and return a directory containing the blueprint

    if it's a URL of an archive, download and extract it.
    if it's a local archive, extract it.
    if it's a local yaml, return it.
    else turn to github and try to get it.
    else should implicitly fail.
    """
    # Using it this way instead of a default value, because None may be passed
    blueprint_filename = blueprint_filename or DEFAULT_BLUEPRINT_PATH

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


def get_blueprint_id(blueprint_folder,
                     blueprint_filename=DEFAULT_BLUEPRINT_PATH):
    """The name of the blueprint will be the name of the folder.
    If blueprint_filename is provided, it will be appended to the
    folder.
    """
    blueprint_filename = blueprint_filename or DEFAULT_BLUEPRINT_PATH
    blueprint_id = os.path.dirname(blueprint_folder).split('/')[-1]
    if not blueprint_filename == DEFAULT_BLUEPRINT_PATH:
        filename, _ = os.path.splitext(os.path.basename(blueprint_filename))
        blueprint_id = (blueprint_id + '.' + filename)
    return blueprint_id.replace('_', '-')
