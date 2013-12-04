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

env.hosts = [env.host_name]

if env.http_port is '80':
    http = ''
else:
    http = ':'+env.http_port
if env.https_port is '443':
    https = ''
else:
    https = ':'+env.http_port
env.ports = [http, https]

env.db_inst_dir = os.path.join(env.indico_inst_dir, env.db_inst_dirname)
env.indico_conf_dir = os.path.join(env.indico_inst_dir, env.indico_conf_dirname)

def _update_params(host_name=env.host_name, http_port=env.http_port, https_port=env.https_port,
                   ssl_pem_path=env.ssl_pem_path, ssl_key_path=env.ssl_key_path,
                   redis_pswd=env.redis_pswd, redis_port=env.redis_port):
    """
    Updates the parameters with the passed arguments
    """
    env.host_name = host_name
    env.hosts[0] = env.host_name
    env.http_port = http_port
    env.https_port = https_port
    env.ssl_pem_path = ssl_pem_path
    env.ssl_key_path = ssl_key_path
    env.redis_pswd = redis_pswd
    env.redis_port = redis_port
    env.ports = _get_ports()

def _putl(source_file, dest_dir):
    """
    To be used instead of put, since it doesn't support symbolic links
    """

    put(source_file, '/')
    run("mv -f /{0} {1}".format(os.path.basename(source_file), dest_dir))

def _get_ports():
    if env.http_port is '80':
        http = ''
    else:
        http = ':'+env.http_port
    if env.https_port is '443':
        https = ''
    else:
        https = ':'+env.http_port
    return [http, https]

@task
def config(host_name=env.host_name, http_port=env.http_port, https_port=env.https_port,
           ssl_pem_path=env.ssl_pem_path, ssl_key_path=env.ssl_key_path,
           redis_pswd=env.redis_pswd, redis_port=env.redis_port):
    """
    Configure the VM with all the necessary information
    """

    load_ssl(ssl_pem_path, ssl_key_path)
    update_server(http_port, https_port)
    update_redis(redis_pswd, redis_port)

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
def update_server(host_name = env.host_name, http_port=env.http_port, https_port=env.https_port):
    """
    Change the server configuration (hostname and ports)
    """

    _update_params(host_name=host_name, http_port=http_port, https_port=https_port)

    sed(os.path.join(env.httpd_conf_dir, 'httpd.conf'), \
        '^ServerName.*', "ServerName {0}".format(env.host_name))

    sed(os.path.join(env.indico_conf_dir, 'indico.conf'), \
        '^BaseURL.*', \
        "BaseURL              = \"http://{0}{1}/indico\"" \
        .format(env.host_name, env.ports[0]))
    run("sed -i.bak -r -e \"11s|.*|-A INPUT -m state --state NEW -m tcp -p tcp --dport {0} -j ACCEPT|g\" {1}" \
        .format(env.http_port, os.path.join(env.iptables_dir, 'iptables')))
    run("sed -i.bak -r -e \"5s|.*|<VirtualHost *:{0}>|g\" {1}" \
        .format(env.http_port, os.path.join(env.httpd_confd_dir, 'indico.conf')))

    sed(os.path.join(env.indico_conf_dir, 'indico.conf'), \
        '^BaseSecureURL.*', \
        "BaseSecureURL        = \"https://{0}{1}/indico\"" \
        .format(env.host_name, env.ports[1]))
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'), \
        '^LoginURL.*', \
        "LoginURL             = \"https://{0}{1}/indico/signIn.py\"" \
        .format(env.host_name, env.ports[1]))
    run("sed -i.bak -r -e \"12s|.*|-A INPUT -m state --state NEW -m tcp -p tcp --dport {0} -j ACCEPT|g\" {1}" \
        .format(env.https_port, os.path.join(env.iptables_dir, 'iptables')))
    run("sed -i.bak -r -e \"30s|.*|<VirtualHost *:{0}>|g\" {1}" \
        .format(env.https_port, os.path.join(env.httpd_confd_dir, 'indico.conf')))


@task
def update_redis(redis_pswd=env.redis_pswd, redis_port=env.redis_port):
    """
    Change the Redis configuration
    """

    _update_params(redis_pswd=redis_pswd, redis_port=redis_port)

    sed('/etc/redis.conf', '^(#)? *requirepass.*', "requirepass {0}".format(env.redis_pswd))
    sed('/etc/redis.conf', '^(#)? *port.*', "port {0}".format(env.redis_port))
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'), '^(#)? *RedisConnectionURL.*', \
        "RedisConnectionURL = \"redis://unused:{0}@{1}:{2}/0\"".format(env.redis_pswd, env.host_name, env.redis_port))
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'), '^(#)? *RedisCacheURL.*', \
        "RedisCacheURL = \"redis://unused:{0}@{1}:{2}/1\"".format(env.redis_pswd, env.host_name, env.redis_port))

@task
def start(*what):
    """
    Start Indico components
    """

    if not what:
        what = ["redis", "db", "httpd"]
    
    for w in what:
        if w == 'redis':
            run('service redis start')
        if w == 'db':
            run("zdaemon -C {0} start".format(os.path.join(env.indico_conf_dir, 'zdctl.conf')))
        if w == 'httpd':
            run('service httpd start')

@task
def restart(*what):
    """
    Restart Indico components
    """

    if not what:
        what = ["redis", "db", "httpd"]
    
    for w in what:
        if w == 'redis':
            run('service redis restart')
        if w == 'db':
            run("zdaemon -C {0} restart".format(os.path.join(env.indico_conf_dir, 'zdctl.conf')))
        if w == 'httpd':
            run('service httpd restart')
