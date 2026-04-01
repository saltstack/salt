FROM debian:bookworm-slim

RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
        openssh-server \
        procps \
        python3 \
        sudo \
        && \
    rm -rf /var/lib/apt/lists/*

# sshd requires /run/sshd to exist
RUN mkdir -p /run/sshd

# Create the salt user.  An unset password is treated as a locked account
# by Debian sshd; setting the hash to '*' marks it as "no password" without
# locking it so that key-based auth is permitted.
RUN useradd -m -s /bin/bash salt && \
    usermod -p '*' salt && \
    mkdir -p /home/salt/.ssh && \
    chmod 700 /home/salt/.ssh

# Grant the salt user passwordless sudo so salt-thin can run pkg.install
RUN echo "salt ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/salt && \
    chmod 440 /etc/sudoers.d/salt

# Inject the host public key as an authorised key
ARG PUBKEY
RUN echo "$PUBKEY" > /home/salt/.ssh/authorized_keys && \
    chmod 600 /home/salt/.ssh/authorized_keys && \
    chown -R salt:salt /home/salt/.ssh

# Harden sshd: key-only auth, no root login, no PAM noise
RUN sed -i \
        -e 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' \
        -e 's/^#\?PermitRootLogin.*/PermitRootLogin no/' \
        -e 's/^#\?UsePAM.*/UsePAM no/' \
        /etc/ssh/sshd_config && \
    echo "AllowUsers salt" >> /etc/ssh/sshd_config

EXPOSE 22

CMD ["/usr/sbin/sshd", "-D", "-e"]
