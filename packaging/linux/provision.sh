#/bin/bash -e

CORE_TAG_NAME="3.4m4"
NEW_TAG_NAME="3.4.0_m4"
curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-packager/$CORE_TAG_NAME/common/provision.sh -o ./common-provision.sh &&
source common-provision.sh

GITHUB_USERNAME=$1
GITHUB_PASSWORD=$2
AWS_ACCESS_KEY_ID=$3
AWS_ACCESS_KEY=$4
BRANCH=$5

rm -rf cloudify-cli
git clone https://github.com/cloudify-cosmo/cloudify-cli.git
cd cloudify-cli/packaging/omnibus
git checkout $BRANCH
git tag -d $CORE_TAG_NAME
git tag $NEW_TAG_NAME
omnibus build cloudify && result="success"
cd pkg
rm -f *.json
[ $(ls | grep rpm) ] && FILEEXT="rpm"
[ $(ls | grep deb) ] && FILEEXT="deb"

echo "creating md5"
[ "$result" == "success" ] && create_md5 $FILEEXT &&
echo "uploading to s3"
[ -z ${AWS_ACCESS_KEY} ] || upload_to_s3 $FILEEXT && upload_to_s3 "md5"

