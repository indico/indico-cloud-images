import os
import sys
from contextlib import contextmanager

from fabric.api import *
from fabric.contrib.files import sed
from fabric.operations import put, run
from fabric.colors import red


@contextmanager
def virtualenv():
    with prefix('source {}/bin/activate'.format(os.path.join(env.indico_dir, env.virtualenv_dirname))):
        yield


def _build_parameters():
    env.hosts = [env.machine['name'] + ':' + str(env.machine['ssh_port'])]
    env.indico_conf_dir = os.path.join(env.indico_dir, env.conf_dirname)


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

    indico_conf = os.path.join(env.indico_conf_dir, 'indico.conf')

    sed(os.path.join(env.httpd_conf_dir, 'httpd.conf'),
        '^ServerName.*', "ServerName {0}".format(env.machine['name']))

    sed(indico_conf, '^BaseURL.*', 'BaseURL = "http://{}"'.format(env.machine['name']))
    sed(indico_conf, '^BaseSecureURL.*', 'BaseSecureURL = "https://{}"'.format(env.machine['name']))
    sed(indico_conf, '^LoginURL.*', 'LoginURL = "https://{}/user/login"'.format(env.machine['name']))


@task
def config(**params):
    """
    Configure the VM with all the necessary information
    """

    load_ssl(**params)
    update_server(**params)


def _service_action(services, action):
    if services[0] == 'all':
        services = ["redis", "db", "httpd", "scheduler"]
    elif not services:
        print red("Please specify a service name (or 'all')")
        sys.exit(1)

    for svc in services:
        if svc == 'redis':
            run('service redis {}'.format(action))
        elif svc == 'db':
            with virtualenv():
                run("zdaemon -C {} {}".format(os.path.join(env.indico_conf_dir, 'zdctl.conf'), action))
        elif svc == 'scheduler':
            with virtualenv():
                sudo("indico_scheduler {}".format(action), user="apache")
        elif svc == 'httpd':
            run('service httpd {}'.format(action))
        else:
            print red("Unknown service: {}".format(svc))
            sys.exit(1)


@task
def start(*what):
    """
    Start Indico components
    """
    _service_action(what, 'start')


@task
def restart(*what):
    """
    Restart Indico components
    """

    _service_action(what, 'restart')


@task
def stop(*what):
    """
    Stop Indico components
    """

    _service_action(what, 'stop')
