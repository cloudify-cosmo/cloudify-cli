#/bin/bash -e

function install_prereqs
{
    if which yum; then
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
    sudo yum install -y rpm-build redhat-rpm-config
    sudo yum install -y python-devel gcc
    sudo mkdir -p /root/rpmbuild/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
    sudo cp /vagrant/linux/build.spec /root/rpmbuild/SPECS
    sudo rpmbuild -ba /root/rpmbuild/SPECS/build.spec \
        --define "GITHUB_USERNAME $GITHUB_USERNAME" \
        --define "GITHUB_PASSWORD $GITHUB_PASSWORD" \
        --define "DISTRO $DISTRO" \
        --define "RELEASE $RELEASE"
}

function upload_to_s3() {
    path=$1
    files=$2

    sudo pip install s3cmd==1.5.2
    cd /tmp/x86_64
    sudo s3cmd put --force --acl-public --access_key=${AWS_ACCESS_KEY_ID} --secret_key=${AWS_ACCESS_KEY} \
        --no-preserve --progress --human-readable-sizes --check-md5 *.rpm* s3://${AWS_S3_BUCKET}/${VERSION}/
}

GITHUB_USERNAME=$1
GITHUB_PASSWORD=$2
AWS_ACCESS_KEY_ID=$3
AWS_ACCESS_KEY=$4
AWS_S3_BUCKET='gigaspaces-repository-eu/org/cloudify3'

VERSION='2.2.0'
# these are propagated and used in the build.spec file to name the package.
DISTRO=$(python -c "import platform; print platform.linux_distribution(full_distribution_name=False)[0]")
RELEASE=$(python -c "import platform; print platform.linux_distribution(full_distribution_name=False)[2]")


if which yum; then
    if ! which python2.7 >> /dev/null; then
        install_py27
    else
        alias python=python2.7
    fi
    build_rpm
fi

# this should be used AFTER renaming the cli packages to contain versions.
# generate md5 file.
md5sum=$(md5sum *.tar.gz)
echo $md5sum | sudo tee ${md5sum##* }_${VERSION}.md5

if [ ! -z ${AWS_ACCESS_KEY} ]; then
    upload_to_s3
fi
