FROM ubuntu:16.04

ARG ssh_key

ENV SSH_KEY=${ssh_key}

# installing packages using by ssh and some utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    vim \
    xorg \
    openssh-server \
    xauth 

# adding the project
ADD . /dataset-creator
WORKDIR /dataset-creator

# running the bootstrap script for ubuntu 16.04
RUN bash bootstrap.sh

# configure ssh for access the container
RUN mkdir /var/run/sshd \
    && mkdir /root/.ssh \
    && chmod 700 /root/.ssh \
    && ssh-keygen -A \
    && sed -i "s/^.*PasswordAuthentication.*$/PasswordAuthentication no/" /etc/ssh/sshd_config \
    && sed -i "s/^.*X11Forwarding.*$/X11Forwarding yes/" /etc/ssh/sshd_config \
    && sed -i "s/^.*X11UseLocalhost.*$/X11UseLocalhost no/" /etc/ssh/sshd_config \
    && grep "^X11UseLocalhost" /etc/ssh/sshd_config || echo "X11UseLocalhost no" >> /etc/ssh/sshd_config

# adding my public ssh key

RUN echo ${SSH_KEY} >> /root/.ssh/authorized_keys

# entrypoint for access the container and see graphic interface
ENTRYPOINT ["sh", "-c", "/usr/sbin/sshd && tail -f /dev/null"]