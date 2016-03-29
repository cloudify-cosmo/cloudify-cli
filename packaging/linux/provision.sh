#/bin/bash -e

function install_prereqs
{
    if which yum >> /dev/null; then
        sudo yum -y --exclude=kernel\* update &&
        sudo yum install -y yum-downloadonly wget mlocate yum-utils
        sudo yum install -y python-devel libyaml-devel make gcc g++ libxml2-devel libxslt-devel
    else
        echo 'unsupported package manager, exiting'
        exit 1
    fi
}

function install_py27
{
    # install python and additions
    # http://bicofino.io/blog/2014/01/16/installing-python-2-dot-7-6-on-centos-6-dot-5/
    sudo yum groupinstall -y 'development tools'
    sudo yum install -y zlib-devel bzip2-devel openssl-devel xz-libs
    sudo mkdir /py27
    cd /py27
    sudo wget http://www.python.org/ftp/python/2.7.6/Python-2.7.6.tar.xz
    sudo xz -d Python-2.7.6.tar.xz
    sudo tar -xvf Python-2.7.6.tar
    cd Python-2.7.6
    sudo ./configure --prefix=/usr
    sudo make
    sudo make altinstall
    if which python2.7; then
        alias python=python2.7
    fi
}

function build_rpm() {
    # these are propagated and used in the build.spec file to name the package.
    DISTRO=$(python -c "import platform; print platform.linux_distribution(full_distribution_name=False)[0]")
    RELEASE=$(python -c "import platform; print platform.linux_distribution(full_distribution_name=False)[2]")

    sudo yum install -y rpm-build redhat-rpm-config
    sudo yum install -y python-devel gcc
    sudo mkdir -p /root/rpmbuild/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
    sudo cp /vagrant/linux/build.spec /root/rpmbuild/SPECS
    sudo rpmbuild -ba /root/rpmbuild/SPECS/build.spec \
        --define "GITHUB_USERNAME $GITHUB_USERNAME" \
        --define "GITHUB_PASSWORD $GITHUB_PASSWORD" \
        --define "DISTRO $DISTRO" \
        --define "RELEASE $RELEASE" \
        --define "VERSION $VERSION" \
        --define "PRERELEASE $PRERELEASE" \
        --define "BUILD $BUILD" \
        --define "CORE_TAG_NAME $CORE_TAG_NAME" \
        --define "PLUGINS_TAG_NAME $PLUGINS_TAG_NAME"
    # This is the UGLIEST HACK EVER!
    # Since rpmbuild spec files cannot receive a '-' in their version,
    # we do this... thing and replace an underscore with a dash.
    # cd /tmp/x86_64 &&
    # sudo mv *.rpm $(ls *.rpm | sed 's|_|-|g')
}


CORE_TAG_NAME="3.4m3"
curl https://raw.githubusercontent.com/cloudify-cosmo/cloudify-packager/$CORE_TAG_NAME/common/provision.sh -o ./common-provision.sh &&
source common-provision.sh

GITHUB_USERNAME=$1
GITHUB_PASSWORD=$2
AWS_ACCESS_KEY_ID=$3
AWS_ACCESS_KEY=$4


if which yum; then
    if which python2.7 >> /dev/null; then
        alias python=python2.7
    else
        install_py27
    fi
    build_rpm && rpm_result="success"
fi

[ "$rpm_result" == "success" ] && cd /tmp/x86_64 && create_md5 "rpm" &&
[ -z ${AWS_ACCESS_KEY} ] || upload_to_s3 "rpm" && upload_to_s3 "md5"
