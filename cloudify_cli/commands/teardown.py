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

from cloudify_rest_client.exceptions import CloudifyClientError

from .. import env
from .. import exceptions
from ..cli import cfy, helptexts
from ..bootstrap import bootstrap as bs


@cfy.command(name='teardown', short_help='Teardown a manager [manager only]')
@cfy.options.force(help=helptexts.FORCE_TEARDOWN)
@cfy.options.ignore_deployments
@cfy.options.verbose()
@cfy.pass_context
@cfy.assert_manager_active()
def teardown(ctx, force, ignore_deployments):
    """Teardown the manager
    """
    _assert_force(force)

    try:
        manager_ip = env.profile.manager_ip
    except exceptions.CloudifyCliError:
        # manager ip does not exist in the local context
        # this can mean one of two things:
        # 1. bootstrap was unsuccessful
        # 2. we are in the wrong directory
        try:
            env.load_env()
            # this means we are probably in the right directory
            # which means the teardown was unsuccessful, try to teardown
            # anyway
        except BaseException:
            # this means we are in the wrong directory, have the user
            # execute the 'use' command to retrieve manager deployment,
            # because other wise we cannot bootstrap from here. If the
            # manager is down, the user must return to the original
            # directory in order to teardown
            raise exceptions.CloudifyCliError(
                "You are attempting to teardown from an "
                "invalid directory. Please execute `cfy profiles use` before "
                "running this command. If the manager is "
                "unavailable, you must execute this command from the "
                "directory you initially bootstrapped from, or from the last "
                "directory a `cfy profiles use` command was executed on this"
                "manager.")
        else:
            _do_teardown()
    else:
        # make sure we don't teardown the manager if there are running
        # deployments, unless the user explicitly specified it.
        _validate_deployments(ignore_deployments, manager_ip)

        # execute teardown
        _do_teardown()


def _get_number_of_deployments(manager_ip):
    client = env.get_rest_client(rest_host=manager_ip)
    try:
        return len(client.deployments.list())
    except CloudifyClientError:
        raise exceptions.CloudifyCliError(
            "Failed to query manager {0} about existing "
            "deployments; The manager may be down. If you wish to "
            "skip this check, you may use the "'--ignore-deployments'" "
            "flag, in which case teardown will occur regardless of "
            "the deployment's status."
            .format(manager_ip))


def _validate_deployments(ignore_deployments, manager_ip):
    if ignore_deployments:
        return
    if _get_number_of_deployments(manager_ip) > 0:
        raise exceptions.CloudifyCliError(
            "Manager {0} has existing deployments. Delete "
            "all deployments first or add the "
            "'--ignore-deployments' flag to your command to ignore "
            "these deployments and execute teardown."
            .format(manager_ip)
        )


def _assert_force(force):
    if not force:
        raise exceptions.CloudifyCliError(
            "This action requires additional confirmation. Add the "
            "'-f/--force' flag to your command if you are certain this "
            "command should be executed.")


def _do_teardown():
    # reload settings since the provider context maybe changed
    p = env.get_profile_context()
    provider_context = p.provider_context
    bs.read_manager_deployment_dump_if_needed(
        provider_context.get('cloudify', {}).get('manager_deployment'))
    bs.teardown()

    env.delete_profile(p.manager_ip)
