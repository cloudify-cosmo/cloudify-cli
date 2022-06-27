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
import json
import shutil
import tempfile
from datetime import datetime

from cloudify.workflows import local
from cloudify.utils import LocalCommandRunner

from dsl_parser.parser import parse_from_path
from dsl_parser import constants as dsl_constants

from cloudify_cli import constants, env, exceptions, utils
from cloudify_cli.logger import get_logger
from cloudify_cli.config.config import CloudifyConfig


_ENV_NAME = 'local'


def initialize_blueprint(blueprint_path,
                         name,
                         storage=None,
                         install_plugins=False,
                         inputs=None,
                         resolver=None):
    logger = get_logger()

    logger.info('Initializing blueprint...')
    if install_plugins:
        _install_plugins(blueprint_path=blueprint_path)

    config = CloudifyConfig()
    return local.init_env(
        blueprint_path=blueprint_path,
        name=name,
        inputs=inputs,
        storage=storage,
        ignored_modules=constants.IGNORED_LOCAL_WORKFLOW_MODULES,
        provider_context=config.local_provider_context,
        resolver=resolver,
        validate_version=config.validate_definitions_version)


def _is_old_local_profile(storage_dir):
    try:
        entries = os.listdir(storage_dir)
    except (IOError, OSError):
        return False
    return (
        entries
        and 'blueprints' not in entries
        and 'deployments' not in entries
    )


def _update_local_profile(storage_dir):
    backup_dirname = '{0}_backup_{1}'.format(
        os.path.basename(storage_dir),
        datetime.utcnow().strftime('%Y_%m_%d_%H_%M_%S')
    )
    backup_target = os.path.join(
        os.path.dirname(storage_dir),
        backup_dirname,
    )
    shutil.copytree(storage_dir, backup_target)
    blueprints_dir = os.path.join(storage_dir, 'blueprints')
    deployments_dir = os.path.join(storage_dir, 'deployments')
    for blueprint_id in os.listdir(storage_dir):
        source_blueprint_dir = os.path.join(storage_dir, blueprint_id)
        with open(os.path.join(source_blueprint_dir, 'data')) as f:
            data = json.load(f)
        target_blueprint_dir = os.path.join(blueprints_dir, blueprint_id)
        target_resources_dir = os.path.join(target_blueprint_dir, 'resources')
        os.makedirs(target_blueprint_dir)

        blueprint_fn = os.path.join(target_blueprint_dir, 'blueprint.json')
        blueprint_data = data.copy()
        blueprint_data['id'] = blueprint_id
        blueprint_data['resources'] = target_resources_dir
        with open(blueprint_fn, 'w') as f:
            json.dump(blueprint_data, f)

        shutil.copy(
            os.path.join(source_blueprint_dir, 'payload'),
            os.path.join(target_blueprint_dir, 'payload'),
        )
        shutil.copytree(
            os.path.join(source_blueprint_dir, 'resources'),
            target_resources_dir,
        )
        target_deployment_dir = os.path.join(deployments_dir, blueprint_id)
        os.makedirs(target_deployment_dir)

        shutil.copy(
            os.path.join(source_blueprint_dir, 'executions'),
            os.path.join(target_deployment_dir, 'executions.json'),
        )

        source_instances_dir = os.path.join(
            source_blueprint_dir, 'node-instances')
        target_instances_dir = os.path.join(
            target_deployment_dir, 'node-instances')
        os.makedirs(target_instances_dir)
        for instance_fn in os.listdir(source_instances_dir):
            shutil.copy(
                os.path.join(source_instances_dir, instance_fn),
                os.path.join(target_instances_dir, instance_fn + '.json')
            )
        shutil.copytree(
            os.path.join(source_blueprint_dir, 'work'),
            os.path.join(target_deployment_dir, 'work'),
        )

        deployment_fn = os.path.join(target_deployment_dir, 'deployment.json')
        deployment_data = data.copy()
        deployment_data['id'] = blueprint_id
        deployment_data['blueprint_id'] = blueprint_id
        deployment_data['nodes'] = {
            n['id']: n for n in deployment_data['plan']['nodes']
        }
        with open(deployment_fn, 'w') as f:
            json.dump(deployment_data, f)

        shutil.rmtree(source_blueprint_dir)


def storage_dir():
    storage = os.path.join(env.PROFILES_DIR, _ENV_NAME)
    if _is_old_local_profile(storage):
        _update_local_profile(storage)
    return storage


def list_blueprints():
    blueprints = []
    storage = get_storage()
    try:
        bp_names = storage.blueprint_ids()
    except IOError as e:
        if e.errno != 2:  # file not found
            raise
        bp_names = []
    for bp_id in bp_names:
        bp = storage.get_blueprint(bp_id)
        blueprints.append({
            'id': bp_id,
            'description': bp['plan']['description'],
            'main_file_name': bp['blueprint_filename'],
            'created_at': bp['created_at'],
        })
    return blueprints


def get_storage():
    return local.FileStorage(storage_dir=storage_dir())


def load_env(blueprint_id):
    env = local.load_env(name=blueprint_id or 'local', storage=get_storage())
    if env is None:
        error = exceptions.CloudifyCliError('Please initialize a blueprint')
        error.possible_solutions = ["Run `cfy init BLUEPRINT_PATH`"]
        raise error
    return env


def blueprint_exists(blueprint_id):
    storage = local.FileStorage(storage_dir=storage_dir())
    return storage.get_blueprint(blueprint_id) is not None


def remove(blueprint_id):
    storage = get_storage()
    storage.remove_deployment(blueprint_id)
    storage.remove_blueprint(blueprint_id)


def _install_plugins(blueprint_path):
    requirements = create_requirements(blueprint_path=blueprint_path)
    logger = get_logger()

    if requirements:
        # Validate we are inside a virtual env
        if not utils.is_virtual_env():
            raise exceptions.CloudifyCliError(
                'You must be running inside a '
                'virtualenv to install blueprint plugins')

        runner = LocalCommandRunner(logger)
        # Dump the requirements to a file and let pip install it.
        # This will utilize pip's mechanism of cleanup in case an installation
        # fails.
        tmp_path = tempfile.mkstemp(suffix='.txt', prefix='requirements_')[1]
        utils.dump_to_file(collection=requirements, file_path=tmp_path)
        command_parts = [sys.executable, '-m', 'pip', 'install', '-r',
                         tmp_path]
        runner.run(command=' '.join(command_parts), stdout_pipe=False)
    else:
        logger.info('There are no plugins to install')


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
