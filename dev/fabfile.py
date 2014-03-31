from fabric.api import *
from fabric.contrib.files import sed
from fabric.operations import put, run
from fabric.context_managers import settings
import os
import uuid


def _build_parameters():
    env.hosts = [env.host_machine['name'] + ':' +
                 str(env.host_machine['ssh_port'])]
    env.img_path = os.path.join(env.img_dir, env.img_name)
    env.vd_path = os.path.join(env.img_dir, env.vd_name)

    env.db_inst_dir = os.path.join(env.indico_inst_dir, env.db_inst_dirname)
    env.indico_conf_dir = os.path.join(env.indico_inst_dir,
                                       env.indico_conf_dirname)


def _update_params(**params):
    """
    Updates the parameters with the passed arguments
    """

    env.update(params)
    _build_parameters()


PUIAS_REPO_URL = "http://springdale.princeton.edu/data/puias/6.4/x86_64/os/RPM-GPG-KEY-puias"
YUM_DEPS = ['python-devel', 'gcc', 'httpd', 'mod_wsgi', 'python-reportlab',
            'python-imaging', 'python-lxml', 'mod_ssl', 'redis', 'openldap-devel']
INDICO_EXTRA_DEPS = ['hiredis', 'python-ldap', 'redis']

env.conf = "fabfile.conf"
execfile(env.conf, {}, env)
_build_parameters()


def _debug_update():
    """
    Enable port forwarding in case of debug or disable it otherwise
    """

    # Modifying the ports in indico.conf
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'),
        '^(#)? *BaseURL.*',
        "BaseURL = \"http://{0}:{1}/indico\""
        .format(env.host_machine['name'], env.host_machine['http_port']))
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'),
        '^(#)? *BaseSecureURL.*', "BaseSecureURL = \"https://{0}:{1}/indico\""
                                  .format(env.host_machine['name'], env.host_machine['https_port']))
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'),
        '^(#)? *LoginURL.*', "LoginURL = \"https://{0}:{1}/indico/signIn.py\""
                             .format(env.host_machine['name'], env.host_machine['https_port']))
    sed(os.path.join(env.httpd_conf_dir, 'httpd.conf'),
        '^(#)? *ServerName.*', "ServerName {0}".format(env.host_machine['name']))


def _putl(source_file, dest_dir):
    """
    To be used instead of put, since it doesn't support symbolic links
    """

    put(source_file, '/')
    run("mkdir -p {0}".format(dest_dir))
    run("mv -f /{0} {1}".format(os.path.basename(source_file), dest_dir))


def add_line(file_path, number, line):
    run("sed -i.bak -r -e \"{0}i\\{1}\" {2}".format(number, line, file_path))


def _gen_file(rules_dict, in_path, out_path):
    with open(in_path, 'r') as fin:
        with open(out_path, 'w+') as fout:
            fout.write(fin.read().format(**rules_dict))


def _gen_indico_httpd_conf():
    in_path = os.path.join(env.tpl_dir, 'indico_httpd.conf')
    out_path = os.path.join(env.conf_dir, 'indico_httpd.conf')
    rules_dict = {
        'virtualhost_http_port': "<VirtualHost *:{0}>".format(env.guest_machine['http_port']),
        'virtualhost_https_port': "<VirtualHost *:{0}>".format(env.guest_machine['https_port']),
        'indico_inst_dir': env.indico_inst_dir,
        'ssl_pem_path': os.path.join(env.ssl_certs_dir, 'self-gen.pem'),
        'ssl_key_path': os.path.join(env.ssl_private_dir, 'self-gen.key')
    }

    _gen_file(rules_dict, in_path, out_path)


def _gen_indico_indico_conf():
    if env.debug_vm:
        http = ':{0}'.format(env.host_machine['http_port'])
        https = ':{0}'.format(env.host_machine['https_port'])
        name = env.host_machine['name']
    else:
        http = ':{0}'.format(env.guest_machine['http_port']) if env.guest_machine['http_port'] is not '80' else ''
        https = ':{0}'.format(env.guest_machine['https_port']) if env.guest_machine['https_port'] is not '443' else ''
        name = env.guest_machine['name']

    in_path = os.path.join(env.tpl_dir, 'indico_indico.conf')
    out_path = os.path.join(env.conf_dir, 'indico_indico.conf')
    rules_dict = {
        'redis_connection_url': "RedisConnectionURL = \'redis://unused:{0}@{1}:{2}/0\'"
                                .format(env.redis_pswd, env.redis_host, env.redis_port),
        'base_url': "BaseURL = \"http://{0}{1}/indico\"".format(name, http),
        'base_secure_url': "BaseSecureURL = \"https://{0}{1}/indico\"".format(name, https),
        'login_url': "LoginURL = \"https://{0}{1}/indico/signIn.py\""
                     .format(name, https),
        'indico_inst_dir': env.indico_inst_dir,
        'redis_cache_url': "RedisCacheURL = \'redis://unused:{0}@{1}:{2}/1\'"
                           .format(env.redis_pswd, env.redis_host, env.redis_port)
    }

    _gen_file(rules_dict, in_path, out_path)


def _gen_puias_repo():
    in_path = os.path.join(env.tpl_dir, 'puias.repo')
    out_path = os.path.join(env.conf_dir, 'puias.repo')
    rules_dict = {
        'puias_priority': env.puias_priority
    }

    _gen_file(rules_dict, in_path, out_path)


def _gen_redis_conf():
    in_path = os.path.join(env.tpl_dir, 'redis.conf')
    out_path = os.path.join(env.conf_dir, 'redis.conf')
    rules_dict = {
        'redis_pswd': env.redis_pswd,
        'redis_port': env.redis_port
    }

    _gen_file(rules_dict, in_path, out_path)


def _gen_random_pswd():
    return uuid.uuid4().get_hex()


def _gen_self_signed_cert():
    """
    Self-generating an ssl certificate
    """

    run("mkdir -p {0}".format(env.ssl_certs_dir))
    run("mkdir -p {0}".format(env.ssl_private_dir))
    run("openssl req -new -x509 -nodes -out {0} -keyout {1} -days 3650 -subj \'/CN={2}\'"
        .format(os.path.join(env.ssl_certs_dir, 'self-gen.pem'),
                os.path.join(env.ssl_private_dir, 'self-gen.key'),
                env.guest_machine['name']))


@task
def dependencies_inst():
    """
    Dependencies installation
    """

    run('wget {0}'.format(PUIAS_REPO_URL))
    run('mv RPM-GPG-KEY-puias /etc/pki/rpm-gpg/RPM-GPG-KEY-puias')
    _gen_puias_repo()
    _putl(os.path.join(env.conf_dir, 'puias.repo'), env.yum_repos_dir)
    run('yum -y install {0}'.format(' '.join(YUM_DEPS)))
    run('easy_install {0}'.format(' '.join(INDICO_EXTRA_DEPS)))


@task
def indico_inst(**params):
    """
    Indico installation and first setup
    """

    _update_params(**params)

    run('easy_install indico')
    run("echo -e \"{0}\nc\ny\n{1}\" | indico_initial_setup"
        .format(env.indico_inst_dir, env.db_inst_dir))


@task
def indico_config(**params):
    """
    Configure Indico and the database
    """

    _update_params(**params)

    env.redis_pswd = _gen_random_pswd()

    # Moving and modifying the Indico Apache .conf file
    _gen_indico_httpd_conf()
    _putl(os.path.join(env.conf_dir, 'indico_httpd.conf'), env.httpd_confd_dir)
    run("mv -f {0} {1}".format(os.path.join(env.httpd_confd_dir, 'indico_httpd.conf'),
                               os.path.join(env.httpd_confd_dir, 'indico.conf')))

    # Modifying the ports in indico.conf
    _gen_indico_indico_conf()
    _putl(os.path.join(env.conf_dir, 'indico_indico.conf'), env.indico_inst_dir)
    run("mv -f {0} {1}".format(os.path.join(env.indico_inst_dir, 'indico_indico.conf'),
                               os.path.join(env.indico_inst_dir, 'indico.conf')))

    # Adding a ServerName in httpd.conf
    name = env.host_machine['name'] if env.debug_vm else env.guest_machine['name']
    sed(os.path.join(env.httpd_conf_dir, 'httpd.conf'), '#ServerName.*', "ServerName {0}".format(name))

    # Configure Redis
    _gen_redis_conf()
    _putl(os.path.join(env.conf_dir, 'redis.conf'), '/etc')


@task
def vm_config(**params):
    """
    Configures other aspects of the VM
    """

    _update_params(**params)

    _gen_self_signed_cert()

    # Adding the ports to the iptables
    add_line(os.path.join(env.iptables_dir, 'iptables'), 11,
             "-A INPUT -m state --state NEW -m tcp -p tcp --dport {0} -j ACCEPT"
             .format(env.guest_machine['http_port']))
    add_line(os.path.join(env.iptables_dir, 'iptables'), 12,
             "-A INPUT -m state --state NEW -m tcp -p tcp --dport {0} -j ACCEPT"
             .format(env.guest_machine['https_port']))
    run('service iptables restart')

    # Modifying the ssl.conf file
    _putl(os.path.join(env.conf_dir, 'ssl.conf'), env.httpd_confd_dir)

    # Change SELinux policies to allow Apache access
    for idir in ['archive', 'cache', 'htdocs', 'log', 'tmp']:
        run("semanage fcontext -a -t httpd_sys_content_t \'{0}(/.*)?\'"
            .format(os.path.join(env.indico_inst_dir, idir)))
    run("semanage fcontext -a -t httpd_sys_content_t \'{0}(/.*)?\'"
        .format(env.db_inst_dir))
    run("restorecon -Rv {0}".format(env.indico_inst_dir))
    run("restorecon -Rv {0}".format(env.db_inst_dir))
    run('setsebool -P httpd_can_network_connect 1')


@task
def config(**params):
    """
    Configure Indico and various aspects of the VM
    """

    indico_config(**params)

    vm_config(**params)


@task
def deploy(**params):
    """
    Deploy Indico into the VM
    """

    dependencies_inst()
    indico_inst(**params)
    config(**params)


@task
def start(**params):
    """
    Start Indico
    """

    _update_params(**params)

    run('service redis start')
    run("zdaemon -C {0} start".format(os.path.join(env.indico_conf_dir, 'zdctl.conf')))
    run('service httpd start')


@task
def launch_vm(**params):
    """
    Run the Virtual Machine
    """

    _update_params(**params)

    local("echo '' > {0}".format(env.qemu_log))

    # if in debug mode, redirect to local port (for testing)
    if env.debug_vm:
        redir = " -redir tcp:{0}::{1} -redir tcp:{2}::{3}" \
                .format(env.host_machine['http_port'], env.guest_machine['http_port'],
                        env.host_machine['https_port'], env.guest_machine['https_port'])
    else:
        redir = ""

    local(("{0} -m 256 -redir tcp:{4}::{5}{6} -net nic -net user, -drive file={1}" +
          ",if=virtio -drive file={2},if=virtio -serial file:{3} &")
          .format(env.virtualization_cmd, env.img_path, env.vd_path, env.qemu_log,
                  env.host_machine['ssh_port'], env.guest_machine['ssh_port'], redir))

    print("Booting up VM...")
    local("while ! grep -q \"Starting atd:.*[.*OK.*]\" \"{0}\"; do sleep 5; done"
          .format(env.qemu_log))
    print("VM running!")


@task
def config_no_cloud(**params):
    """
    cloud-init no-cloud fake config
    """

    _update_params(**params)

    local("sed -i.bak \'s|^password:.*|password: {0}|g\' {1}"
          .format(env.password, os.path.join(env.conf_dir, 'user-data')))
    local("mkisofs -output {0} -volid cidata -joliet -rock {1} {2}"
          .format(env.vd_path, os.path.join(env.conf_dir, 'user-data'),
                  os.path.join(env.conf_dir, 'meta-data')))


def cleanup_vm():
    with settings(warn_only=True):
        run('rm /etc/udev/rules.d/70-persistent-net.rules')
        run('rm /lib/udev/write_net_rules')
    run('shutdown -h now')


@task
def run_vm_debug(**params):
    """
    Run the VM and start Indico (debugging purposes)
    """

    env.debug_vm = True
    launch_vm(**params)
    _debug_update()
    start()


@task
def create_vm_img(**params):
    """
    Creates a Virtual Image ready to be deployed on the cloud
    """

    config_no_cloud(**params)
    launch_vm(**params)
    deploy(**params)
    cleanup_vm()
