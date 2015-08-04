#!/usr/bin/env bash

function state_error
{
    echo "ERROR: ${1:-UNKNOWN} (status $?)" 1>&2
    exit 1
}

PKG_NAME="{{ name }}"
PKG_DIR="{{ sources_path }}"
VERSION="{{ version }}"

echo -e "\nInstalling ${PKG_NAME} version ${VERSION}...\n"

function check_pip
{
    if ! which pip >> /dev/null; then
        state_error "pip not in path. Please verify that pip is installed and is in the path."
    fi
}

function install_virtualenv
{
    if ! which virtualenv >> /dev/null; then
        echo "Installing Virtualenv..."
        pip install --use-wheel --no-index --find-links=${PKG_DIR}/wheelhouse virtualenv
    fi
}

function install_cloudify
{
    echo "Creating Virtualenv /cfy/env..."
    virtualenv /cfy/env &&
    if ! which cfy >> /dev/null; then
        /cfy/env/bin/pip install --use-wheel --no-index --find-links=${PKG_DIR}/wheelhouse cloudify --pre
        /cfy/env/bin/pip install --use-wheel --no-index --find-links=${PKG_DIR}/wheelhouse cloudify-vsphere-plugin --pre
        /cfy/env/bin/pip install --use-wheel --no-index --find-links=${PKG_DIR}/wheelhouse cloudify-softlayer-plugin --pre
        /cfy/env/bin/pip install --use-wheel --no-index --find-links=${PKG_DIR}/wheelhouse cloudify-fabric-plugin --pre
        /cfy/env/bin/pip install --use-wheel --no-index --find-links=${PKG_DIR}/wheelhouse cloudify-openstack-plugin --pre
        /cfy/env/bin/pip install --use-wheel --no-index --find-links=${PKG_DIR}/wheelhouse cloudify-aws-plugin --pre
        # when the cli is built for py2.6, unless argparse is put within `install_requires`, we'll have to enable this:
        # if which yum; then
        #   /cfy/env/bin/pip install --use-wheel --no-index --find-links=${PKG_DIR}/wheelhouse argparse=#SOME_VERSION#
        # fi
    else
        state_error "Cloudify's CLI appears to be installed already and is in your path."
    fi
}

check_pip &&
# Questionable. Do we want to install virtualenv for the user if it isn't already installed?
install_virtualenv &&
install_cloudify &&

echo "Cleaning up..."
rm -rf ${PKG_DIR}/wheelhouse &&

echo -e "${PKG_NAME} ${VERSION} Installation completed successfully!\n"
