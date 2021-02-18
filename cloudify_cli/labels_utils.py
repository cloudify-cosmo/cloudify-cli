import json

from .table import print_data
from .utils import explicit_tenant_name_message
from .logger import CloudifyJSONEncoder, get_global_json_output, output


def modify_resource_labels(resource_list):
    for element in resource_list:
        resource_labels_list = []
        for raw_label in element.get('labels', []):
            resource_labels_list.append(raw_label.key + ':' + raw_label.value)
        element['labels'] = ','.join(resource_labels_list)


def list_labels(resource_id,
                resource_name,
                resource_client,
                logger,
                tenant_name):
    explicit_tenant_name_message(tenant_name, logger)
    logger.info('Listing labels of %s %s...', resource_name, resource_id)

    resource_labels = {}
    raw_resource_labels = resource_client.get(resource_id)['labels']
    for label in raw_resource_labels:
        label_key, label_value = label['key'], label['value']
        resource_labels.setdefault(label_key, [])
        resource_labels[label_key].append(label_value)

    printable_resource_labels = [
        {'key': resource_label_key, 'values': resource_label_values} for
        resource_label_key, resource_label_values in resource_labels.items()
    ]

    if get_global_json_output():
        output(json.dumps(resource_labels, cls=CloudifyJSONEncoder))
    else:
        print_data(['key', 'values'],
                   printable_resource_labels,
                   '{0} labels'.format(resource_name.capitalize()),
                   max_width=50)


def add_labels(resource_id,
               resource_name,
               resource_client,
               labels_list,
               logger,
               tenant_name):
    explicit_tenant_name_message(tenant_name, logger)
    logger.info('Adding labels to %s %s...', resource_name, resource_id)

    resource_labels = _get_resource_labels(resource_client, resource_id)
    curr_labels_set = labels_list_to_set(resource_labels)
    provided_labels_set = labels_list_to_set(labels_list)

    new_labels = provided_labels_set.difference(curr_labels_set)
    if new_labels:
        updated_labels = _labels_set_to_list(
            curr_labels_set.union(provided_labels_set))
        if resource_name == 'deployment':
            resource_client.update_labels(resource_id, updated_labels)
        elif resource_name == 'blueprint':
            resource_client.update(resource_id, {'labels': updated_labels})
        logger.info(
            'The following label(s) were added successfully to %s %s: %s',
            resource_name, resource_id, _labels_set_to_list(new_labels))
    else:
        logger.info('The provided labels are already assigned to %s %s. '
                    'No labels were added.', resource_name, resource_id)


def delete_labels(resource_id,
                  resource_name,
                  resource_client,
                  label,
                  logger,
                  tenant_name):
    explicit_tenant_name_message(tenant_name, logger)
    logger.info('Deleting labels from %s %s...', resource_name, resource_id)
    resource_labels = _get_resource_labels(resource_client, resource_id)

    updated_labels = []
    labels_to_delete = []
    if isinstance(label, dict):
        if label in resource_labels:
            labels_to_delete = [label]
            resource_labels.remove(label)
            updated_labels = resource_labels
    else:  # A label key was provided
        for resource_label in resource_labels:
            if label in resource_label:
                labels_to_delete.append(resource_label)
            else:
                updated_labels.append(resource_label)

    if labels_to_delete:
        if resource_name == 'deployment':
            resource_client.update_labels(resource_id, updated_labels)
        elif resource_name == 'blueprint':
            resource_client.update(resource_id, {'labels': updated_labels})
        logger.info('The following label(s) were deleted successfully from %s '
                    '%s: %s', resource_name, resource_id, labels_to_delete)
    else:
        logger.info('The provided labels are not assigned to %s %s. No '
                    'labels were deleted.', resource_name, resource_id)


def _get_resource_labels(resource_client, resource_id):
    raw_resource_labels = resource_client.get(resource_id)['labels']
    return [{resource_label['key']: resource_label['value']}
            for resource_label in raw_resource_labels]


def _labels_set_to_list(labels_set):
    return [{key: value} for key, value in labels_set]


def labels_list_to_set(labels_list):
    labels_set = set()
    for label in labels_list:
        [(key, value)] = label.items()
        labels_set.add((key, value))

    return labels_set
