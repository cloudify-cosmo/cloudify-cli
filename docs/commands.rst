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

dev
---
Cloudify's CLI provides an interface to running premade [fabric](http://www.fabfile.org/) tasks on the management server.

This supplies an easy way to run personalized, complex ssh scripts on the manager without having to manually connect to it.

.. note:: The tasks must run in the context of the `cfy` command (That is, under the virtualenv Cloudify's CLI is installed) and in the directory .cloudify is in.

.. note:: The tasks don't have to be decorated with the `@task` decorator as they're directly called from the cli's code just like any other python function. Also, as fabric is one of the cli's dependencies, you don't have to install it separately unless you're using the cli as a binary in which case you'll have to install fabric yourself.

.. argparse::
   :module: cloudify_cli.cli
   :func: register_commands
   :prog: cfy
   :path: dev

Example:

.. code-block:: bash

 cfy dev --tasks-file my_tasks.py -v my_task --arg1=something --arg2=otherthing ...
 cfy dev -v my_task arg1_value arg2_value ...

`--tasks-file my_tasks.py` can be omitted if a `tasks.py` file exists in your current working directory.

So for instance, if you want to echo `something` in your currently running manager, all you have to do is supply a tasks.py file with the following:

.. code-block:: python

 from fabric.api import run

 def echo(text):
    run('echo {0}'.format(text))

and then run:

.. code-block:: bash

 cfy dev echo something!


.. note:: The `dev` command doesn't appear in cfy by default when running `cfy -h`. You can run `cfy dev -h` for a command reference.

Cloudify provides a tasks `repo <https://github.com/cloudify-cosmo/cloudify-cli-fabric-tasks>`_ from which users can obtain tasks and to which developers should contribute for the benefit of all.