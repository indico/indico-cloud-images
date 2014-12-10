#!/bin/bash

echo "indico-cloud-init: start config"

function find_replace(){{
    sed -i.bak -r -e "s|$2|$3|g" $1
}}

if {enable_networking}; then
    # Enable networking (CentOS 7 cloud images)
    mv /ifcfg-ens3 /etc/sysconfig/network-scripts/ifcfg-ens3
    service network restart
fi

# Install EPEL 7 (needed for Redis)
yum -y install wget
wget http://dl.fedoraproject.org/pub/epel/7/x86_64/e/epel-release-7-2.noarch.rpm
rpm -Uvh epel-release-7*.rpm
rm epel-release-7*.rpm

touch /etc/sudoers.tmp
cp /etc/sudoers /tmp/sudoers.new
find_replace /tmp/sudoers.new "Defaults    requiretty" "Defaults    !requiretty"
visudo -c -f /tmp/sudoers.new
if [ "$?" -eq "0" ]; then
    cp /tmp/sudoers.new /etc/sudoers
fi
rm /etc/sudoers.tmp

# Install RHEL/CentOS dependencies
yum -y install iptables-services python-devel python-virtualenv gcc httpd mod_wsgi python-reportlab python-imaging mod_ssl redis openldap-devel libffi-devel libxml-devel libxslt-devel

# Create Indico base dir
mkdir -p {indico_inst_dir}

# Create/load virtualenv
virtualenv {indico_inst_dir}/env
. {indico_inst_dir}/env/bin/activate

# Install Python dependencies and Indico
easy_install --always-unzip python-ldap
easy_install --always-unzip indico

# Silly hack, due to some eggs modifying themselves in run-time
chown -R apache:apache {indico_inst_dir}/env/lib/python2.7/site-packages/

# Configure Indico
echo -e "{indico_inst_dir}\nc\ny\n{db_inst_dir}" | indico_initial_setup

# Configure Apache HTTPD
find_replace {httpd_conf_dir}/httpd.conf '#ServerName.*' "ServerName {host_name}"

mkdir -p {ssl_certs_dir}
mkdir -p {ssl_private_dir}

# Load certificate if passed
if ! {load_ssl}; then
    openssl req -new -x509 -nodes -out "{ssl_certs_dir}/{ssl_pem_filename}" -keyout "{ssl_private_dir}/{ssl_key_filename}" -days 3650 -subj "/CN={host_name}"
else
    mv -f /{ssl_pem_filename} {ssl_certs_dir}/{ssl_pem_filename}
    mv -f /{ssl_key_filename} {ssl_private_dir}/{ssl_key_filename}
fi

# Set up iptables
iptables -A INPUT -p tcp -m tcp --dport 22 -j ACCEPT
iptables -A INPUT -p tcp -m tcp --dport 80 -j ACCEPT
iptables -A INPUT -p tcp -m tcp --dport 443 -j ACCEPT

service iptables save
service iptables restart

# Setup postfix if needed
if {postfix}; then
    echo "resolve_numeric_domain = yes" >> /etc/postfix/main.cf
    find_replace /etc/postfix/master.cf ".*      inet  n       -       n       -       -       smtpd" "{smtp_server_port}      inet  n       -       n       -       -       smtpd"
fi

# Properly configure SELinux

for idir in 'archive' 'cache' 'htdocs' 'log' 'tmp'
do
    semanage fcontext -a -t httpd_sys_content_t "{indico_inst_dir}/$idir(/.*)?"
done
semanage fcontext -a -t httpd_sys_content_t "{db_inst_dir}(/.*)?"
restorecon -Rv {indico_inst_dir}
restorecon -Rv {db_inst_dir}
setsebool -P httpd_can_network_connect 1

# Copy config files to their places
mkdir -p {httpd_confd_dir} {indico_inst_dir}/etc /etc
mv -f /indico_httpd.conf {httpd_confd_dir}/indico.conf
mv -f /indico_indico.conf {indico_inst_dir}/etc/indico.conf
mv -f /redis.conf /etc/redis.conf

echo '# Nothing to see here' > /etc/httpd/conf.d/welcome.conf

touch /etc/sudoers.tmp
cp /etc/sudoers /tmp/sudoers.new
find_replace /tmp/sudoers.new "Defaults    !requiretty" "Defaults    requiretty"
visudo -c -f /tmp/sudoers.new
if [ "$?" -eq "0" ]; then
    cp /tmp/sudoers.new /etc/sudoers
fi
rm /etc/sudoers.tmp

echo "indico-cloud-init: config done"
