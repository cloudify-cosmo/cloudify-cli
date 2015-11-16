#!/bin/bash -e


function install_requirements() {
    pip install wheel==0.24.0
    pip install s3cmd==1.5.2
}

function download_wheels() {
    pip wheel --wheel-dir packaging/source/wheels https://github.com/cloudify-cosmo/cloudify-cli/archive/$CORE_TAG_NAME.zip#egg=cloudify-cli \
    https://github.com/cloudify-cosmo/cloudify-rest-client/archive/$CORE_TAG_NAME.zip#egg=cloudify-rest-client \
    https://github.com/cloudify-cosmo/cloudify-dsl-parser/archive/$CORE_TAG_NAME.zip#egg=cloudify-dsl-parser \
    https://github.com/cloudify-cosmo/cloudify-plugins-common/archive/$CORE_TAG_NAME.zip#egg=cloudify-plugins-common \
    https://github.com/cloudify-cosmo/cloudify-script-plugin/archive/$PLUGINS_TAG_NAME.zip#egg=cloudify-script-plugin
}

function download_resources() {
    mkdir -p packaging/source/{pip,python,virtualenv,blueprints}
    pushd packaging/source/pip
    curl -O https://dl.dropboxusercontent.com/u/407576/cfy-win-cli-package-resources/pip/get-pip.py
    curl -O https://dl.dropboxusercontent.com/u/407576/cfy-win-cli-package-resources/pip/pip-6.1.1-py2.py3-none-any.whl
    curl -O https://dl.dropboxusercontent.com/u/407576/cfy-win-cli-package-resources/pip/setuptools-15.2-py2.py3-none-any.whl
    popd
    pushd packaging/source/python
    curl -O https://dl.dropboxusercontent.com/u/407576/cfy-win-cli-package-resources/python/python.msi
    popd
    pushd packaging/source/virtualenv
    curl -O https://dl.dropboxusercontent.com/u/407576/cfy-win-cli-package-resources/virtualenv/virtualenv-12.1.1-py2.py3-none-any.whl
    popd
    pushd packaging/source/blueprints
    curl --fail http://cloudify-public-repositories.s3.amazonaws.com/cloudify-manager-blueprints/$CORE_TAG_NAME/cloudify-manager-blueprints.tar.gz -o /tmp/cloudify-manager-blueprints.tar.gz
    tar -zxvf /tmp/cloudify-manager-blueprints.tar.gz --strip-components=1
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


# VERSION/PRERELEASE/BUILD must be exported as they are being read as an env var by the install wizard
export VERSION="3.3.0"
export PRERELEASE="None" && [ "$PRERELEASE" == "None" ] && export PRERELEASE="ga"
export BUILD="300"
CORE_TAG_NAME="3.3"
PLUGINS_TAG_NAME="1.3"

AWS_ACCESS_KEY_ID=$1
AWS_ACCESS_KEY=$2
AWS_S3_BUCKET="gigaspaces-repository-eu"
AWS_S3_PATH="org/cloudify3/${VERSION}/${PRERELEASE}-RELEASE"

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
download_wheels &&
download_resources &&
iscc packaging/create_install_wizard.iss &&
cd /home/Administrator/packaging/output/ && md5sum=$(md5sum -t *.exe) && echo $md5sum > ${md5sum##* }.md5 &&
[ -z ${AWS_ACCESS_KEY} ] || upload_to_s3 "*.exe" && upload_to_s3 "*.md5"
