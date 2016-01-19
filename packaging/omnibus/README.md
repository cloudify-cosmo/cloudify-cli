cloudify Omnibus project
========================
This project creates full-stack platform-specific packages for
`cloudify`!

Installation
------------
You must have a sane Ruby 1.9+ environment with Bundler installed. Ensure all
the required gems are installed:

```shell
$ bundle install --binstubs
```

Usage
-----
### Build

You create a platform-specific package using the `build project` command:

```shell
$ bin/omnibus build cloudify
```

The platform/architecture type of the package created will match the platform
where the `build project` command is invoked. For example, running this command
on a MacBook Pro will generate a Mac OS X package. After the build completes
packages will be available in the `pkg/` folder.

### Clean

You can clean up all temporary files generated during the build process with
the `clean` command:

```shell
$ bin/omnibus clean cloudify
```

Adding the `--purge` purge option removes __ALL__ files generated during the
build including the project install directory (`/opt/cloudify`) and
the package cache directory (`/var/cache/omnibus/pkg`):

```shell
$ bin/omnibus clean cloudify --purge
```

### Publish

Omnibus has a built-in mechanism for releasing to a variety of "backends", such
as Amazon S3. You must set the proper credentials in your `omnibus.rb` config
file or specify them via the command line.

```shell
$ bin/omnibus publish path/to/*.deb --backend s3
```

### Help

Full help for the Omnibus command line interface can be accessed with the
`help` command:

```shell
$ bin/omnibus help
```

Version Manifest
----------------

Git-based software definitions may specify branches as their
default_version. In this case, the exact git revision to use will be
determined at build-time unless a project override (see below) or
external version manifest is used.  To generate a version manifest use
the `omnibus manifest` command:

```
omnibus manifest PROJECT -l warn
```

This will output a JSON-formatted manifest containing the resolved
version of every software definition.


Kitchen-based Build Environment
-------------------------------
Every Omnibus project ships will a project-specific
[Berksfile](http://berkshelf.com/) that will allow you to build your omnibus projects on all of the projects listed
in the `.kitchen.yml`. You can add/remove additional platforms as needed by
changing the list found in the `.kitchen.yml` `platforms` YAML stanza.

This build environment is designed to get you up-and-running quickly. However,
there is nothing that restricts you to building on other platforms. Simply use
the [omnibus cookbook](https://github.com/opscode-cookbooks/omnibus) to setup
your desired platform and execute the build steps listed above.

The default build environment requires Test Kitchen and VirtualBox for local
development. Test Kitchen also exposes the ability to provision instances using
various cloud providers like AWS, DigitalOcean, or OpenStack. For more
information, please see the [Test Kitchen documentation](http://kitchen.ci).

Once you have tweaked your `.kitchen.yml` (or `.kitchen.local.yml`) to your
liking, you can bring up an individual build environment using the `kitchen`
command.

```shell
$ bin/kitchen converge ubuntu-1204
```

Then login to the instance and build the project as described in the Usage
section:

```shell
$ bundle exec kitchen login ubuntu-1204
[vagrant@ubuntu...] $ cd cloudify
[vagrant@ubuntu...] $ bundle install
[vagrant@ubuntu...] $ ...
[vagrant@ubuntu...] $ bin/omnibus build cloudify
```

For a complete list of all commands and platforms, run `kitchen list` or
`kitchen help`.


cloudify-windows Omnibus project
================================
This project creates full-stack platform-specific packages for
`cloudify-windows` using Amazon EC2.  UPDATE the .kitchen.yml with the appropriate security group, key, etc... (CHANGEME sections)
The userdata will create vagrant/vagrant user/password in the instance as well as install chocolatey/cygwin/cyg-get and winsshd (to rsync) for test guests with the addition of visual c++ for python27 on the build guest.  There are some issues auto-building compared to nix/mac so see below:

Usage
-----
### Build

Create a platform-specific package:

```shell

#**********#
# REQUIRED # Edit the .kitchen.yml and specify correct values for subnet, key, security-group, etc.
#**********#

# create instance and get IP address for rsync
NAME=ms
bundle exec kitchen create ${NAME} && BUILD_IP=$(bundle exec kitchen diagnose ${NAME} | awk -F': ' '/hostname:/{print $2}')

# due to folder not synced, so until rsync is working for aws windows rsync
# manually (user/pass vagrant/vagrant):
rsync -av -e 'ssh -o StrictHostKeyChecking=no' --exclude=.git --exclude=.kitchen . vagrant@${BUILD_IP}:/cygdrive/c/vagrant

# build
bundle exec kitchen converge ${NAME}

# clean pkg dir then copy pkg dir with msi from build guest to local
rm -f pkg/*
rsync -av -e ssh vagrant@${BUILD_IP}:/cygdrive/c/vagrant/pkg .

# destroy msi builder instance
bundle exec kitchen destroy ${NAME}

```
### Test

Test install the package:

```shell

#**********#
# REQUIRED # Edit the .kitchen.yml and specify correct values for subnet, key, security-group, etc.
#**********#

# create instance and get IP address for rsync
NAME=cloudify-win
bundle exec kitchen create ${NAME} && TEST_IP=$(bundle exec kitchen diagnose ${NAME} | awk -F': ' '/hostname:/{print $2}')

# this will sync the pkg folder containing the msi
# mod perms then copy pkg dir with msi from local to install guest
chmod 755 pkg/cloudify-*msi
rsync -av -e 'ssh -o StrictHostKeyChecking=no' pkg vagrant@${TEST_IP}:/cygdrive/c/Users/vagrant/

# install
bundle exec kitchen converge ${NAME}

# run serverspec tests (verify)
bundle exec kitchen verify ${NAME}

# destroy msi installer instance
bundle exec kitchen destroy ${NAME}

```
