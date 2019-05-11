FROM centos:6
RUN yum install -y http://opensource.wandisco.com/centos/6/git/x86_64/wandisco-git-release-6-1.noarch.rpm
RUN yum install -y git fakeroot python-devel rpm-build
RUN yum update -y nss
RUN curl -sSL https://rvm.io/pkuczynski.asc | gpg2 --import -
RUN gpg2 --keyserver hkp://keys.gnupg.net --recv-keys \
        409B6B1796C275462A1703113804BB82D39DC0E3 \
        7D2BAF1CF37B13E2069D6956105BD0E739499BDB
RUN curl -sSL https://get.rvm.io | bash -s stable
RUN /bin/bash -c '''\
    source /etc/profile.d/rvm.sh && \
    rvm install 2.4.4 && rvm use 2.4.4 && \
    gem install bundler -v '=1.16.0' --no-document && \
    gem install mixlib-cli -v 1.7.0 --no-document && \
    gem install ohai -v 14.8.12 --no-document && \
    gem install omnibus -v 6.0.25 --no-document \
'''
RUN yum install sudo -y
