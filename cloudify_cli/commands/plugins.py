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

import tarfile
from urlparse import urlparse

import click

from .. import table
from .. import utils
from ..cli import helptexts, cfy
from ..exceptions import CloudifyCliError

columns = [
    'id',
    'package_name',
    'package_version',
    'supported_platform',
    'distribution',
    'distribution_release',
    'uploaded_at'
]


@cfy.group(name='plugins')
@cfy.options.verbose()
def plugins():
    """Handle plugins on the manager
    """
    pass


@plugins.command(name='validate',
                 short_help='Validate a plugin')
@cfy.argument('plugin-path')
@cfy.options.verbose()
@cfy.pass_logger
def validate(plugin_path, logger):
    """Validate a plugin

    This will try to validate the plugin's archive is not corrupted.
    A valid plugin is a wagon (http://github.com/cloudify-cosomo/wagon)
    in the tar.gz format.

    `PLUGIN_PATH` is the path to wagon archive to validate.
    """
    logger.info('Validating plugin {0}...'.format(plugin_path))

    if not tarfile.is_tarfile(plugin_path):
        raise CloudifyCliError(
            'Archive {0} is of an unsupported type. Only '
            'tar.gz/wgn is allowed'.format(plugin_path))
    with tarfile.open(plugin_path) as tar:
        tar_members = tar.getmembers()
        package_json_path = "{0}/{1}".format(
            tar_members[0].name, 'package.json')
        # TODO: Find a better way to validate a plugin.
        # This is.. bad.
        try:
            tar.getmember(package_json_path)
        except KeyError:
            raise CloudifyCliError(
                'Failed to validate plugin {0} '
                '(package.json was not found in archive)'.format(plugin_path))

    logger.info('Plugin validated successfully')


@plugins.command(name='delete',
                 short_help='Delete a plugin [manager only]')
@cfy.argument('plugin-id')
@cfy.options.force(help=helptexts.FORCE_DELETE_PLUGIN)
@cfy.options.verbose()
@cfy.assert_manager_active
@cfy.pass_client()
@cfy.pass_logger
def delete(plugin_id, force, logger, client):
    """Delete a plugin from the manager

    `PLUGIN_ID` is the id of the plugin to delete.
    """
    logger.info('Deleting plugin {0}...'.format(plugin_id))
    client.plugins.delete(plugin_id=plugin_id, force=force)
    logger.info('Plugin deleted')


@plugins.command(name='upload',
                 short_help='Upload a plugin [manager only]')
@cfy.argument('plugin-path')
@cfy.options.verbose()
@click.pass_context
@cfy.assert_manager_active
@cfy.pass_client()
@cfy.pass_logger
def upload(ctx, plugin_path, logger, client):
    """Upload a plugin to the manager

    `PLUGIN_PATH` is the path to wagon archive to upload.
    """
    # Test whether the path is a valid URL. If it is, no point in doing local
    # validations - it will be validated on the server side anyway
    parsed_url = urlparse(plugin_path)
    if not parsed_url.scheme or not parsed_url.netloc:
        ctx.invoke(validate, plugin_path=plugin_path)

    progress_handler = utils.generate_progress_handler(plugin_path, '')
    logger.info('Uploading plugin {0}...'.format(plugin_path))
    plugin = client.plugins.upload(plugin_path, progress_handler)
    logger.info("Plugin uploaded. The plugin's id is {0}".format(plugin.id))


@plugins.command(name='download',
                 short_help='Download a plugin [manager only]')
@cfy.argument('plugin-id')
@cfy.options.output_path
@cfy.options.verbose()
@cfy.pass_logger
@cfy.pass_client()
def download(plugin_id, output_path, logger, client):
    """Download a plugin from the manager

    `PLUGIN_ID` is the id of the plugin to download.
    """
    logger.info('Downloading plugin {0}...'.format(plugin_id))
    plugin_name = output_path if output_path else plugin_id
    progress_handler = utils.generate_progress_handler(plugin_name, '')
    target_file = client.plugins.download(plugin_id,
                                          output_path,
                                          progress_handler)
    logger.info('Plugin downloaded as {0}'.format(target_file))


@plugins.command(name='get',
                 short_help='Retrieve plugin information [manager only]')
@cfy.argument('plugin-id')
@cfy.options.verbose()
@cfy.assert_manager_active
@cfy.pass_client()
@cfy.pass_logger
def get(plugin_id, logger, client):
    """Retrieve information for a specific plugin

    `PLUGIN_ID` is the id of the plugin to get information on.
    """
    logger.info('Retrieving plugin {0}...'.format(plugin_id))
    plugin = client.plugins.get(plugin_id, _include=columns)

    pt = table.generate(columns, data=[plugin])
    table.log('Plugin:', pt)


@plugins.command(name='list',
                 short_help='List plugins [manager only]')
@cfy.options.sort_by('uploaded_at')
@cfy.options.descending
@cfy.options.verbose()
@cfy.assert_manager_active
@cfy.pass_client()
@cfy.pass_logger
def list(sort_by, descending, logger, client):
    """List all plugins on the manager
    """
    logger.info('Listing all plugins...')
    plugins = client.plugins.list(
        _include=columns,
        sort=sort_by,
        is_descending=descending)

    pt = table.generate(columns, data=plugins)
    table.log('Plugins:', pt)
