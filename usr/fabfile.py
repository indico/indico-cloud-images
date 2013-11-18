from fabric.api import *
from fabric.contrib.files import sed
from fabric.operations import put, run
from fabric.main import load_settings
import os

env.conf = 'fabfile.conf'

settings = load_settings(env.conf)
if not settings:
    raise RuntimeError("Configuration file {0} is needed!".format(env.conf))
env.update(settings)

env.hosts = ["{0}@{1}:{2}".format(env.user_name, env.host_name, env.host_port)]

env.db_inst_dir = os.path.join(env.indico_inst_dir, env.db_inst_dirname)
env.indico_conf_dir = os.path.join(env.indico_inst_dir, env.indico_conf_dirname)

env.ssl_certs_dir = os.path.join(env.ssl_dir, env.ssl_certs_dirname)
env.ssl_private_dir = os.path.join(env.ssl_dir, env.ssl_private_dirname)

def _update_params(host_name=env.host_name, http_port=env.http_port, https_port=env.https_port,
                   ssl_pem_path=env.ssl_pem_path, ssl_key_path=env.ssl_key_path):
    """
    Updates the parameters with the passed arguments
    """
    env.host_name = host_name
    env.hosts[0] = "{0}@{1}:{2}".format(env.user_name, env.host_name, env.host_port)
    env.http_port = http_port
    env.https_port = https_port
    env.ssl_pem_path = ssl_pem_path
    env.ssl_key_path = ssl_key_path

def _putl(source_file, dest_dir):
    """
    To be used instead of put, since it doesn't support symbolic links
    """

    put(source_file, '/')
    run("mv -f /{0} {1}".format(os.path.basename(source_file), dest_dir))

@task
def config(host_name=env.host_name, http_port=env.http_port, https_port=env.https_port,
           ssl_pem_path=env.ssl_pem_path, ssl_key_path=env.ssl_key_path):
    """
    Configure the VM with all the necessary information
    """

    load_ssl(ssl_pem_path, ssl_key_path)
    update_host_name(host_name)
    update_http_port(http_port)
    update_https_port(https_port)

@task
def load_ssl(ssl_pem_path=env.ssl_pem_path, ssl_key_path=env.ssl_key_path):
    """
    Load a personal SSL certificate into the VM
    """

    _update_params(ssl_pem_path=ssl_pem_path, ssl_key_path=ssl_key_path)

    # Copy the new certificate
    _putl(env.ssl_pem_path, env.ssl_certs_dir)
    _putl(env.ssl_key_path, env.ssl_private_dir)

    # Modify the indico.conf SSL entries
    sed(os.path.join(env.httpd_confd_dir, 'indico.conf'), \
        "{0}.*.pem".format(env.ssl_certs_dir), \
        os.path.join(env.ssl_certs_dir, os.path.basename(env.ssl_pem_path)))
    sed(os.path.join(env.httpd_confd_dir, 'indico.conf'), \
        "{0}.*.key".format(env.ssl_private_dir), \
        os.path.join(env.ssl_private_dir, os.path.basename(env.ssl_key_path)))

@task
def update_host_name(host_name = env.host_name):
    """
    Change the host name of the Indico Server
    """

    _update_params(host_name=host_name)

    # Replacing the ServerName in httpd.conf
    sed(os.path.join(env.httpd_conf_dir, 'httpd.conf'), \
        '#ServerName.*', "ServerName {0}".format(env.host_name))

    # Modifying the hostname in indico.conf
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'), \
        'BaseURL.*', \
        "BaseURL              = \"http://{0}:{1}/indico\"" \
        .format(env.host_name, env.http_port))
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'), \
        'BaseSecureURL.*', \
        "BaseSecureURL        = \"https://{0}:{1}/indico\"" \
        .format(env.host_name, env.https_port))
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'), \
        'LoginURL.*', \
        "LoginURL             = \"https://{0}:{1}/indico/signIn.py\"" \
        .format(env.host_name, env.https_port))

@task
def update_http_port(http_port=env.http_port):
    """
    Change the http port
    """

    _update_params(http_port=http_port)

    # Modifying the http port in indico.conf
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'), \
        'BaseURL.*', \
        "BaseURL              = \"http://{0}:{1}/indico\"" \
        .format(env.host_name, env.http_port))
    run("sed -i.bak -r -e \"11s|.*|-A INPUT -m state --state NEW -m tcp -p tcp --dport {0} -j ACCEPT|g\" {1}" \
        .format(env.http_port, os.path.join(env.iptables_dir, 'iptables')))

@task
def update_https_port(https_port=env.https_port):
    """
    Change the https port
    """

    _update_params(https_port=https_port)

    # Modifying the https port in indico.conf
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'), \
        'BaseSecureURL.*', \
        "BaseSecureURL        = \"https://{0}:{1}/indico\"" \
        .format(env.host_name, env.https_port))
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'), \
        'LoginURL.*', \
        "LoginURL             = \"https://{0}:{1}/indico/signIn.py\"" \
        .format(env.host_name, env.https_port))
    run("sed -i.bak -r -e \"12s|.*|-A INPUT -m state --state NEW -m tcp -p tcp --dport {0} -j ACCEPT|g\" {1}" \
        .format(env.https_port, os.path.join(env.iptables_dir, 'iptables')))
