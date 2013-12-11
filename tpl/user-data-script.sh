#!/bin/bash

function find_replace(){{
    sed -i.bak -r -e "s|$2|$3|g" $1
}}

function add_line(){{
    sed -i.bak -r -e "$2 i\\$3" $1
}}

touch /etc/sudoers.tmp
cp /etc/sudoers /tmp/sudoers.new
find_replace /tmp/sudoers.new "Defaults    requiretty" "Defaults    !requiretty"
visudo -c -f /tmp/sudoers.new
if [ "$?" -eq "0" ]; then
    cp /tmp/sudoers.new /etc/sudoers
fi
rm /etc/sudoers.tmp

wget http://springdale.princeton.edu/data/puias/6.4/x86_64/os/RPM-GPG-KEY-puias
mkdir -p /etc/pki/rpm-gpg
mv RPM-GPG-KEY-puias /etc/pki/rpm-gpg/RPM-GPG-KEY-puias
mkdir -p {yum_repos_dir}
mv -f /puias.repo {yum_repos_dir}/puias.repo
yum -y install python-devel gcc httpd mod_wsgi python-reportlab python-imaging python-lxml mod_ssl redis openldap-devel
easy_install hiredis python-ldap redis

easy_install indico
echo -e "{indico_inst_dir}\nc\ny\n{db_inst_dir}" | indico_initial_setup

find_replace {httpd_conf_dir}/httpd.conf '#ServerName.*' "ServerName {host_name}"

mkdir -p {ssl_certs_dir}
mkdir -p {ssl_private_dir}
if ! {load_ssl}; then
    openssl req -new -x509 -nodes -out "{ssl_certs_dir}/{ssl_pem_filename}" -keyout "{ssl_private_dir}/{ssl_key_filename}" -days 3650 -subj "/CN={host_name}"
else
    mv -f /{ssl_pem_filename} {ssl_certs_dir}/{ssl_pem_filename}
    mv -f /{ssl_key_filename} {ssl_private_dir}/{ssl_key_filename}
fi
add_line {iptables_path} 11 "-A INPUT -m state --state NEW -m tcp -p tcp --dport {http_port} -j ACCEPT"
add_line {iptables_path} 12 "-A INPUT -m state --state NEW -m tcp -p tcp --dport {https_port} -j ACCEPT"
service iptables restart
for idir in 'archive' 'cache' 'htdocs' 'log' 'tmp'
do
    semanage fcontext -a -t httpd_sys_content_t "{indico_inst_dir}/$idir(/.*)?"
done
semanage fcontext -a -t httpd_sys_content_t "{db_inst_dir}(/.*)?"
restorecon -Rv {indico_inst_dir}
restorecon -Rv {db_inst_dir}
setsebool -P httpd_can_network_connect 1

mkdir -p {httpd_confd_dir} {indico_inst_dir}/etc /etc
mv -f /indico_httpd.conf {httpd_confd_dir}/indico.conf
mv -f /indico_indico.conf {indico_inst_dir}/etc/indico.conf
mv -f /redis.conf /etc/redis.conf
mv -f /ssl.conf {httpd_confd_dir}/ssl.conf

touch /etc/sudoers.tmp
cp /etc/sudoers /tmp/sudoers.new
find_replace /tmp/sudoers.new "Defaults    !requiretty" "Defaults    requiretty"
visudo -c -f /tmp/sudoers.new
if [ "$?" -eq "0" ]; then
    cp /tmp/sudoers.new /etc/sudoers
fi
rm /etc/sudoers.tmp
