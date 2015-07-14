from cloudify_cli.logger import get_logger
import importlib
import yaml

def test_environment(plugin_name, inputs):
    logger = get_logger()

    try:
        plugin = importlib.import_module(
            plugin_name
            )
    except ImportError:
        logger.error(
            'Could not import {plugin}- did you pip install it?'.format(
            plugin=plugin_name)
            )

    if hasattr(plugin, 'test_environment'):
        if inputs is not None:
            with open(inputs) as inputs_handle:
                inputs = inputs_handle.read()
            inputs = yaml.load(inputs)
        else:
            inputs = {}
        plugin.test_environment(inputs)
    else:
        logger.error(
            '{plugin} does not support environment testing yet. '
            'It should have a test_environment method which accepts an '
            'inputs dictionary.'.format(plugin=plugin_name)
            )
