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

def _update_params(ssl_pem_path=env.ssl_pem_path, ssl_key_path=env.ssl_key_path):
    """
    Updates the parameters with the passed arguments
    """

    env.ssl_pem_path = ssl_pem_path
    env.ssl_key_path = ssl_key_path

def _putl(source_file, dest_dir):
    """
    To be used instead of put, since it doesn't support symbolic links
    """

    put(source_file, '/')
    run("mv -f /{0} {1}".format(os.path.basename(source_file), dest_dir))

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
