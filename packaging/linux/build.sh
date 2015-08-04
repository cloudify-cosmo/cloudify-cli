#/bin/bash

function install_prereqs
{
    if which yum; then
        sudo yum -y --exclude=kernel\* update &&
        sudo yum install -y yum-downloadonly wget mlocate yum-utils s3cmd
        sudo yum install -y python-devel libyaml-devel make gcc g++ git rpm-build libxml2-devel libxslt-devel
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

function build() {
    sudo yum install -y rpm-build redhat-rpm-config
    sudo mkdir -p /root/rpmbuild/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
    sudo cp /vagrant/linux/build.spec /root/rpmbuild/SPECS
    sudo rpmbuild -ba /root/rpmbuild/SPECS/build.spec --define "GITHUB_USERNAME $GITHUB_USERNAME" --define "GITHUB_PASSWORD $GITHUB_PASSWORD"
}

function upload_to_s3() {
    s3cmd -d --access_key=${AWS_ACCESS_KEY_ID} --secret_key=${AWS_SECRET_KEY} --progress -H -p --check-md5 --continue-put put /cloudify/* s3://${AWS_S3_BUCKET}/${AWS_S3_BUCKET_PREFIX}
}

GITHUB_USERNAME=$1
GITHUB_PASSWORD=$2
AWS_ACCESS_KEY_ID=$3
AWS_ACCESS_KEY=$4
AWS_S3_BUCKET = 'gigaspaces-repository-eu'
AWS_S3_BUCKET_PREFIX = 'org/cloudify3/'


if which yum; then
    if ! which python2.7 >> /dev/null; then
        install_py27
    else
        alias python=python2.7
    fi
fi

build

if [ ! -z ${AWS_ACCESS_KEY} ]; then
    upload_to_s3
fi