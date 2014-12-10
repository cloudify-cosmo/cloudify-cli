Commands
========

There are two flags that can be used for all operations:
 * --verbose: prints the traceback and prints the events in verbose mode (a full event json)
 * --debug: sets all loggers declared in the `config <https://github.com/cloudify-cosmo/cloudify-cli/blob/master/cloudify_cli/resources/config.yaml>`_ file to debug mode.

      In particular, sets the rest client logger to debug mode, this means that the output will include http communication with the rest server (response, requests and headers).

cfy
---
.. argparse::
   :module: cloudify_cli.cli
   :func: register_commands
   :prog: cfy

   init
      Initializing a configuration for a specific provider is a deprecated feature and will be removed in a future version.

   bootstrap
      The command takes care of provisioning the resources and installing the packages required for the Cloudify Manager to function.

      .. note:: The command also allows you to run validations without actually bootstrapping to verify that the resources required are available for the bootstrap process.

   status
      The command prints out the currently active manager's IP address and a status of the active manager's running services.

   dev
      Cloudify's CLI provides an interface to running premade [fabric](http://www.fabfile.org/) tasks on the management server.

      This supplies an easy way to run personalized, complex ssh scripts on the manager without having to manually connect to it.

      .. note:: The tasks don't have to be decorated with the `@task` decorator as they're directly called from the cli's code just like any other python function. Also, as fabric is one of the cli's dependencies, you don't have to install it separately unless you're using the cli as a binary in which case you'll have to install fabric yourself.

      Example:

      .. code-block:: bash

       cfy dev --tasks-file my_tasks.py -v -t my_task -a --arg1=something --arg2=otherthing ...
       cfy dev -v -t my_task -a arg1_value arg2_value ...

      `--tasks-file my_tasks.py` can be omitted if a `tasks.py` file exists in your current working directory.

      So for instance, if you want to echo `something` in your currently running manager, all you have to do is supply a tasks.py file with the following:

      .. code-block:: python

       from fabric.api import run

       def echo(text):
          run('echo {0}'.format(text))

      and then run:

      .. code-block:: bash

       cfy dev echo something!

      Cloudify provides a tasks `repo <https://github.com/cloudify-cosmo/cloudify-cli-fabric-tasks>`_ from which users can obtain tasks and to which developers should contribute for the benefit of all.

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
