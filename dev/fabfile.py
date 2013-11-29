from fabric.api import *
from fabric.contrib.files import sed
from fabric.operations import put, run
from fabric.context_managers import settings
import os
import uuid

from fabric.network import ssh


def build_parameters():
    env.hosts = [env.host_machine['name'] + ':' + str(env.host_machine['ssh_port'])]
    env.img_path = os.path.join(env.img_dir, env.img_name)
    env.vd_path = os.path.join(env.img_dir, env.vd_name)

    env.db_inst_dir = os.path.join(env.indico_inst_dir, env.db_inst_dirname)
    env.indico_conf_dir = os.path.join(env.indico_inst_dir, env.indico_conf_dirname)


def _update_params(**params):
    """
    Updates the parameters with the passed arguments
    """

    env.update(params)
    build_parameters()


PUIAS_REPO_URL = "http://springdale.princeton.edu/data/puias/6.4/x86_64/os/RPM-GPG-KEY-puias"
YUM_DEPS = ['python-devel', 'gcc', 'httpd', 'mod_wsgi', 'python-reportlab',
            'python-imaging', 'python-lxml', 'mod_ssl', 'redis', 'openldap-devel']
INDICO_EXTRA_DEPS = ['hiredis', 'python-ldap']


execfile("fabfile.conf", {}, env)
build_parameters()


def _update_ports_debug():
    """
    Enable port forwarding in case of debug or disable it otherwise
    """

    # Modifying the ports in indico.conf
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'),
        '^(#)? *BaseURL.*',
        "BaseURL              = \"http://{0}{1}/indico\""
        .format(env.host_machine['name'], env.host_machine['http_port']))
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'),
        '^(#)? *BaseSecureURL.*',
        "BaseSecureURL        = \"https://{0}{1}/indico\""
        .format(env.host_machine['name'], env.host_machine['https_port']))
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'),
        '^(#)? *LoginURL.*',
        "LoginURL             = \"https://{0}{1}/indico/signIn.py\""
        .format(env.host_machine['name'], env.host_machine['https_port']))


def _putl(source_file, dest_dir):
    """
    To be used instead of put, since it doesn't support symbolic links
    """

    put(source_file, '/')
    run("mv -f /{0} {1}".format(os.path.basename(source_file), dest_dir))


def _gen_random_pswd():
    return uuid.uuid4().get_hex()


def _gen_self_signed_cert():
    # Self-generating an ssl certificate
    run("mkdir -p {0}".format(env.ssl_certs_dir))
    run("mkdir -p {0}".format(env.ssl_private_dir))
    run("openssl req -new -x509 -nodes -out {0} -keyout {1} -days 3650 -subj \'/CN={2}\'"
        .format (os.path.join(env.ssl_certs_dir, 'self-gen.pem'),
                 os.path.join(env.ssl_private_dir, 'self-gen.key'),
                 env.guest_machine['name']))


@task
def dependencies_inst():
    """
    Dependencies installation
    """

    run('wget {0}'.format(PUIAS_REPO_URL))
    run('mv RPM-GPG-KEY-puias /etc/pki/rpm-gpg/RPM-GPG-KEY-puias')
    _putl(os.path.join(env.config_dir, 'puias.repo'), '/etc/yum.repos.d')
    run('yum -y install {0}'.format(' '.join(YUM_DEPS)))
    run('easy_install {0}'.format(' '.join(INDICO_EXTRA_DEPS)))


@task
def indico_inst(indico_inst_dir=env.indico_inst_dir, db_inst_dir=None):
    """
    Indico installation and first setup
    """

    _update_params(indico_inst_dir=indico_inst_dir, db_inst_dir=db_inst_dir)

    run('easy_install indico')
    run("echo -e \"{0}\nc\ny\n{1}\" | indico_initial_setup"
        .format(env.indico_inst_dir, env.db_inst_dir))


@task
def indico_config(**kwparams):
    """
    Configure Indico and the database
    """

    _update_params(**kwparams)

    # Moving and modifying the Indico Apache .conf file
    _putl(os.path.join(env.config_dir, 'indico.conf'), env.httpd_confd_dir)
    sed(os.path.join(env.httpd_confd_dir, 'indico.conf'), '/opt/indico', env.indico_inst_dir)

    if env.debug_vm:
        sed(os.path.join(env.httpd_confd_dir, 'indico.conf'), '/etc/ssl/certs', env.ssl_certs_dir)
        sed(os.path.join(env.httpd_confd_dir, 'indico.conf'), '/etc/ssl/private', env.ssl_private_dir)
    run("sed -i.bak -r -e \"5s|.*|<VirtualHost *:{0}>|g\" {1}"
        .format(env.guest_machine['http_port'], os.path.join(env.httpd_confd_dir, 'indico.conf')))
    run("sed -i.bak -r -e \"30s|.*|<VirtualHost *:{0}>|g\" {1}"
        .format(env.guest_machine['https_port'], os.path.join(env.httpd_confd_dir, 'indico.conf')))


    # Adding a ServerName in httpd.conf
    sed(os.path.join(env.httpd_conf_dir, 'httpd.conf'),
        '#ServerName.*',
        "ServerName {0}".format(env.guest_machine['name']))


@task
def vm_config(**params):
    """
    Configures other aspects of the VM
    """

    _update_params(**params)

    if env.debug_vm:
        _gen_self_signed_cert()


    # Adding the ports 80 and 443 to the iptables
    run("sed \"11i\\-A INPUT -m state --state NEW -m tcp -p tcp --dport {0} -j ACCEPT\" {1} > {2}"
        .format(env.guest_machine['http_port'], os.path.join(env.iptables_dir, 'iptables'), os.path.join(env.iptables_dir, 'temp')))
    run("mv -f {0} {1}"
        .format(os.path.join(env.iptables_dir, 'temp'), os.path.join(env.iptables_dir, 'iptables')))
    run("sed \"12i\\-A INPUT -m state --state NEW -m tcp -p tcp --dport {0} -j ACCEPT\" {1} > {2}"
        .format(env.guest_machine['https_port'], os.path.join(env.iptables_dir, 'iptables'), os.path.join(env.iptables_dir, 'temp')))
    run("mv -f {0} {1}"
        .format(os.path.join(env.iptables_dir, 'temp'), os.path.join(env.iptables_dir, 'iptables')))
    run('service iptables restart')

    # Modifying the ssl.conf file
    _putl(os.path.join(env.config_dir, 'ssl.conf'), env.httpd_confd_dir)

    # Change SELinux policies to allow Apache access
    for idir in ['archive', 'cache', 'htdocs', 'log', 'tmp']:
        run("semanage fcontext -a -t httpd_sys_content_t \'{0}(/.*)?\'"
            .format(os.path.join(env.indico_inst_dir, idir)))

    run("semanage fcontext -a -t httpd_sys_content_t \'{0}(/.*)?\'"
        .format(env.db_inst_dir))

    run("restorecon -Rv {0}".format(env.indico_inst_dir))
    run("restorecon -Rv {0}".format(env.db_inst_dir))
    run('setsebool -P httpd_can_network_connect 1')

    # Configure Redis
    pswd = _gen_random_pswd()
    _putl(os.path.join(env.config_dir, 'redis.conf'), '/etc')
    sed('/etc/redis.conf', '^(#)? *requirepass.*', "requirepass {0}".format(pswd))
    sed('/etc/redis.conf', '^(#)? *port.*', "port {0}".format(env.redis_port))
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'), '^(#)? *RedisConnectionURL.*',
        "RedisConnectionURL = \"redis://unused:{0}@{1}:{2}/0\"".format(pswd, env.redis_host, env.redis_port))
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'), '^(#)? *RedisCacheURL.*',
        "RedisCacheURL = \"redis://unused:{0}@{1}:{2}/1\"".format(pswd, env.redis_host, env.redis_port))


@task
def config(host_name=env.guest_machine['name'], config_dir=env.config_dir, indico_inst_dir=env.indico_inst_dir,
           db_inst_dir=env.db_inst_dir, http_port_fwd=env.host_machine['http_port'], https_port_fwd=env.host_machine['https_port']):
    """
    Configure Indico and various aspects of the VM
    """

    indico_config(host_name=host_name, config_dir=config_dir, indico_inst_dir=indico_inst_dir,
                  http_port_fwd=http_port_fwd, https_port_fwd=https_port_fwd)

    if env.debug_vm:
        _update_ports_debug()

    vm_config(host_name=host_name, config_dir=config_dir, indico_inst_dir=indico_inst_dir,
              db_inst_dir=db_inst_dir)


@task
def deploy(host_name=env.guest_machine['name'], config_dir=env.config_dir,
           indico_inst_dir=env.indico_inst_dir, db_inst_dir=None,
           http_port_fwd=env.host_machine['http_port'], https_port_fwd=env.host_machine['https_port']):
    """
    Deploy Indico into the VM
    """

    dependencies_inst()
    indico_inst(indico_inst_dir, db_inst_dir)
    config(host_name, config_dir, indico_inst_dir, db_inst_dir, http_port_fwd, https_port_fwd)


@task
def start():
    """
    Start Indico
    """

    _update_params()

    run("zdaemon -C {0} start".format(os.path.join(env.indico_conf_dir, 'zdctl.conf')))
    run('service redis start')
    run('service httpd start')

@task
def launch_vm(**params):
    """
    Run the Virtual Machine
    """

    _update_params(**params)

    local("touch {0}".format(env.qemu_log))

    # if in debug mode, redirect to local port (for testing)
    if env.debug_vm:
        redir = " -redir tcp:{0}::{1} -redir tcp:{2}::{3}" \
                .format(env.host_machine['http_port'], env.guest_machine['http_port'], env.host_machine['https_port'], env.guest_machine['https_port'])
    else:
        redir = ""

    local(("{0} -m 256 -redir tcp:{4}::{5}{6} -net nic -net user, -drive file={1}" +
          ",if=virtio -drive file={2},if=virtio -serial file:{3} &")
          .format(env.virtualization_cmd, env.img_path, env.vd_path, env.qemu_log, env.host_machine['ssh_port'], env.guest_machine['ssh_port'], redir))

    print("Booting up VM...")
    local("while ! grep -q \"Starting atd:.*[.*OK.*]\" \"{0}\"; do sleep 5; done"
          .format(env.qemu_log))
    print("VM running!")


def config_no_cloud(config_dir=env.config_dir, vd_path=env.vd_path):
    """
    cloud-init no-cloud fake config
    """

    _update_params(config_dir=config_dir, vd_path=vd_path)

    local("sed -i .bak \'s|^password:.*|password: {0}|g\' {1}"
          .format(env.password, os.path.join(env.config_dir, 'user-data')))
    local("mkisofs -output {0} -volid cidata -joliet -rock {1} {2}"
          .format(env.vd_path, os.path.join(env.config_dir, 'user-data'),
                  os.path.join(env.config_dir, 'meta-data')))

@task
def cleanup_vm():
    with settings(warn_only=True):
        run('rm /etc/udev/rules.d/70-persistent-net.rules')
        run('rm /lib/udev/write_net_rules')
    run('shutdown -h now')

@task
def run_vm(host_port_fwd=env.host_machine['ssh_port'], img_name=env.img_name, vd_name=env.vd_name,
              indico_inst_dir=env.indico_inst_dir, virtualization_cmd=env.virtualization_cmd,
              http_port_fwd=env.host_machine['http_port'], https_port_fwd=env.host_machine['https_port'],
              img_dir=env.img_dir):
    """
    Run the VM and start Indico (Debugging purposes)
    """
    env.debug_vm = True
    launch_vm(host_port_fwd=host_port_fwd, img_name=img_name, vd_name=vd_name, virtualization_cmd=virtualization_cmd,
              http_port_fwd=http_port_fwd, https_port_fwd=https_port_fwd, img_dir=img_dir)
    start()


@task
def create_vm_img(host_name=env.guest_machine['name'], host_port_fwd=env.host_machine['ssh_port'], config_dir=env.config_dir,
                  img_path=env.img_path, vd_path=env.vd_path, indico_inst_dir=env.indico_inst_dir,
                  db_inst_dir=None, virtualization_cmd=env.virtualization_cmd):
    """
    Creates a Virtual Image ready to be deployed on the cloud
    """

    config_no_cloud(config_dir, vd_path)
    launch_vm(host_port_fwd=host_port_fwd, img_path=img_path, vd_path=vd_path,
              virtualization_cmd=virtualization_cmd, debug=False)
    deploy(host_name=host_name, config_dir=config_dir, indico_inst_dir=indico_inst_dir, db_inst_dir=db_inst_dir)
    cleanup_vm()
