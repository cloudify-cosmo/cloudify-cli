set -e

[[ -z "${CLOUDIFY_VERSION}" ]] || [[ -z "${CLOUDIFY_PACKAGE_RELEASE}" ]] && {
	echo "CLOUDIFY_VERSION and CLOUDIFY_PACKAGE_RELEASE must be set"
	exit 1
}
[[ -z "${PROJECT_DIR}" ]] && {
	echo "PROJECT_DIR must be set to the directory containing the CLI code"
	exit 1
}
[[ -z "${RESULT_DIR}" ]] && {
	echo "RESULT_DIR must be set to the directory where the built deb will be moved"
	exit 1
}
set -xu

BUILD_DIR=~/cloudify-cli_${CLOUDIFY_VERSION}-${CLOUDIFY_PACKAGE_RELEASE}_amd64

apt-get update
apt-get install python python-virtualenv git -y
mkdir -p "${BUILD_DIR}/DEBIAN" "${BUILD_DIR}/opt"
cat >"${BUILD_DIR}/DEBIAN/control" <<EOF
Package: cloudify
Version: ${CLOUDIFY_VERSION}
Section: base
Priority: optional
Architecture: amd64
Depends: python (>= 2.7)
Maintainer: Cloudify Platform Ltd. <cosmo-admin@cloudify.co>
Description: Cloudify's Command Line Interface
EOF
virtualenv /opt/cfy
/opt/cfy/bin/pip install -r "${PROJECT_DIR}/dev-requirements.txt"
/opt/cfy/bin/pip install "${PROJECT_DIR}"
cp /opt/cfy "${BUILD_DIR}/opt/cfy" -fr

mkdir -p "${BUILD_DIR}/usr/bin"
ln -s "/opt/cfy/bin/cfy" "${BUILD_DIR}/usr/bin/cfy"

dpkg-deb --build "${BUILD_DIR}"
mv ~/*.deb "${RESULT_DIR}"
