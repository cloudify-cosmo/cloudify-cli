#!/bin/bash -e

function install_requirements() {
    pip install wheel==0.24.0
}

function download_wheels() {
    GITHUB_USERNAME=$1
    GITHUB_PASSWORD=$2

    mkdir -p packaging/source/wheels
    curl -LO https://pypi.python.org/packages/2.7/l/lxml/lxml-3.5.0.win32-py2.7.exe
    wheel convert lxml-3.5.0.win32-py2.7.exe --dest-dir packaging/source/wheels

    PATCH_URL="https://raw.githubusercontent.com/cloudify-cosmo/cloudify-cli/${CLI_BRANCH}/packaging/omnibus/config/patches/cloudify-cli/cloudify_cli.patch"
    curl -sLO https://github.com/cloudify-cosmo/cloudify-cli/archive/${CLI_BRANCH}.zip
    unzip -q -o ${CLI_BRANCH}.zip
    [[ -f ${CLI_BRANCH}.zip ]] && rm -f ${CLI_BRANCH}.zip
    curl -sL "${PATCH_URL}" -o cloudify-cli-${CLI_BRANCH}/cloudify_cli.patch
    patch -p1 -d cloudify-cli-${CLI_BRANCH} < cloudify-cli-${CLI_BRANCH}/cloudify_cli.patch
    rm -f cloudify-cli-${CLI_BRANCH}/cloudify_cli.patch
    zip -q -r cloudify-cli-${CLI_BRANCH}.zip cloudify-cli-${CLI_BRANCH}
    [[ $? -eq 0 ]] && rm -rf cloudify-cli-${CLI_BRANCH}

    pip wheel --wheel-dir packaging/source/wheels --find-links packaging/source/wheels C:/Cygwin/home/Administrator/cloudify-cli-${CLI_BRANCH}.zip \
    https://github.com/cloudify-cosmo/cloudify-common/archive/${CORE_BRANCH}.zip#egg=cloudify-common \
    https://github.com/cloudify-cosmo/cloudify-fabric-plugin/archive/1.5.2.zip#egg=cloudify-fabric-plugin

    # Rename "Bad" wheels
    pushd packaging/source/wheels
        for file in *cp27m*; do
            a="$(echo $file | sed s/-cp27m-/-none-/)"
            mv -v "$file" "$a"
        done
    popd

}

function download_resources() {

    GITHUB_USERNAME=$1
    GITHUB_PASSWORD=$2

    mkdir -p packaging/source/{python,types,scripts,plugins}
    pushd packaging/source/python
        curl -L http://gigaspaces-repository-eu.s3.amazonaws.com/org/cloudify3/components/Python279_x32.tar.gz -o /tmp/Python279_x32.tar.gz
        tar -zxvf /tmp/Python279_x32.tar.gz --strip-components=1
    popd

    # Downloading types.yaml
    pushd packaging/source/types
        curl -LO http://www.getcloudify.org/spec/cloudify/${CORE_TAG_NAME}/types.yaml
    popd

    # Downloading Scripts
    pushd packaging/source/scripts
        curl -LO https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager/${CORE_BRANCH}/resources/rest-service/cloudify/fs/mkfs.sh
        curl -LO https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager/${CORE_BRANCH}/resources/rest-service/cloudify/fs/fdisk.sh
        curl -LO https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager/${CORE_BRANCH}/resources/rest-service/cloudify/fs/mount.sh
        curl -LO https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager/${CORE_BRANCH}/resources/rest-service/cloudify/fs/unmount.sh
        curl -LO https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager/${CORE_BRANCH}/resources/rest-service/cloudify/policies/host_failure.clj
        curl -LO https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager/${CORE_BRANCH}/resources/rest-service/cloudify/policies/threshold.clj
        curl -LO https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager/${CORE_BRANCH}/resources/rest-service/cloudify/policies/ewma_stabilized.clj
        curl -LO https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager/${CORE_BRANCH}/resources/rest-service/cloudify/triggers/execute_workflow.clj
    popd

    # Downloading plugin yamls
    pushd packaging/source/plugins
        mkdir -p {fabric-plugin,script-plugin,diamond-plugin,openstack-plugin,aws-plugin,vsphere-plugin,softlayer-plugin}

        curl -L https://raw.githubusercontent.com/cloudify-cosmo/cloudify-fabric-plugin/1.5.2/plugin.yaml -o fabric-plugin/plugin.yaml
        curl -L https://raw.githubusercontent.com/cloudify-cosmo/cloudify-diamond-plugin/1.3.17/plugin.yaml -o diamond-plugin/plugin.yaml
        curl -L https://raw.githubusercontent.com/cloudify-cosmo/cloudify-openstack-plugin/2.0.1/plugin.yaml -o openstack-plugin/plugin.yaml
        curl -L https://raw.githubusercontent.com/cloudify-cosmo/cloudify-aws-plugin/1.4.10/plugin.yaml -o aws-plugin/plugin.yaml
        curl -L https://$GITHUB_USERNAME:$GITHUB_PASSWORD@raw.githubusercontent.com/cloudify-cosmo/cloudify-softlayer-plugin/1.3.1/plugin.yaml -o softlayer-plugin/plugin.yaml

        # Downloading commercial plugin yamls
        curl -L https://raw.githubusercontent.com/cloudify-cosmo/cloudify-vsphere-plugin/2.4.0/plugin.yaml -o vsphere-plugin/plugin.yaml
    popd
}

function update_remote_to_local_links() {
    sed -i -e 's/https:\/\/raw\.githubusercontent\.com\/cloudify-cosmo\/cloudify-manager\/.*\/resources\/rest-service\/cloudify\/.*\//file:\/cfy\/cloudify\/scripts\//g' packaging/source/types/types.yaml
}

# VERSION/PRERELEASE/BUILD/CORE_BRANCH/PLUGINS_TAG_NAME must be exported as they are being read as an env var by the install wizard

export GITHUB_USERNAME=$1
export GITHUB_PASSWORD=$2
export AWS_ACCESS_KEY_ID=$3
export AWS_ACCESS_KEY=$4
export REPO=$5
export BRANCH=$6
export CORE_TAG_NAME="4.5.5.dev1"
export CORE_BRANCH="18.10.18-build"

curl -u $GITHUB_USERNAME:$GITHUB_PASSWORD https://raw.githubusercontent.com/cloudify-cosmo/${REPO}/${CORE_BRANCH}/packages-urls/common_build_env.sh -o ./common_build_env.sh &&
source common_build_env.sh &&
curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-common/${CORE_BRANCH}/packaging/common/provision.sh -o ./common-provision.sh &&
source common-provision.sh

export CLI_BRANCH="$CORE_BRANCH"
if [ "$CORE_BRANCH" != "master" ] && [ "$REPO" == "cloudify-versions" ]; then
    source packaging/source_branch
fi
if [[ ! -z $BRANCH ]] && [[ "$BRANCH" != "master" ]];then
    pushd /tmp
        curl -sLO https://github.com/cloudify-cosmo/cloudify-cli/archive/${BRANCH}.zip
        if zip -T $BRANCH.zip > /dev/null; then
            export CLI_BRANCH="$BRANCH"
            AWS_S3_PATH="$AWS_S3_PATH/$BRANCH"
        fi
    popd
fi
install_common_prereqs &&
#install_requirements && # moved to cloudify-common
download_wheels $GITHUB_USERNAME $GITHUB_PASSWORD &&
download_resources $GITHUB_USERNAME $GITHUB_PASSWORD &&
update_remote_to_local_links &&
iscc packaging/create_install_wizard.iss &&
cd /home/Administrator/packaging/output/ && create_md5 "exe"  &&
[ -z ${AWS_ACCESS_KEY} ] || upload_to_s3 "exe" && upload_to_s3 "md5"
