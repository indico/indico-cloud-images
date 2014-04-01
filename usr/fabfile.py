from fabric.api import *
from fabric.contrib.files import sed, contains
from fabric.operations import put, run
import os


def _build_parameters():
    env.hosts = [env.machine['name'] + ':' + str(env.machine['ssh_port'])]
    env.indico_conf_dir = os.path.join(env.indico_inst_dir, env.indico_conf_dirname)


def _update_params(**params):
    """
    Updates the parameters with the passed arguments
    """

    env.update(params)
    _build_parameters()

env.conf = 'fabfile.conf'
execfile(env.conf, {}, env)
_build_parameters()


def _putl(source_file, dest_dir):
    """
    To be used instead of put, since it doesn't support symbolic links
    """

    put(source_file, '/')
    run("mkdir -p {0}".format(dest_dir))
    run("mv -f /{0} {1}".format(os.path.basename(source_file), dest_dir))


@task
def load_ssl(**params):
    """
    Load a personal SSL certificate into the VM
    """

    _update_params(**params)

    # Copy the new certificate
    _putl(env.ssl_pem_path, env.ssl_certs_dir)
    _putl(env.ssl_key_path, env.ssl_private_dir)

    # Modify the indico.conf SSL entries
    sed(os.path.join(env.httpd_confd_dir, 'indico.conf'),
        "{0}.*.pem".format(env.ssl_certs_dir),
        os.path.join(env.ssl_certs_dir, os.path.basename(env.ssl_pem_path)))
    sed(os.path.join(env.httpd_confd_dir, 'indico.conf'),
        "{0}.*.key".format(env.ssl_private_dir),
        os.path.join(env.ssl_private_dir, os.path.basename(env.ssl_key_path)))


@task
def update_server(**params):
    """
    Change the server configuration (hostname and ports)
    """

    _update_params(**params)

    sed(os.path.join(env.httpd_conf_dir, 'httpd.conf'),
        '^ServerName.*', "ServerName {0}".format(env.machine['name']))

    http = ':{0}'.format(env.machine['http_port']) if env.machine['http_port'] is not '80' else ''
    https = ':{0}'.format(env.machine['https_port']) if env.machine['https_port'] is not '443' else ''

    sed(os.path.join(env.indico_conf_dir, 'indico.conf'),
        '^BaseURL.*',
        "BaseURL              = \"http://{0}{1}/indico\""
        .format(env.machine['name'], http))
    run("sed -i.bak -r -e \"11s|.*|-A INPUT -m state --state NEW -m tcp -p tcp --dport {0} -j ACCEPT|g\" {1}"
        .format(env.machine['http_port'], os.path.join(env.iptables_dir, 'iptables')))
    run("sed -i.bak -r -e \"5s|.*|<VirtualHost *:{0}>|g\" {1}"
        .format(env.machine['http_port'], os.path.join(env.httpd_confd_dir, 'indico.conf')))

    sed(os.path.join(env.indico_conf_dir, 'indico.conf'),
        '^BaseSecureURL.*',
        "BaseSecureURL        = \"https://{0}{1}/indico\""
        .format(env.machine['name'], https))
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'),
        '^LoginURL.*',
        "LoginURL             = \"https://{0}{1}/indico/signIn.py\""
        .format(env.machine['name'], https))
    run("sed -i.bak -r -e \"12s|.*|-A INPUT -m state --state NEW -m tcp -p tcp --dport {0} -j ACCEPT|g\" {1}"
        .format(env.machine['https_port'], os.path.join(env.iptables_dir, 'iptables')))
    run("sed -i.bak -r -e \"30s|.*|<VirtualHost *:{0}>|g\" {1}"
        .format(env.machine['https_port'], os.path.join(env.httpd_confd_dir, 'indico.conf')))

    sed(os.path.join(env.indico_conf_dir, 'indico.conf'),
        '^SupportEmail.*',
        "SupportEmail         = \"root@{0}\"".format(env.machine['name']))
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'),
        '^PublicSupportEmail.*',
        "PublicSupportEmail         = \"root@{0}\"".format(env.machine['name']))
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'),
        '^NoReplyEmail.*',
        "NoReplyEmail         = \"noreply-root@{0}\"".format(env.machine['name']))


@task
def update_redis(**params):
    """
    Change the Redis configuration
    """

    _update_params(**params)

    sed('/etc/redis.conf', '^(#)? *requirepass.*', "requirepass {0}".format(env.redis_pswd))
    sed('/etc/redis.conf', '^(#)? *port.*', "port {0}".format(env.redis_port))
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'), '^(#)? *RedisConnectionURL.*',
        "RedisConnectionURL = \"redis://unused:{0}@{1}:{2}/0\"".format(env.redis_pswd, env.redis_host, env.redis_port))
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'), '^(#)? *RedisCacheURL.*',
        "RedisCacheURL = \"redis://unused:{0}@{1}:{2}/1\"".format(env.redis_pswd, env.redis_host, env.redis_port))


@task
def update_smtp(**params):
    """
    Change the SMTP configuration
    """

    _update_params(**params)

    sed(os.path.join(env.indico_conf_dir, 'indico.conf'),
        '^SmtpServer.*',
        "SmtpServer           = ('{0}', {0})".format(env.smtp_server_name, env.smtp_server_port))
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'),
        '^SmtpLogin.*',
        "SmtpLogin           = \"{0}\"".format(env.smtp_login))
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'),
        '^SmtpPassword.*',
        "SmtpPassword           = \"{0}\"".format(env.smtp_pswd))
    if env.postfix:
        sed('/etc/postfix/master.cf',
            '.*      inet  n       -       n       -       -       smtpd',
            "{0}      inet  n       -       n       -       -       smtpd".format(env.smtp_server_port))
        if not contains('/etc/postfix/master.cf', 'resolve_numeric_domain = yes'):
            append('/etc/postfix/master.cf', 'resolve_numeric_domain = yes')



@task
def config(**params):
    """
    Configure the VM with all the necessary information
    """

    load_ssl(**params)
    update_server(**params)
    update_redis(**params)
    update_smtp(**params)


@task
def start(*what):
    """
    Start Indico components
    """

    if not what:
        what = ["redis", "db", "httpd", "postfix"]

    for w in what:
        if w == 'redis':
            run('service redis start')
        if w == 'db':
            run("zdaemon -C {0} start".format(os.path.join(env.indico_conf_dir, 'zdctl.conf')))
        if w == 'httpd':
            run('service httpd start')
        if env.postfix and w == 'postfix':
            run('service postfix start')


@task
def restart(*what):
    """
    Restart Indico components
    """

    if not what:
        what = ["redis", "db", "httpd", "postfix"]

    for w in what:
        if w == 'redis':
            run('service redis restart')
        if w == 'db':
            run("zdaemon -C {0} restart".format(os.path.join(env.indico_conf_dir, 'zdctl.conf')))
        if w == 'httpd':
            run('service httpd restart')
        if env.postfix and w == 'postfix':
            run('service postfix restart')
