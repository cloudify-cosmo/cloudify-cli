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
# * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

"""
Handles all commands that start with 'cfy blueprints'
"""

from cloudify_cli import utils
from cloudify_cli.logger import get_logger
from cloudify_cli.utils import print_table


def restore(snapshot_id):
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    logger.info("Restoring snapshot '{0}' at management server {1}"
                .format(snapshot_id, management_ip))
    client = utils.get_rest_client(management_ip)
    client.snapshots.restore(snapshot_id)
    logger.info('Restored snapshot successfully')


def create(snapshot_id):
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    logger.info("Creating snapshot '{0}' at management server {1}"
                .format(snapshot_id, management_ip))
    client = utils.get_rest_client(management_ip)
    snapshot = client.snapshots.create(snapshot_id)
    logger.info("Snapshot created, snapshot's id is: {0}"
                .format(snapshot.id))


def delete(snapshot_id):
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    logger.info("Deleting snapshot '{0}' from management server {1}"
                .format(snapshot_id, management_ip))
    client = utils.get_rest_client(management_ip)
    client.snapshots.delete(snapshot_id)
    logger.info('Deleted snapshot successfully')


def upload(snapshot_path, snapshot_id):
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    logger.info("Uploading snapshot '{0}' at management server {1}"
                .format(snapshot_path.name, management_ip))
    client = utils.get_rest_client(management_ip)
    snapshot = client.snapshots.upload(snapshot_path.name, snapshot_id)
    logger.info("Uploaded snapshot, snapshot's id is: {0}"
                .format(snapshot.id))


def download(snapshot_id, output):
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    logger.info("Downloading snapshot '{0}' ...".format(snapshot_id))
    client = utils.get_rest_client(management_ip)
    target_file = client.snapshots.download(snapshot_id, output)
    logger.info("Snapshot '{0}' has been downloaded successfully as '{1}'"
                .format(snapshot_id, target_file))


def ls():
    logger = get_logger()
    management_ip = utils.get_management_server_ip()
    client = utils.get_rest_client(management_ip)
    logger.info('Getting snapshots list... [manager={0}]'
                .format(management_ip))
    pt = utils.table(['id', 'created_at'],
                     data=client.snapshots.list())
    print_table('Snapshots:', pt)
