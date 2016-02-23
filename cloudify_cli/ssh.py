import os

import fabric.api as fab


from cloudify_cli.cli import get_global_verbosity
from cloudify_cli import utils
from cloudify_cli.exceptions import CloudifyCliError


def get_manager_date():
    # output here should be hidden anyway.
    with fab.settings(fab.hide('running', 'stdout')):
        return run_command_on_manager('date +%Y%m%dT%H%M%S').stdout


def get_file_from_manager(remote_source_path, destination_path):
    key_filename = os.path.expanduser(utils.get_management_key())
    with fab.settings(
            fab.hide('running', 'stdout'),
            host_string=utils.build_manager_host_string(),
            key_filename=key_filename):
        fab.get(remote_source_path, destination_path)


def run_command_on_manager(command, use_sudo=False):
    def execute():
        key_filename = os.path.expanduser(utils.get_management_key())
        with fab.settings(
                host_string=utils.build_manager_host_string(),
                key_filename=key_filename,
                warn_only=True):
            if use_sudo:
                result = fab.sudo(command)
            else:
                result = fab.run(command)
            if result.failed:
                raise CloudifyCliError(
                    'Failed to execute: {0} ({1})'.format(
                        result.read_command, result.stderr))
            return result

    if get_global_verbosity():
        return execute()
    else:
        with fab.hide('running', 'stdout'):
            return execute()
