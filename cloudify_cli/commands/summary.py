from .. import utils
from ..cli import cfy
from ..logger import get_global_json_output
from ..table import print_data
import click


BASE_SUMMARY_FIELDS = [
    'tenant_name',
    'visibility',
]
DEPLOYMENTS_SUMMARY_FIELDS = [
    'blueprint_id',
] + BASE_SUMMARY_FIELDS
NODES_SUMMARY_FIELDS = [
    'deployment_id',
] + BASE_SUMMARY_FIELDS
NODE_INSTANCES_SUMMARY_FIELDS = [
    'deployment_id',
    'node_id',
    'state',
    'host_id',
] + BASE_SUMMARY_FIELDS
EXECUTIONS_SUMMARY_FIELDS = [
    'status',
    'blueprint_id',
    'deployment_id',
    'workflow_id',
] + BASE_SUMMARY_FIELDS
BLUEPRINTS_SUMMARY_FIELDS = BASE_SUMMARY_FIELDS


@cfy.group(name='summary')
@cfy.options.common_options
@cfy.assert_manager_active()
def summary():
    """Get summary information
    """
    pass


def _structure_results_and_columns(results, target_field, sub_field,
                                   summary_type):
    """Restructure the results returned from the rest client.

    This is needed in case sub-fields are provided, as sub-fields will result
    in output that looks like:
    [
        {
            "<target_field>": "<value>",
            "<summary_type>": <total count>,
            "by <sub_field>": [
                {
                    "<sub_field>": "<sub_field value>",
                    "<summary_type>": <count>,
                },
                ... more sub-field results for this value of target_field ...
            ],
        },
        ... more results ...
    ]

    For compatibility with the CLI output tools, we want to turn this into:
    [
        {
            "<target_field>": "<value>",
            "<sub_field>": "<sub_field value>",
            "<summary_type>": <count>,
        },
        ... more sub-field results for this value of target_field ...
        {
            "<target_field>": "<value>",
            "<sub_field>": "<TOTAL if not json, empty if json>",
            "<summary_type>": <count>,
        },
        ... sub-fields followed by totals for other target_field values ...
    ]
    """
    if sub_field:
        columns = [target_field, sub_field, summary_type]
        structured_result = []
        for result in results:
            for sub_result in result['by ' + sub_field]:
                structured_result.append(
                    {
                        target_field: result[target_field],
                        sub_field: sub_result[sub_field],
                        summary_type: sub_result[summary_type],
                    }
                )
            structured_result.append(
                {
                    target_field: result[target_field],
                    sub_field: '' if get_global_json_output() else 'TOTAL',
                    summary_type: result[summary_type],
                }
            )
    else:
        columns = [target_field, summary_type]
        structured_result = results
    return columns, structured_result


@summary.command(name='nodes',
                 short_help='Retrieve summary of node details [manager only]')
@cfy.argument('target_field', type=click.Choice(NODES_SUMMARY_FIELDS))
@cfy.argument('sub_field', type=click.Choice(NODES_SUMMARY_FIELDS),
              default=None, required=False)
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='summary')
@cfy.options.all_tenants
@cfy.pass_logger
@cfy.pass_client()
def nodes(target_field, sub_field, logger, client, tenant_name, all_tenants):
    """Retrieve summary of nodes, e.g. a count of each node with the same
    deployment ID.

    `TARGET_FIELD` is the field to summarise nodes on.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Retrieving summary of nodes on field {field}'.format(
        field=target_field))

    summary = client.summary.nodes.get(
        _target_field=target_field,
        _sub_field=sub_field,
        _all_tenants=all_tenants,
    )

    columns, items = _structure_results_and_columns(
        summary.items,
        target_field,
        sub_field,
        'nodes',
    )

    print_data(
        columns,
        items,
        'Node summary by {field}'.format(field=target_field),
    )


@summary.command(name='node_instances',
                 short_help='Retrieve summary of node instance details '
                            '[manager only]')
@cfy.argument('target_field',
              type=click.Choice(NODE_INSTANCES_SUMMARY_FIELDS))
@cfy.argument('sub_field',
              type=click.Choice(NODE_INSTANCES_SUMMARY_FIELDS),
              default=None, required=False)
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='summary')
@cfy.options.all_tenants
@cfy.pass_logger
@cfy.pass_client()
def node_instances(target_field, sub_field, logger, client, tenant_name,
                   all_tenants):
    """Retrieve summary of node instances, e.g. a count of each node instance
    with the same deployment ID.

    `TARGET_FIELD` is the field to summarise node instances on.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info(
        'Retrieving summary of node instances on field {field}'.format(
            field=target_field,
        )
    )

    summary = client.summary.node_instances.get(
        _target_field=target_field,
        _sub_field=sub_field,
        _all_tenants=all_tenants,
    )

    columns, items = _structure_results_and_columns(
        summary.items,
        target_field,
        sub_field,
        'node_instances',
    )

    print_data(
        columns,
        items,
        'Node instance summary by {field}'.format(field=target_field),
    )


@summary.command(name='deployments',
                 short_help='Retrieve summary of deployment details '
                            '[manager only]')
@cfy.argument('target_field', type=click.Choice(DEPLOYMENTS_SUMMARY_FIELDS))
@cfy.argument('sub_field', type=click.Choice(DEPLOYMENTS_SUMMARY_FIELDS),
              default=None, required=False)
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='summary')
@cfy.options.all_tenants
@cfy.pass_logger
@cfy.pass_client()
def deployments(target_field, sub_field, logger, client, tenant_name,
                all_tenants):
    """Retrieve summary of deployments, e.g. a count of each deployment with
    the same blueprint ID.

    `TARGET_FIELD` is the field to summarise deployments on.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Retrieving summary of deployments on field {field}'.format(
        field=target_field))

    summary = client.summary.deployments.get(
        _target_field=target_field,
        _sub_field=sub_field,
        _all_tenants=all_tenants,
    )

    columns, items = _structure_results_and_columns(
        summary.items,
        target_field,
        sub_field,
        'deployments',
    )

    print_data(
        columns,
        items,
        'Deployment summary by {field}'.format(field=target_field),
    )


@summary.command(name='executions',
                 short_help='Retrieve summary of execution details '
                            '[manager only]')
@cfy.argument('target_field', type=click.Choice(EXECUTIONS_SUMMARY_FIELDS))
@cfy.argument('sub_field', type=click.Choice(EXECUTIONS_SUMMARY_FIELDS),
              default=None, required=False)
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='summary')
@cfy.options.all_tenants
@cfy.pass_logger
@cfy.pass_client()
def executions(target_field, sub_field, logger, client, tenant_name,
               all_tenants):
    """Retrieve summary of executions, e.g. a count of each execution with
    the same deployment ID.

    `TARGET_FIELD` is the field to summarise executions on.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Retrieving summary of executions on field {field}'.format(
        field=target_field))

    summary = client.summary.executions.get(
        _target_field=target_field,
        _sub_field=sub_field,
        _all_tenants=all_tenants,
    )

    columns, items = _structure_results_and_columns(
        summary.items,
        target_field,
        sub_field,
        'executions',
    )

    print_data(
        columns,
        items,
        'Execution summary by {field}'.format(field=target_field),
    )


@summary.command(name='blueprints',
                 short_help='Retrieve summary of blueprint details '
                            '[manager only]')
@cfy.argument('target_field', type=click.Choice(BLUEPRINTS_SUMMARY_FIELDS))
@cfy.argument('sub_field', type=click.Choice(BLUEPRINTS_SUMMARY_FIELDS),
              default=None, required=False)
@cfy.options.common_options
@cfy.options.tenant_name(required=False, resource_name_for_help='summary')
@cfy.options.all_tenants
@cfy.pass_logger
@cfy.pass_client()
def blueprints(target_field, sub_field, logger, client, tenant_name,
               all_tenants):
    """Retrieve summary of blueprints, e.g. a count of each blueprint with
    the same tenant name.

    `TARGET_FIELD` is the field to summarise blueprints on.
    """
    utils.explicit_tenant_name_message(tenant_name, logger)
    logger.info('Retrieving summary of blueprints on field {field}'.format(
        field=target_field))

    summary = client.summary.blueprints.get(
        _target_field=target_field,
        _sub_field=sub_field,
        _all_tenants=all_tenants,
    )

    columns, items = _structure_results_and_columns(
        summary.items,
        target_field,
        sub_field,
        'blueprints',
    )

    print_data(
        columns,
        items,
        'Blueprint summary by {field}'.format(field=target_field),
    )
