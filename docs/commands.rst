Commands
========

The ``-v/--verbose`` flag is available for all commands. It sets the command verbosity level. At the moment, there are 4 verbosity levels:

* Running a command without the verbose flag. (This is obviously the default).
* Running a command with ``-v`` will print tracebacks where relevant, in addition to the normal output.
* Running a command with ``-vv`` will, in addition, show ``DEBUG`` log statements of local/remote execution events.
* Running a command with ``-vvv`` will, in addition, set all loggers declared in the
  `config <https://github.com/cloudify-cosmo/cloudify-cli/blob/3.4/cloudify_cli/resources/config.yaml>`_ file to debug mode.

.. note::
  ``--debug`` is equivalent to ``-vvv``


Inputs and Parameters
      All commands that accept inputs or paramaters (e.g. "cfy execute" or "cfy deployments create") expect the value to represent a dictionary. Valid formats are:
 * A path to the YAML file
 * A string formatted as YAML
 * A string formatted as "key1=value1;key2=value2"

cfy
---
.. argparse::
   :module: cloudify_cli.cli
   :func: register_commands
   :prog: cfy

   init
      Initializes CLI configuration files and work environment in the current working directory.

   bootstrap
      The command takes care of creating the topology and installing the Cloudify Manager to function.

      .. note:: The command also allows you to run validations without actually bootstrapping to verify that the resources required are available for the bootstrap process.

   status
      The command prints out the currently active manager's IP address and a status of the active manager's running services.

   dev
      Cloudify's CLI provides an interface to running premade `fabric <http://www.fabfile.org/>`_ tasks on the management server.

      This supplies an easy way to run personalized, complex ssh scripts on the manager without having to manually connect to it.

      .. note:: The tasks don't have to be decorated with the ``@task`` decorator as they're directly called from the cli's code just like any other python function. Also, as fabric is one of the cli's dependencies, you don't have to install it separately unless you're using the cli as a binary in which case you'll have to install fabric yourself.

      Example:

      .. code-block:: bash

       cfy dev --tasks-file my_tasks.py -v -t my_task -a --arg1=something --arg2=otherthing ...
       cfy dev -v -t my_task -a arg1_value arg2_value ...

      ``--tasks-file my_tasks.py`` can be omitted if a ``tasks.py`` file exists in your current working directory.

      So for instance, if you want to echo ``something`` in your currently running manager, all you have to do is supply a ``tasks.py`` file with the following:

      .. code-block:: python

       from fabric.api import run

       def echo(text):
          run('echo {0}'.format(text))

      and then run:

      .. code-block:: bash

       cfy dev -t echo -a something

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
