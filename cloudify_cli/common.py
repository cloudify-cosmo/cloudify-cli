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
import glob
import tempfile

import yaml

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
    inputs = inputs_to_dict(inputs, 'inputs')
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
    inputs.append('{"ignore_bootstrap_validations":true}')
    return inputs


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


def inputs_to_dict(resources, resource_name):
    """Returns a dictionary of inputs

    `resources` can be:
    - A list of files.
    - A single file
    - A directory containing multiple input files
    - A key1=value1;key2=value2 pairs string.
    - Wildcard based string (e.g. *-inputs.yaml)
    """
    logger = get_logger()

    if not resources:
        # TODO: This means that the function either returns a dictionary
        # or None. We should probably return an empty dict here?
        return None

    # Avoid going through the params more than once
    if isinstance(resources, dict):
        return resources

    parsed_dict = {}

    # TODO: We should separate this entire thing into functions where
    # each function deals with a different format of inputs.
    # This is just nasty.
    def handle_inputs_source(resource):
        logger.debug('Processing inputs source: {0}'.format(resource))
        try:
            # parse resource as string representation of a dictionary
            content = plain_string_to_dict(resource)
        except CloudifyCliError:
            try:
                # if resource is a path - parse as a yaml file
                if os.path.isfile(resource):
                    with open(resource) as f:
                        content = yaml.load(f.read())
                else:
                    # parse resource content as yaml
                    content = yaml.load(resource)
            except yaml.error.YAMLError as e:
                raise CloudifyCliError("'{0}' is not a valid YAML. {1}".format(
                    resource, str(e)))

        if isinstance(content, dict):
            parsed_dict.update(content)
        elif content is None:
            # emtpy file should be handled as no input.
            pass
        else:
            raise CloudifyCliError(
                "Invalid input: {0}. {1} must represent a dictionary. "
                "Valid values can be one of:\n "
                "- A path to a YAML file\n "
                "- A path to a directory containing YAML files\n "
                "- A single quoted wildcard based path "
                "(e.g. '*-inputs.yaml')\n "
                "- A string formatted as JSON\n "
                "- A string formatted as key1=value1;key2=value2".format(
                    resource, resource_name))

    if not isinstance(resources, list):
        # TODO: Anyone who uses `inputs_to_dict` should always send a list.
        # Doing this here is unhealthy.
        resources = [resources]

    for resource in resources:
        # workflow parameters always pass an empty dictionary.
        # we ignore it.
        if isinstance(resource, basestring):
            input_files = glob.glob(resource)
            if os.path.isdir(resource):
                for input_file in os.listdir(resource):
                    handle_inputs_source(os.path.join(resource, input_file))
            elif input_files:
                for input_file in input_files:
                    handle_inputs_source(input_file)
            else:
                handle_inputs_source(resource)

    return parsed_dict


def plain_string_to_dict(input_string):
    input_string = input_string.strip()
    input_dict = {}
    mapped_inputs = input_string.split(';')
    for mapped_input in mapped_inputs:
        mapped_input = mapped_input.strip()
        if not mapped_input:
            continue
        split_mapping = mapped_input.split('=')
        if len(split_mapping) == 2:
            key = split_mapping[0].strip()
            value = split_mapping[1].strip()
            input_dict[key] = value
        else:
            # TODO: This should happen in the calling function.
            raise CloudifyCliError(
                "Invalid input format: {0}, the expected format is: "
                "key1=value1;key2=value2".format(input_string))

    return input_dict


def get_blueprint(source, blueprint_filename='blueprint.yaml'):
    """Get a source and return a directory containing the blueprint

    if it's a URL of an archive, download and extract it.
    if it's a local archive, extract it.
    if it's a local yaml, return it.
    else turn to github and try to get it.
    else should implicitly fail.
    """
    def get_blueprint_file(final_source, nest_one=True):
        blueprint = utils.extract_archive(final_source)
        # TODO: To support cases in which the blueprint is not nested
        # within the archive, we need to allow this to be false.
        # This will currently not work as nothing calls this with false.
        # We need to add a check for that or something.
        if nest_one:
            blueprint = os.path.join(blueprint, os.listdir(blueprint)[0])
        blueprint_file = os.path.join(blueprint, blueprint_filename)
        if not os.path.isfile(blueprint_file):
            raise CloudifyCliError(
                'Could not find `{0}`. Please provide the name of the main '
                'blueprint file by using the `-n/--blueprint-filename` flag'
                .format(blueprint_filename))
        return blueprint_file

    # TODO: Verify this supports file://
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
    source_parts = source.split(':', 1)
    repo = source_parts[0]
    tag = source_parts[1] if len(source_parts) == 2 else 'master'
    url = 'https://github.com/{0}/archive/{1}.tar.gz'.format(repo, tag)
    return utils.download_file(url)


def get_blueprint_id(blueprint_folder,
                     blueprint_filename=DEFAULT_BLUEPRINT_PATH):
    # If you provided a folder, take the name of the folder.
    # If you provided a blueprint via the -n flag, append that to the folder
    blueprint_id = os.path.dirname(blueprint_folder).split('/')[-1]
    if not blueprint_filename == DEFAULT_BLUEPRINT_PATH:
        filename, _ = os.path.splitext(os.path.basename(blueprint_filename))
        blueprint_id = (blueprint_id + '.' + filename)
    return blueprint_id.replace('_', '-')
