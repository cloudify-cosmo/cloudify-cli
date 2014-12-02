Commands
========

There are two flags that can be used for all operations:
 * --verbose: prints the stack trace
 * --debug: sets all loggers declared in the `config <https://github.com/cloudify-cosmo/cloudify-cli/blob/master/cloudify_cli/resources/config.yaml>`_ file to debug mode.

      In particular, sets the rest client logger to debug mode, this means that the output will include headers.

cfy
---
.. argparse::
   :module: cloudify_cli.cli
   :func: register_commands
   :prog: cfy

blueprints
----------
.. argparse::
   :module: cloudify_cli.cli
   :func: register_commands
   :prog: cfy
   :path: blueprints

deployments
-----------
.. argparse::
   :module: cloudify_cli.cli
   :func: register_commands
   :prog: cfy
   :path: deployments

executions
----------
.. argparse::
   :module: cloudify_cli.cli
   :func: register_commands
   :prog: cfy
   :path: executions

local
-----
.. argparse::
   :module: cloudify_cli.cli
   :func: register_commands
   :prog: cfy
   :path: local

events
------
.. argparse::
   :module: cloudify_cli.cli
   :func: register_commands
   :prog: cfy
   :path: events

workflows
---------
.. argparse::
   :module: cloudify_cli.cli
   :func: register_commands
   :prog: cfy
   :path: workflows
