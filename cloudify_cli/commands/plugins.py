########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import tarfile

import click

from .. import env
from .. import utils
from .. import common
from ..config import cfy
from ..config import helptexts
from ..logger import get_logger
from ..exceptions import CloudifyCliError


fields = [
    'id',
    'package_name',
    'package_version',
    'supported_platform',
    'distribution',
    'distribution_release',
    'uploaded_at'
]


@cfy.group(name='plugins')
@cfy.options.verbose
def plugins():
    """Handle plugins on the manager
    """
    env.assert_manager_active()


@plugins.command(name='validate')
@cfy.argument('plugin-path')
@cfy.options.verbose
def validate(plugin_path):
    """Validate a plugin

    This will try to validate the plugin's archive is not corrupted.
    A valid plugin is a wagon (http://github.com/cloudify-cosomo/wagon)
    in the tar.gz format.

    `PLUGIN_PATH` is the path to wagon archive to validate.
    """
    logger = get_logger()
    logger.info('Validating plugin {0}...'.format(plugin_path))

    if not tarfile.is_tarfile(plugin_path):
        raise CloudifyCliError(
            'Archive {0} is of an unsupported type. Only '
            'tar.gz is allowed'.format(plugin_path))
    with tarfile.open(plugin_path) as tar:
        tar_members = tar.getmembers()
        package_json_path = "{0}/{1}".format(
            tar_members[0].name, 'package.json')
        # TODO: Find a better way to validate a plugin.
        # This is.. bad.
        try:
            package_member = tar.getmember(package_json_path)
        except KeyError:
            raise CloudifyCliError(
                'Failed to validate plugin {0} '
                '(package.json was not found in archive)'.format(plugin_path))
        try:
            tar.extractfile(package_member).read()
        except:
            raise CloudifyCliError(
                'Failed to validate plugin {0} '
                '(unable to read package.json)'.format(plugin_path))

    logger.info('Plugin validated successfully')


@plugins.command(name='delete')
@cfy.argument('plugin-id')
@cfy.options.force(help=helptexts.FORCE_DELETE_PLUGIN)
@cfy.options.verbose
def delete(plugin_id, force):
    """Delete a plugin from the manager

    `PLUGIN_ID` is the id of the plugin to delete.
    """
    logger = get_logger()
    client = env.get_rest_client()

    logger.info('Deleting plugin {0}...'.format(plugin_id))
    client.plugins.delete(plugin_id=plugin_id, force=force)
    logger.info('Plugin deleted')


@plugins.command(name='upload')
@cfy.argument('plugin-path')
@cfy.options.verbose
@click.pass_context
def upload(ctx, plugin_path):
    """Upload a plugin to the manager

    `PLUGIN_PATH` is the path to wagon archive to upload.
    """
    ctx.invoke(validate, plugin_path=plugin_path)

    logger = get_logger()
    client = env.get_rest_client()

    progress_handler = utils.generate_progress_handler(plugin_path, '')
    logger.info('Uploading plugin {0}...'.format(plugin_path))
    plugin = client.plugins.upload(plugin_path, progress_handler)
    logger.info("Plugin uploaded. The plugin's id is {0}".format(plugin.id))


@plugins.command(name='download')
@cfy.argument('plugin-id')
@cfy.options.output_path
@cfy.options.verbose
def download(plugin_id, output_path):
    """Download a plugin from the manager

    `PLUGIN_ID` is the id of the plugin to download.
    """
    logger = get_logger()
    client = env.get_rest_client()

    logger.info('Downloading plugin {0}...'.format(plugin_id))
    progress_handler = utils.generate_progress_handler(output_path, '')
    target_file = client.plugins.download(plugin_id,
                                          output_path,
                                          progress_handler)
    logger.info('Plugin downloaded as {0}'.format(target_file))


@plugins.command(name='get')
@cfy.argument('plugin-id')
@cfy.options.verbose
def get(plugin_id):
    """Retrieve information for a specific plugin

    `PLUGIN_ID` is the id of the plugin to get information on.
    """
    logger = get_logger()
    client = env.get_rest_client()

    logger.info('Retrieving plugin {0}...'.format(plugin_id))
    plugin = client.plugins.get(plugin_id, _include=fields)

    pt = utils.table(fields, data=[plugin])
    common.print_table('Plugin:', pt)


@plugins.command(name='list')
@cfy.options.sort_by('uploaded_at')
@cfy.options.descending
@cfy.options.verbose
def list(sort_by=None, descending=False):
    """List all plugins on the manager
    """
    logger = get_logger()
    client = env.get_rest_client()

    logger.info('Listing all plugins...')
    plugins = client.plugins.list(_include=fields,
                                  sort=sort_by,
                                  is_descending=descending)

    pt = utils.table(fields, data=plugins)
    common.print_table('Plugins:', pt)


# TODO: Add plugins install for local. Currently, we use wagon for that.
# We should transparently pass all wagon args to wagon from an install
# command like `cfy plugins install`
