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
echo -e "# INDICO_INST_DIR #\nc\ny\n# DB_INST_DIR #" | indico_initial_setup

# -------------------- #
# Indico configuration #
# -------------------- #
find_replace # HTTPD_CONF_DIR #/httpd.conf '#ServerName.*' "ServerName # HOST_NAME #"

# ----------------------------- #
# Virtual Machine configuration #
# ----------------------------- #
mkdir -p # SSL_CERTS_DIR #
mkdir -p # SSL_PRIVATE_DIR #
if !# LOAD_SSL #; then
    openssl openssl req -new -x509 -nodes -out "# SSL_PEM_PATH #" -keyout "# SSL_KEY_PATH #" -days 3650 -subj "/CN=# HOST_NAME #"
fi
add_line # IPTABLES_PATH # 11 "-A INPUT -m state --state NEW -m tcp -p tcp --dport # HTTP_PORT # -j ACCEPT"
add_line # IPTABLES_PATH # 12 "-A INPUT -m state --state NEW -m tcp -p tcp --dport # HTTPS_PORT # -j ACCEPT"
service iptables restart
for idir in 'archive' 'cache' 'htdocs' 'log' 'tmp'
do
    semanage fcontext -a -t httpd_sys_content_t "# INDICO_INST_DIR #/$idir(/.*)?"
done
semanage fcontext -a -t httpd_sys_content_t "# DB_INST_DIR #(/.*)?"
restorecon -Rv # INDICO_INST_DIR #
restorecon -Rv # DB_INST_DIR #
setsebool -P httpd_can_network_connect 1
