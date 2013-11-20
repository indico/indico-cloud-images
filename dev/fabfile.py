from fabric.api import *
from fabric.contrib.files import sed
from fabric.operations import put, run
from fabric.main import load_settings
import os
import string
import random

env.conf = 'fabfile.conf'

settings = load_settings(env.conf)
if not settings:
    raise RuntimeError("Configuration file {0} is needed!".format(env.conf))
env.update(settings)

if env.debug == 'True':
    env.ports = [env.http_port_fwd, env.https_port_fwd]
else:
    env.ports = [env.http_port, env.https_port]

env.hosts = ["{0}@{1}:{2}".format(env.user_name, env.host_name, env.host_port_fwd)]

env.img_path = os.path.join(env.img_dir, env.img_name)
env.vd_path = os.path.join(env.img_dir, env.vd_name)

env.db_inst_dir = os.path.join(env.indico_inst_dir, env.db_inst_dirname)
env.indico_conf_dir = os.path.join(env.indico_inst_dir, env.indico_conf_dirname)

env.ssl_certs_dir = os.path.join(env.ssl_dir, env.ssl_certs_dirname)
env.ssl_private_dir = os.path.join(env.ssl_dir, env.ssl_private_dirname)

def _update_params(host_name=env.host_name, host_port_fwd=env.host_port_fwd, config_dir=env.config_dir,
                   img_path=env.img_path, vd_path=env.vd_path, indico_inst_dir=env.indico_inst_dir,
                   db_inst_dir=None, virtualization_cmd=env.virtualization_cmd, http_port_fwd=env.http_port_fwd,
                   https_port_fwd=env.https_port_fwd, debug=env.debug):
    """
    Updates the parameters with the passed arguments
    """

    env.host_name = host_name
    env.host_port_fwd = host_port_fwd
    env.hosts = ["{0}@{1}:{2}".format(env.user_name, env.host_name, env.host_port_fwd)]
    env.config_dir = config_dir
    env.img_path = img_path
    env.vd_path = vd_path
    env.indico_inst_dir = indico_inst_dir
    env.indico_conf_dir = os.path.join(env.indico_inst_dir, env.indico_conf_dirname)
    if db_inst_dir is None:
        env.db_inst_dir = os.path.join(env.indico_inst_dir, env.db_inst_dirname)
    else:
        env.db_inst_dir = db_inst_dir
    env.virtualization_cmd = virtualization_cmd
    env.http_port_fwd = http_port_fwd
    env.https_port_fwd = https_port_fwd
    if debug == 'True':
        env.debug = True
    else:
        env.debug = False
    env.ports = _get_ports()

def _get_ports():
    """
    Return a list of ports, depending if the debug mode is on or off
    """

    if env.debug:
        return [env.http_port_fwd, env.https_port_fwd]
    else:
        return [env.http_port, env.https_port]

def _update_ports():
    """
    Enable port forwarding in case of debug or disable it otherwise
    """

    # Modifying the ports in indico.conf
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'), \
        '^(#)? *BaseURL.*', \
        "BaseURL              = \"http://{0}:{1}/indico\"" \
        .format(env.host_name, env.ports[0]))
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'), \
        '^(#)? *BaseSecureURL.*', \
        "BaseSecureURL        = \"https://{0}:{1}/indico\"" \
        .format(env.host_name, env.ports[1]))
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'), \
        '^(#)? *LoginURL.*', \
        "LoginURL             = \"https://{0}:{1}/indico/signIn.py\"" \
        .format(env.host_name, env.ports[1]))

def _putl(source_file, dest_dir):
    """
    To be used instead of put, since it doesn't support symbolic links
    """

    put(source_file, '/')
    run("mv -f /{0} {1}".format(os.path.basename(source_file), dest_dir))

def _get_random_number():
    n = int(''.join(random.choice(string.digits) for x in range(2)))+1
    return n

def _gen_random_pswd():
    n = _get_random_number()
    pswd = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for x in range(n))
    return pswd

@task
def dependencies_inst():
    """
    Dependencies installation
    """

    run('wget http://springdale.princeton.edu/data/puias/6.4/x86_64/os/RPM-GPG-KEY-puias')
    run('mv RPM-GPG-KEY-puias /etc/pki/rpm-gpg/RPM-GPG-KEY-puias')
    _putl(os.path.join(env.config_dir, 'puias.repo'), '/etc/yum.repos.d')
    run('yum -y install python-devel.x86_64 gcc.x86_64 httpd.x86_64 mod_wsgi.x86_64' + \
        ' python-reportlab.x86_64 python-imaging.x86_64 python-lxml.x86_64 mod_ssl.x86_64 redis.x86_64')
    run('easy_install ZODB3==3.10.5 zc.queue==1.3 hiredis redis')

@task
def indico_inst(indico_inst_dir=env.indico_inst_dir, db_inst_dir=None):
    """
    Indico installation and first setup
    """

    _update_params(indico_inst_dir=indico_inst_dir, db_inst_dir=db_inst_dir)

    run('easy_install indico')
    run("echo -e \"{0}\nc\ny\n{1}\" | indico_initial_setup"\
        .format(env.indico_inst_dir, env.db_inst_dir))


@task
def indico_config(host_name=env.host_name, config_dir=env.config_dir,
                  indico_inst_dir=env.indico_inst_dir, http_port_fwd=env.http_port_fwd,
                  https_port_fwd=env.https_port_fwd):
    """
    Configure Indico and the database
    """

    _update_params(host_name=host_name, config_dir=config_dir, indico_inst_dir=indico_inst_dir, \
                   http_port_fwd=http_port_fwd, https_port_fwd=https_port_fwd)

    # Moving and modifying the Indico Apache .conf file
    _putl(os.path.join(env.config_dir, 'indico.conf'), env.httpd_confd_dir)
    sed(os.path.join(env.httpd_confd_dir, 'indico.conf'), '/opt/indico', env.indico_inst_dir)
    sed(os.path.join(env.httpd_confd_dir, 'indico.conf'), '/etc/ssl/certs', env.ssl_certs_dir)
    sed(os.path.join(env.httpd_confd_dir, 'indico.conf'), '/etc/ssl/private', env.ssl_private_dir)

    # Adding a ServerName in httpd.conf
    sed(os.path.join(env.httpd_conf_dir, 'httpd.conf'), \
        '#ServerName.*', \
        "ServerName {0}".format(env.host_name))

    # Adding the corresponding ports to indico.conf
    _update_ports()

@task
def vm_config(host_name=env.host_name, config_dir=env.config_dir,
              indico_inst_dir=env.indico_inst_dir, db_inst_dir=env.db_inst_dir):
    """
    Configures other aspects of the VM
    """

    _update_params(host_name=host_name, config_dir=config_dir, \
                   indico_inst_dir=indico_inst_dir, db_inst_dir=db_inst_dir)

    # Self-generating an ssl certificate
    run("mkdir -p {0}".format(env.ssl_certs_dir))
    run("mkdir -p {0}".format(env.ssl_private_dir))
    run("openssl req -new -x509 -nodes -out {0} -keyout {1} -days 3650 -subj \'/CN={2}\'" \
        .format (os.path.join(env.ssl_certs_dir, 'self-gen.pem'), \
                 os.path.join(env.ssl_private_dir, 'self-gen.key'), \
                 env.host_name))

    # Adding the ports 80 and 443 to the iptables
    run("sed \"11i\\-A INPUT -m state --state NEW -m tcp -p tcp --dport {0} -j ACCEPT\" {1} > {2}" \
        .format(env.http_port, os.path.join(env.iptables_dir, 'iptables'), os.path.join(env.iptables_dir, 'temp')))
    run("mv -f {0} {1}"\
        .format(os.path.join(env.iptables_dir, 'temp'), os.path.join(env.iptables_dir, 'iptables')))
    run("sed \"12i\\-A INPUT -m state --state NEW -m tcp -p tcp --dport {0} -j ACCEPT\" {1} > {2}" \
        .format(env.https_port, os.path.join(env.iptables_dir, 'iptables'), os.path.join(env.iptables_dir, 'temp')))
    run("mv -f {0} {1}"\
        .format(os.path.join(env.iptables_dir, 'temp'), os.path.join(env.iptables_dir, 'iptables')))
    run('service iptables restart')

    # Modifying the ssl.conf file
    _putl(os.path.join(env.config_dir, 'ssl.conf'), env.httpd_confd_dir)

    # Change SELinux policies to allow Apache access
    run("semanage fcontext -a -t httpd_sys_content_t \'{0}(/.*)?\'" \
        .format(os.path.join(env.indico_inst_dir, 'archive')))
    run("semanage fcontext -a -t httpd_sys_content_t \'{0}(/.*)?\'" \
        .format(os.path.join(env.indico_inst_dir, 'cache')))
    run("semanage fcontext -a -t httpd_sys_content_t \'{0}(/.*)?\'" \
        .format(env.db_inst_dir))
    run("semanage fcontext -a -t httpd_sys_content_t \'{0}(/.*)?\'" \
        .format(os.path.join(env.indico_inst_dir, 'htdocs')))
    run("semanage fcontext -a -t httpd_sys_content_t \'{0}(/.*)?\'" \
        .format(os.path.join(env.indico_inst_dir, 'log')))
    run("semanage fcontext -a -t httpd_sys_content_t \'{0}(/.*)?\'" \
        .format(os.path.join(env.indico_inst_dir, 'tmp')))
    run("restorecon -Rv {0}".format(env.indico_inst_dir))
    run("restorecon -Rv {0}".format(env.db_inst_dir))
    run('setsebool -P httpd_can_network_connect 1')

    # Configure Redis
    pswd = _gen_random_pswd()
    _putl(os.path.join(env.config_dir, 'redis.conf'), '/etc')
    sed('/etc/redis.conf', '^(#)? *requirepass.*', "requirepass {0}".format(pswd))
    sed('/etc/redis.conf', '^(#)? *port.*', "port {0}".format(env.redis_port))
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'), '^(#)? *RedisConnectionURL.*', \
        "RedisConnectionURL = \"redis://unused:{0}@{1}:{2}/0\"".format(pswd, env.host_name, env.redis_port))
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'), '^(#)? *RedisCacheURL.*', \
        "RedisCacheURL = \"redis://unused:{0}@{1}:{2}/1\"".format(pswd, env.host_name, env.redis_port))


@task
def config(host_name=env.host_name, config_dir=env.config_dir, indico_inst_dir=env.indico_inst_dir,
           db_inst_dir=env.db_inst_dir, http_port_fwd=env.http_port_fwd, https_port_fwd=env.https_port_fwd):
    """
    Configure Indico and various aspects of the VM
    """

    indico_config(host_name, config_dir, indico_inst_dir, http_port_fwd, https_port_fwd)
    vm_config(host_name, config_dir, indico_inst_dir, db_inst_dir)

@task
def deploy(host_name=env.host_name, config_dir=env.config_dir, 
           indico_inst_dir=env.indico_inst_dir, db_inst_dir=None,
           http_port_fwd=env.http_port_fwd, https_port_fwd=env.https_port_fwd):
    """
    Deploy Indico into the VM
    """

    dependencies_inst()
    indico_inst(indico_inst_dir, db_inst_dir)
    config(host_name, config_dir, indico_inst_dir, db_inst_dir, http_port_fwd, https_port_fwd)

@task
def start_db(indico_inst_dir=env.indico_inst_dir):
    """
    Start the database
    """

    _update_params(indico_inst_dir=indico_inst_dir)

    run("zdaemon -C {0} start".format(os.path.join(env.indico_conf_dir, 'zdctl.conf')))

@task
def start_redis():
    """
    Start the Redis server
    """

    run('service redis start')

@task
def start_httpd():
    """
    Start Apache
    """

    run('service httpd start')

@task
def start(indico_inst_dir=env.indico_inst_dir, debug=env.debug):
    """
    Start Indico
    """

    _update_params(debug=debug)

    _update_ports()

    start_db(indico_inst_dir)
    start_redis()
    start_httpd()

@task
def run_vm(host_port_fwd=env.host_port_fwd, img_path=env.img_path,
           vd_path=env.vd_path, virtualization_cmd=env.virtualization_cmd,
           http_port_fwd=env.http_port_fwd, https_port_fwd=env.https_port_fwd, debug=env.debug):
    """
    Run the Virtual Machine
    """

    _update_params(host_port_fwd=host_port_fwd, img_path=img_path, \
                   vd_path=vd_path, virtualization_cmd=virtualization_cmd, \
                   http_port_fwd=http_port_fwd, https_port_fwd=https_port_fwd, debug=debug)

    local("echo \"\" > {0}".format(env.qemu_log))

    if env.debug:
        redir = " -redir tcp:{0}::{1} -redir tcp:{2}::{3}" \
                .format(env.http_port_fwd, env.http_port, env.https_port_fwd, env.https_port)
    else:
        redir = ""

    local(("{0} -m 256 -redir tcp:{4}::{5}{6} -net nic -net user, -drive file={1}" + \
          ",if=virtio -drive file={2},if=virtio -serial file:{3} -daemonize") \
          .format(env.virtualization_cmd, env.img_path, env.vd_path, env.qemu_log, env.host_port_fwd, env.host_port, redir))

    print("Booting up VM...")
    local("while ! grep -q \"Starting atd:.*[.*OK.*]\" \"{0}\"; do sleep 5; done" \
          .format(env.qemu_log))
    print("VM running!")

@task
def config_cloud_init(config_dir=env.config_dir, vd_path=env.vd_path):
    """
    Configure Cloud-Init files
    """

    _update_params(config_dir=config_dir, vd_path=vd_path)

    local("sed -i \'s|^password:.*|password: {0}|g\' {1}" \
          .format(env.password, os.path.join(env.config_dir, 'user-data')))
    local("mkisofs -output {0} -volid cidata -joliet -rock {1} {2}" \
          .format(env.vd_path, os.path.join(env.config_dir, 'user-data'), \
                  os.path.join(env.config_dir, 'meta-data')))

@task
def update_debug(debug=env.debug):
    """
    Update the VM configuration regarding the debug mode
    """

    _update_params(debug=debug)

    _update_ports()

@task
def launch(host_port_fwd=env.host_port_fwd, img_path=env.img_path, vd_path=env.vd_path,
           indico_inst_dir=env.indico_inst_dir, virtualization_cmd=env.virtualization_cmd,
           http_port_fwd=env.http_port_fwd, https_port_fwd=env.https_port_fwd, debug=env.debug):
    """
    Run the VM and start Indico
    """

    run_vm(host_port_fwd, img_path, vd_path, virtualization_cmd, http_port_fwd, https_port_fwd, debug)
    start(indico_inst_dir, debug)

@task
def set_up_vm(host_name=env.host_name, host_port_fwd=env.host_port_fwd, config_dir=env.config_dir,
              img_path=env.img_path, vd_path=env.vd_path, indico_inst_dir=env.indico_inst_dir,
              db_inst_dir=None, virtualization_cmd=env.virtualization_cmd, http_port_fwd=env.http_port_fwd,
              https_port_fwd=env.https_port_fwd, debug=env.debug):
    """
    Install and run Indico
    """

    config_cloud_init(config_dir, vd_path)
    run_vm(host_port_fwd, img_path, vd_path, virtualization_cmd, http_port_fwd, https_port_fwd, debug)
    deploy(host_name, config_dir, indico_inst_dir, db_inst_dir, http_port_fwd, https_port_fwd)
    start(indico_inst_dir, debug)
