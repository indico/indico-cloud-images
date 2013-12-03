#!/bin/bash

function find_replace(){
    sed -i.bak -r -e "s|$2|$3|g" $1
}

function replace_line(){
    sed -i.bak -r -e "$2 s|.*|$3|g" $1
}

function add_line(){
    sed -i.bak -r -e "$2 i|$3" $1
}

# ------------------------- #
# Dependencies installation #
# ------------------------- #
wget http://springdale.princeton.edu/data/puias/6.4/x86_64/os/RPM-GPG-KEY-puias
mv RPM-GPG-KEY-puias /etc/pki/rpm-gpg/RPM-GPG-KEY-puias
yum -y install python-devel gcc httpd mod_wsgi python-reportlab python-imaging python-lxml mod_ssl redis openldap-devel
easy_install hiredis python-ldap

# ------------------- #
# Indico installation #
# ------------------- #
easy_install indico
echo -e "/opt/indico\nc\ny\n/opt/indico/db" | indico_initial_setup

# -------------------- #
# Indico configuration #
# -------------------- #
find_replace /etc/httpd/conf/httpd.conf '#ServerName.*' "ServerName indico-cloud-test2"

# ----------------------------- #
# Virtual Machine configuration #
# ----------------------------- #
mkdir -p /etc/ssl/certs
mkdir -p /etc/ssl/private
if !0; then
    openssl openssl req -new -x509 -nodes -out "/etc/ssl/certs/self-gen.pem" -keyout "/etc/ssl/private/self-gen.key" -days 3650 -subj "/CN=indico-cloud-test2"
fi
add_line /etc/sysconfig/iptables 11 "-A INPUT -m state --state NEW -m tcp -p tcp --dport 80 -j ACCEPT"
add_line /etc/sysconfig/iptables 12 "-A INPUT -m state --state NEW -m tcp -p tcp --dport 443 -j ACCEPT"
service iptables restart
for idir in 'archive' 'cache' 'htdocs' 'log' 'tmp'
do
    semanage fcontext -a -t httpd_sys_content_t "/opt/indico/$idir(/.*)?"
done
semanage fcontext -a -t httpd_sys_content_t "/opt/indico/db(/.*)?"
restorecon -Rv /opt/indico
restorecon -Rv /opt/indico/db
setsebool -P httpd_can_network_connect 1
