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

    pip wheel --wheel-dir packaging/source/wheels --find-links packaging/source/wheels https://github.com/cloudify-cosmo/cloudify-cli/archive/$CORE_TAG_NAME.zip#egg=cloudify-cli \
    https://github.com/cloudify-cosmo/cloudify-rest-client/archive/$CORE_TAG_NAME.zip#egg=cloudify-rest-client \
    https://github.com/cloudify-cosmo/cloudify-dsl-parser/archive/$CORE_TAG_NAME.zip#egg=cloudify-dsl-parser \
    https://github.com/cloudify-cosmo/cloudify-plugins-common/archive/$CORE_TAG_NAME.zip#egg=cloudify-plugins-common \
    https://github.com/cloudify-cosmo/cloudify-script-plugin/archive/$PLUGINS_TAG_NAME.zip#egg=cloudify-script-plugin \
    https://github.com/cloudify-cosmo/cloudify-fabric-plugin/archive/$PLUGINS_TAG_NAME.zip#egg=cloudify-fabric-plugin \
    https://github.com/cloudify-cosmo/cloudify-openstack-plugin/archive/$PLUGINS_TAG_NAME.zip#egg=cloudify-openstack-plugin \
    https://github.com/cloudify-cosmo/cloudify-aws-plugin/archive/$PLUGINS_TAG_NAME.zip#egg=cloudify-aws-plugin \
    https://github.com/cloudify-cosmo/tosca-vcloud-plugin/archive/$PLUGINS_TAG_NAME.zip#egg=cloudify-vcloud-plugin \
    https://$GITHUB_USERNAME:$GITHUB_PASSWORD@github.com/cloudify-cosmo/cloudify-vsphere-plugin/archive/$PLUGINS_TAG_NAME.zip#egg=cloudify-vsphere-plugin \
    https://$GITHUB_USERNAME:$GITHUB_PASSWORD@github.com/cloudify-cosmo/cloudify-softlayer-plugin/archive/$PLUGINS_TAG_NAME.zip#egg=cloudify-softlayer-plugin
}

function download_resources() {

    GITHUB_USERNAME=$1
    GITHUB_PASSWORD=$2

    mkdir -p packaging/source/{pip,python,virtualenv,blueprints,types,scripts,plugins}
    pushd packaging/source/pip
        curl -LO https://dl.dropboxusercontent.com/u/407576/cfy-win-cli-package-resources/pip/get-pip.py
        curl -LO https://dl.dropboxusercontent.com/u/407576/cfy-win-cli-package-resources/pip/pip-6.1.1-py2.py3-none-any.whl
        curl -LO https://dl.dropboxusercontent.com/u/407576/cfy-win-cli-package-resources/pip/setuptools-15.2-py2.py3-none-any.whl
    popd
    pushd packaging/source/python
        curl -LO https://dl.dropboxusercontent.com/u/407576/cfy-win-cli-package-resources/python/python.msi
    popd
    pushd packaging/source/virtualenv
        curl -LO https://dl.dropboxusercontent.com/u/407576/cfy-win-cli-package-resources/virtualenv/virtualenv-12.1.1-py2.py3-none-any.whl
    popd
    pushd packaging/source/blueprints
        curl -L https://github.com/cloudify-cosmo/cloudify-manager-blueprints/archive/$CORE_TAG_NAME.tar.gz -o /tmp/cloudify-manager-blueprints.tar.gz
        tar -zxvf /tmp/cloudify-manager-blueprints.tar.gz --strip-components=1
    popd

    # Downloading types.yaml
    pushd packaging/source/types
        curl -LO http://getcloudify.org.s3.amazonaws.com/spec/cloudify/$CORE_TAG_NAME/types.yaml
    popd

    # Downloading Scripts
    pushd packaging/source/scripts
        curl -LO https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager/$CORE_TAG_NAME/resources/rest-service/cloudify/fs/mkfs.sh
        curl -LO https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager/$CORE_TAG_NAME/resources/rest-service/cloudify/fs/fdisk.sh
        curl -LO https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager/$CORE_TAG_NAME/resources/rest-service/cloudify/fs/mount.sh
        curl -LO https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager/$CORE_TAG_NAME/resources/rest-service/cloudify/fs/unmount.sh
        curl -LO https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager/$CORE_TAG_NAME/resources/rest-service/cloudify/policies/host_failure.clj
        curl -LO https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager/$CORE_TAG_NAME/resources/rest-service/cloudify/policies/threshold.clj
        curl -LO https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager/$CORE_TAG_NAME/resources/rest-service/cloudify/policies/ewma_stabilized.clj
        curl -LO https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager/$CORE_TAG_NAME/resources/rest-service/cloudify/triggers/execute_workflow.clj
    popd

    # Downloading plugin yamls
    pushd packaging/source/plugins
        mkdir -p {fabric-plugin,script-plugin,diamond-plugin,openstack-plugin,aws-plugin,tosca-vcloud-plugin,vsphere-plugin,softlayer-plugin}

        curl -L https://raw.githubusercontent.com/cloudify-cosmo/cloudify-fabric-plugin/$PLUGINS_TAG_NAME/plugin.yaml -o fabric-plugin/plugin.yaml
        curl -L https://raw.githubusercontent.com/cloudify-cosmo/cloudify-script-plugin/$PLUGINS_TAG_NAME/plugin.yaml -o script-plugin/plugin.yaml
        curl -L https://raw.githubusercontent.com/cloudify-cosmo/cloudify-diamond-plugin/$PLUGINS_TAG_NAME/plugin.yaml -o diamond-plugin/plugin.yaml
        curl -L https://raw.githubusercontent.com/cloudify-cosmo/cloudify-openstack-plugin/$PLUGINS_TAG_NAME/plugin.yaml -o openstack-plugin/plugin.yaml
        curl -L https://raw.githubusercontent.com/cloudify-cosmo/cloudify-aws-plugin/$PLUGINS_TAG_NAME/plugin.yaml -o aws-plugin/plugin.yaml
        curl -L https://raw.githubusercontent.com/cloudify-cosmo/tosca-vcloud-plugin/$PLUGINS_TAG_NAME/plugin.yaml -o tosca-vcloud-plugin/plugin.yaml

        # Downloading commercial plugin yamls
        curl -L https://$GITHUB_USERNAME:$GITHUB_PASSWORD@raw.githubusercontent.com/cloudify-cosmo/cloudify-vsphere-plugin/1.3rc1/plugin.yaml -o vsphere-plugin/plugin.yaml
        curl -L https://$GITHUB_USERNAME:$GITHUB_PASSWORD@raw.githubusercontent.com/cloudify-cosmo/cloudify-softlayer-plugin/1.3rc1/plugin.yaml -o softlayer-plugin/plugin.yaml
    popd
}

function upload_to_s3() {
    ###
    # This will upload both the artifact and md5 files to the relevant bucket.
    # Note that the bucket path is also appended the version.
    ###
    # no preserve is set to false only because preserving file attributes is not yet supported on Windows.

    file=$(basename $(find . -type f -name "$1"))
    date=$(date +"%a, %d %b %Y %T %z")
    acl="x-amz-acl:public-read"
    content_type='application/x-compressed-exe'
    string="PUT\n\n$content_type\n$date\n$acl\n/$AWS_S3_BUCKET/$AWS_S3_PATH/$file"
    signature=$(echo -en "${string}" | openssl sha1 -hmac "${AWS_ACCESS_KEY}" -binary | base64)
    curl -v -X PUT -T "$file" \
      -H "Host: $AWS_S3_BUCKET.s3.amazonaws.com" \
      -H "Date: $date" \
      -H "Content-Type: $content_type" \
      -H "$acl" \
      -H "Authorization: AWS ${AWS_ACCESS_KEY_ID}:$signature" \
      "https://$AWS_S3_BUCKET.s3.amazonaws.com/$AWS_S3_PATH/$file"
}

function update_remote_to_local_links() {
    sed -i -e 's/https:\/\/raw\.githubusercontent\.com\/cloudify-cosmo\/cloudify-manager\/.*\/resources\/rest-service\/cloudify\/.*\//file:\/cfy\/cloudify\/scripts\//g' packaging/source/types/types.yaml
}

# VERSION/PRERELEASE/BUILD/CORE_TAG_NAME/PLUGINS_TAG_NAME must be exported as they are being read as an env var by the install wizard
export VERSION="3.4.0"
export PRERELEASE="m1"
export BUILD="390"
export CORE_TAG_NAME="3.4m1"
export PLUGINS_TAG_NAME="1.3.1"

GITHUB_USERNAME=$1
GITHUB_PASSWORD=$2

AWS_ACCESS_KEY_ID=$3
AWS_ACCESS_KEY=$4
AWS_S3_BUCKET="gigaspaces-repository-eu"
AWS_S3_PATH="org/cloudify3/${VERSION}/${PRERELEASE}"

echo "VERSION: ${VERSION}"
echo "PRERELEASE: ${PRERELEASE}"
echo "BUILD: ${BUILD}"
echo "CORE_TAG_NAME: ${CORE_TAG_NAME}"
echo "PLUGINS_TAG_NAME: ${PLUGINS_TAG_NAME}"
echo "AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID}"
echo "AWS_ACCESS_KEY: ${AWS_ACCESS_KEY}"
echo "AWS_S3_BUCKET: ${AWS_S3_BUCKET}"
echo "AWS_S3_PATH: ${AWS_S3_PATH}"


install_requirements &&
download_wheels $GITHUB_USERNAME $GITHUB_PASSWORD &&
download_resources $GITHUB_USERNAME $GITHUB_PASSWORD &&
update_remote_to_local_links &&
iscc packaging/create_install_wizard.iss &&
cd /home/Administrator/packaging/output/ && md5sum=$(md5sum -t *.exe) && echo $md5sum > ${md5sum##* }.md5 &&
[ -z ${AWS_ACCESS_KEY} ] || upload_to_s3 "*.exe" && upload_to_s3 "*.md5"
