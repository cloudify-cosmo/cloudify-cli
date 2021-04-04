import json
from mock import Mock
from collections import OrderedDict

from cloudify_rest_client import blueprints, deployments

from cloudify_cli.labels_utils import labels_list_to_set
from cloudify_cli.cli.cfy import get_formatted_labels_list
from cloudify_cli.exceptions import (LabelsValidationError,
                                     CloudifyValidationError)


from .test_base import CliCommandTest
from .constants import SAMPLE_ARCHIVE_PATH

LABELS = [
    {'key': 'key1', 'value': 'val ue', 'created_at': '1', 'creator_id': 0},
    {'key': 'key2', 'value': 'val\xf3ue', 'created_at': '2', 'creator_id': 0},
    {'key': 'key2', 'value': 'val,ue ', 'created_at': '2', 'creator_id': 0},
]

LABELED_BLUEPRINT = blueprints.Blueprint({
    'blueprint_id': 'bp1',
    'labels': LABELS
})

LABELED_DEPLOYMENT = deployments.Deployment({
    'deployment_id': 'dep1',
    'labels': LABELS
})


class LabelsFunctionalityTest(CliCommandTest):
    __test__ = True

    def setUp(self):
        super(LabelsFunctionalityTest, self).setUp()

    def test_formatting_labels_list_success(self):
        matching_labels = OrderedDict([
                ('3key:value', {'3key': 'value'}),
                ('key:val ue', {'key': 'val ue'}),
                ('key:val\\,ue', {'key': 'val,ue'}),
                ('ke-y:val\\:ue ', {'ke-y': 'val:ue '}),
                ('k_e.y:12val34. \\,ue', {'k_e.y': '12val34. ,ue'}),
                (' key:val\xf3u\\:e', {'key': 'val\xf3u:e'})])

        labels_str = ','.join(matching_labels.keys())
        formatted_labels_list = get_formatted_labels_list(labels_str)
        self.assertEqual(formatted_labels_list, list(matching_labels.values()))

    def test_null_label_fails(self):
        with self.assertRaisesRegex(CloudifyValidationError, 'control char'):
            get_formatted_labels_list('key:val\x00ue')

    def test_invalid_label_key_fails(self):
        with self.assertRaisesRegex(LabelsValidationError, 'key contains'):
            get_formatted_labels_list('ke&y:value')

    def test_invalid_label_value_fails(self):
        with self.assertRaisesRegex(CloudifyValidationError, 'control char'):
            get_formatted_labels_list('key:val"ue')

    def test_no_colons_in_labels_fails(self):
        with self.assertRaisesRegex(LabelsValidationError, 'form <key>'):
            get_formatted_labels_list('key-value')

    def test_multiple_colons_in_labels_fails(self):
        with self.assertRaisesRegex(LabelsValidationError, 'form <key>'):
            get_formatted_labels_list('key:val:ue')

    def test_missing_label_key_fails(self):
        with self.assertRaisesRegex(LabelsValidationError, 'form <key>'):
            get_formatted_labels_list(':value')

    def test_missing_label_value_fails(self):
        with self.assertRaisesRegex(LabelsValidationError, 'form <key>'):
            get_formatted_labels_list('key:')


class LabelsTest(CliCommandTest):
    __test__ = False

    def setUp(self, resource, create_resource_cmd):
        super(LabelsTest, self).setUp()
        self.use_manager()
        self.create_resource_cmd = create_resource_cmd
        self.labels_cmd = 'cfy ' + resource + ' labels'

    def test_resource_create_failure_with_invalid_labels(self):
        self.invoke(self.create_resource_cmd + ' --labels key:',
                    err_str_segment='form <key>',
                    exception=LabelsValidationError)

        self.invoke(self.create_resource_cmd + ' --labels "key:val\tue"',
                    err_str_segment='control char',
                    exception=CloudifyValidationError)

        self.invoke(self.create_resource_cmd + ' --labels ke&y:value',
                    err_str_segment='key contains',
                    exception=LabelsValidationError)

    def test_resource_labels_delete_failure_with_invalid_label(self):
        self.invoke(
            self.labels_cmd + ' delete key1:val1,key2:val2 res',
            err_str_segment='<key>:<value> or <key>',
            exception=CloudifyValidationError)

        self.invoke(self.labels_cmd + ' delete ke&y res',
                    err_str_segment='key contains illegal',
                    exception=LabelsValidationError)

        self.invoke(self.labels_cmd + ' delete key:"val\tue" res',
                    err_str_segment='control char',
                    exception=CloudifyValidationError)

        self.invoke(self.labels_cmd + ' delete :value res',
                    err_str_segment='form <key>',
                    exception=LabelsValidationError)


class DeploymentsLabelsTest(LabelsTest):
    __test__ = True

    def setUp(self):
        super(DeploymentsLabelsTest, self).setUp(
            'deployments',
            'cfy deployments create -b bp1 dep1')

    def test_deployment_create_with_labels(self):
        self.client.deployments.create = Mock()
        self.invoke('cfy deployments create -b bp1 dep1 '
                    '--labels key1:val1,key2:val2')
        call_args = list(self.client.deployments.create.call_args)
        self.assertEqual(call_args[1]['labels'],
                         [{'key1': 'val1'}, {'key2': 'val2'}])

    def test_deployment_labels_list(self):
        self.client.deployments.get = Mock(return_value=LABELED_DEPLOYMENT)
        raw_outcome = self.invoke('cfy deployments labels list dep1 --json')
        labels = json.loads(raw_outcome.output)
        self.assertEqual(labels,  {'key1': ['val ue'],
                                   'key2': ['val\xf3ue', 'val,ue ']})

    def test_deployment_labels_add(self):
        self.client.deployments.get = Mock(return_value=LABELED_DEPLOYMENT)
        self.client.deployments.update_labels = Mock()
        self.invoke('cfy deployments labels add '
                    'key1:"val ue",key2:"value ",key3:"val\\:" dep1')
        call_args = list(self.client.deployments.update_labels.call_args)
        self.assertEqual(labels_list_to_set(call_args[0][1]),
                         labels_list_to_set([{'key1': 'val ue'},
                                             {'key2': 'value '},
                                             {'key2': 'val\xf3ue'},
                                             {'key2': 'val,ue '},
                                             {'key3': 'val:'}]))

    def test_resource_labels_delete_label(self):
        self.client.deployments.get = Mock(return_value=LABELED_DEPLOYMENT)
        self.client.deployments.update_labels = Mock()
        self.invoke('cfy deployments labels delete key2:"val\\,ue " dep1')
        call_args = list(self.client.deployments.update_labels.call_args)
        self.assertEqual(labels_list_to_set(call_args[0][1]),
                         labels_list_to_set([{'key1': 'val ue'},
                                             {'key2': 'val\xf3ue'}]))

    def test_deployment_labels_delete_key(self):
        self.client.deployments.get = Mock(return_value=LABELED_DEPLOYMENT)
        self.client.deployments.update_labels = Mock()
        self.invoke('cfy deployments labels delete key2 dep1')
        call_args = list(self.client.deployments.update_labels.call_args)
        self.assertEqual(call_args[0][1], [{'key1': 'val ue'}])


class BlueprintsLabelsTest(LabelsTest):
    __test__ = True

    def setUp(self):
        super(BlueprintsLabelsTest, self).setUp(
            'blueprints',
            'cfy blueprints upload {0} -b bp1 '.format(SAMPLE_ARCHIVE_PATH))

    def test_blueprint_upload_with_labels(self):
        self.client.license.check = Mock()
        self.mock_wait_for_blueprint_upload(False)
        cmd = 'cfy blueprints upload {0} -b bp1 '.format(SAMPLE_ARCHIVE_PATH)
        self.client.blueprints.upload = Mock()
        self.invoke(cmd + '--labels key1:val1,key2:val2')
        call_args = list(self.client.blueprints.upload.call_args)
        self.assertEqual(call_args[1]['labels'],
                         [{'key1': 'val1'}, {'key2': 'val2'}])

    def test_blueprint_labels_list(self):
        self.client.blueprints.get = Mock(return_value=LABELED_BLUEPRINT)
        raw_outcome = self.invoke('cfy blueprints labels list bp1 --json')
        labels = json.loads(raw_outcome.output)
        self.assertEqual(labels, {'key1': ['val ue'],
                                  'key2': ['val\xf3ue', 'val,ue ']})

    def test_blueprint_labels_add(self):
        self.client.blueprints.get = Mock(return_value=LABELED_BLUEPRINT)
        self.client.blueprints.update = Mock()
        self.invoke('cfy blueprints labels add '
                    'key1:"val ue",key2:"value ",key3:"val\\:" bp1')
        call_args = list(self.client.blueprints.update.call_args)
        self.assertEqual(labels_list_to_set(call_args[0][1]['labels']),
                         labels_list_to_set([{'key1': 'val ue'},
                                             {'key2': 'value '},
                                             {'key2': 'val\xf3ue'},
                                             {'key2': 'val,ue '},
                                             {'key3': 'val:'}]))

    def test_blueprint_labels_delete_label(self):
        self.client.blueprints.get = Mock(return_value=LABELED_BLUEPRINT)
        self.client.blueprints.update = Mock()
        self.invoke('cfy blueprints labels delete key2:"val\\,ue " bp1')
        call_args = list(self.client.blueprints.update.call_args)
        self.assertEqual(labels_list_to_set(call_args[0][1]['labels']),
                         labels_list_to_set([{'key1': 'val ue'},
                                             {'key2': 'val\xf3ue'}]))

    def test_blueprint_labels_delete_key(self):
        self.client.blueprints.get = Mock(return_value=LABELED_BLUEPRINT)
        self.client.blueprints.update = Mock()
        self.invoke('cfy blueprints labels delete key2 bp1')
        call_args = list(self.client.blueprints.update.call_args)
        self.assertEqual(call_args[0][1]['labels'], [{'key1': 'val ue'}])
