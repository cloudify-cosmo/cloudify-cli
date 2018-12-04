from .. import utils
from ..cli import cfy
from ..table import print_data
import click


@cfy.group(name='summary')
@cfy.options.common_options
@cfy.assert_manager_active()
def summary():
    """Get summary information
    """
    pass


@summary.command(name='nodes',
                 short_help='Retrieve summary of node details [manager only]')
@cfy.argument('target_field', type=click.Choice(['deployment_id']))
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='summary')
@cfy.pass_logger
@cfy.pass_client()
def nodes(target_field, logger, client, tenant_name):
    """Retrieve summary of nodes, e.g. a count of each node with the same
    deployment ID.

    `TARGET_FIELD` is the field to summarise nodes on.
                   Valid fields: deployment_id
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Retrieving summary of nodes on field {field}'.format(
        field=target_field))

    summary = client.summary.nodes.get(
        _target_field=target_field,
    )

    print_data(
        [target_field, 'nodes'],
        summary.items,
        'Node summary by {field}'.format(field=target_field),
    )


@summary.command(name='node_instances',
                 short_help='Retrieve summary of node instance details '
                            '[manager only]')
@cfy.argument('target_field', type=click.Choice(['deployment_id', 'node_id']))
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='summary')
@cfy.pass_logger
@cfy.pass_client()
def node_instances(target_field, logger, client, tenant_name):
    """Retrieve summary of node instances, e.g. a count of each node instance
    with the same deployment ID.

    `TARGET_FIELD` is the field to summarise node instances on.
                   Valid fields: deployment_id, node_id
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info(
        'Retrieving summary of node instances on field {field}'.format(
            field=target_field,
        )
    )

    summary = client.summary.node_instances.get(
        _target_field=target_field,
    )

    print_data(
        [target_field, 'node_instances'],
        summary.items,
        'Node instance summary by {field}'.format(field=target_field),
    )


@summary.command(name='deployments',
                 short_help='Retrieve summary of deployment details '
                            '[manager only]')
@cfy.argument('target_field', type=click.Choice(['blueprint_id']))
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='summary')
@cfy.pass_logger
@cfy.pass_client()
def deployments(target_field, logger, client, tenant_name):
    """Retrieve summary of deployments, e.g. a count of each deployment with
    the same blueprint ID.

    `TARGET_FIELD` is the field to summarise deployments on.
                   Valid fields: blueprint_id
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Retrieving summary of deployments on field {field}'.format(
        field=target_field))

    summary = client.summary.deployments.get(
        _target_field=target_field,
    )

    print_data(
        [target_field, 'deployments'],
        summary.items,
        'Deployment summary by {field}'.format(field=target_field),
    )
