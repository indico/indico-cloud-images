from fabric.api import *
from fabric.contrib.files import sed
from fabric.operations import put, run
import os

env.user_name = 'root'
env.host_name = '127.0.0.1'
env.host_port = '2222'
env.http_port = '8000'
env.https_port = '8443'
env.hosts = ["{0}@{1}:{2}".format(env.user_name, env.host_name, env.host_port)]

env.config_dir = 'config'
env.img_dir = 'img'
env.img_name = 'SLC6.qcow2'
env.img_path = os.path.join(env.img_dir, env.img_name)
env.vd_name = 'init.iso'
env.vd_path = os.path.join(env.img_dir, env.vd_name)


env.indico_inst_dir = '/opt/indico'
env.db_inst_dirname = 'db'
env.db_inst_dir = os.path.join(env.indico_inst_dir, env.db_inst_dirname)

env.indico_conf_dirname = 'etc'
env.indico_conf_dir = os.path.join(env.indico_inst_dir, env.indico_conf_dirname)
env.httpd_conf_dir = '/etc/httpd/conf'
env.httpd_confd_dir = '/etc/httpd/conf.d'
env.iptables_dir = '/etc/sysconfig'
env.ssl_dir = '/etc/ssl'
env.ssl_cert_dirname = 'certs'
env.ssl_cert_dir = os.path.join(env.ssl_dir, env.ssl_cert_dirname)
env.ssl_private_dirname = 'private'
env.ssl_private_dir = os.path.join(env.ssl_dir, env.ssl_private_dirname)

env.virtualization_cmd = 'kvm'

def _args_setup(host_name=env.host_name, host_port=env.host_port, config_dir=env.config_dir,
                img_path=env.img_path, vd_path=env.vd_path, indico_inst_dir=env.indico_inst_dir,
                db_inst_dir=None, virtualization_cmd=env.virtualization_cmd, http_port=env.http_port,
                https_port=env.https_port):
    env.host_name = host_name
    env.host_port = host_port
    env.hosts[0] = "{0}@{1}:{2}".format(env.user_name, env.host_name, env.host_port)
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
    env.http_port = http_port
    env.https_port = https_port
    

def dependencies_inst():
    """
    Dependencies installation
    """

    run('yum -y install python-devel.x86_64 gcc.x86_64 httpd.x86_64 mod_wsgi.x86_64 \
        python-reportlab.x86_64 python-imaging.x86_64 python-lxml.x86_64 mod_ssl.x86_64')
    run('easy_install ZODB3==3.10.5 zc.queue==1.3')

def indico_inst(indico_inst_dir=env.indico_inst_dir, db_inst_dir=None):
    """
    Indico installation and first setup
    """

    _args_setup(indico_inst_dir=indico_inst_dir, db_inst_dir=db_inst_dir)

    run('easy_install indico')
    run("echo -e \"{0}\nc\ny\n{1}\" | indico_initial_setup"\
        .format(env.indico_inst_dir, env.db_inst_dir))


def indico_config(host_name=env.host_name, config_dir=env.config_dir,
                  indico_inst_dir=env.indico_inst_dir, db_inst_dir=env.indico_inst_dir,
                  http_port=env.http_port, https_port=env.https_port):
    """
    Configure Indico and the database
    """

    _args_setup(host_name=host_name, config_dir=config_dir, indico_inst_dir=indico_inst_dir, \
                db_inst_dir=db_inst_dir, http_port=http_port, https_port=https_port)

    # Moving and modifying the Indico Apache .conf file
    put(os.path.join(env.config_dir, 'indico.conf'), env.httpd_confd_dir)
    sed(os.path.join(env.httpd_confd_dir, 'indico.conf'), '/opt/indico', env.indico_inst_dir)
    sed(os.path.join(env.httpd_confd_dir, 'indico.conf'), '/etc/ssl/certs', env.ssl_cert_dir)
    sed(os.path.join(env.httpd_confd_dir, 'indico.conf'), '/etc/ssl/private', env.ssl_private_dir)

    # Self-generating an ssl certificate
    run("mkdir -p {0}".format(env.ssl_cert_dir))
    run("mkdir -p {0}".format(env.ssl_private_dir))
    run("openssl req -new -x509 -nodes -out {0} -keyout {1} -days 3650 -subj \'/CN={2}\'" \
        .format (os.path.join(env.ssl_cert_dir, 'self-gen.pem'), \
                 os.path.join(env.ssl_private_dir, 'self-gen.key'), \
                 env.host_name))

    # Adding a ServerName in httpd.conf
    sed(os.path.join(env.httpd_conf_dir, 'httpd.conf'), \
        '#ServerName www.example.com:80', \
        "ServerName {0}".format(env.host_name))

    # Adding the ports 80 and 443 to the iptables
    run("sed \"11i\\-A INPUT -m state --state NEW -m tcp -p tcp --dport 80 -j ACCEPT\" {0} > {1}" \
        .format(os.path.join(env.iptables_dir, 'iptables'), os.path.join(env.iptables_dir, 'temp')))
    run("mv -f {0} {1}"\
        .format(os.path.join(env.iptables_dir, 'temp'), os.path.join(env.iptables_dir, 'iptables')))
    run("sed \"12i\\-A INPUT -m state --state NEW -m tcp -p tcp --dport 443 -j ACCEPT\" {0} > {1}" \
        .format(os.path.join(env.iptables_dir, 'iptables'), os.path.join(env.iptables_dir, 'temp')))
    run("mv -f {0} {1}"\
        .format(os.path.join(env.iptables_dir, 'temp'), os.path.join(env.iptables_dir, 'iptables')))
    run('service iptables restart')

    # Adding the corresponding ports to indico.conf
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'), \
        'BaseURL              = \"http://localhost/indico\"', \
        "BaseURL              = \"http://{0}:{1}/indico\"" \
        .format(env.host_name, env.http_port))
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'), \
        'BaseSecureURL        = \"https://localhost/indico\"', \
        "BaseSecureURL        = \"https://{0}:{1}/indico\"" \
        .format(env.host_name, env.https_port))
    sed(os.path.join(env.indico_conf_dir, 'indico.conf'), \
        '#   LoginURL             = \"\"', \
        "LoginURL             = \"https://{0}:{1}/indico/signIn.py\"" \
        .format(env.host_name, env.https_port))

    # Modifying the ssl.conf file
    put(os.path.join(env.config_dir, 'ssl.conf'), env.httpd_confd_dir)

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

def deploy(host_name=env.host_name, config_dir=env.config_dir, 
           indico_inst_dir=env.indico_inst_dir, db_inst_dir=None,
           http_port=env.http_port, https_port=env.https_port):
    """
    Deploy Indico into the VM
    """

    dependencies_inst()
    indico_inst(indico_inst_dir, db_inst_dir)
    indico_config(host_name, config_dir, indico_inst_dir, db_inst_dir, http_port, https_port)

def start_db(indico_inst_dir=env.indico_inst_dir):
    """
    Start the database
    """

    _args_setup(indico_inst_dir=indico_inst_dir)

    run("zdaemon -C {0} start".format(os.path.join(env.indico_conf_dir, 'zdctl.conf')))

def start_httpd():
    """
    Start Apache
    """

    run('service httpd start')

def start(indico_inst_dir=env.indico_inst_dir):
    """
    Start Indico
    """

    start_db(indico_inst_dir)
    start_httpd()

def run_vm(host_port=env.host_port, img_path=env.img_path,
           vd_path=env.vd_path, virtualization_cmd=env.virtualization_cmd,
           http_port=env.http_port, https_port=env.https_port):
    """
    Run the Virtual Machine
    """

    _args_setup(host_port=host_port, img_path=img_path, \
                vd_path=vd_path, virtualization_cmd=virtualization_cmd, \
                http_port=http_port, https_port=https_port)

    local("{0} -m 256 -redir tcp:{1}::22 -redir tcp:{2}::80 -redir tcp:{3}::443 \
          -net nic -net user, -drive file={4},if=virtio -drive file={5},if=virtio" \
          .format(env.virtualization_cmd, env.host_port, env.http_port, \
                  env.https_port, env.img_path, env.vd_path))

def config_cloud_init(config_dir=env.config_dir, vd_path=env.vd_path):
    """
    Configure Cloud-Init files
    """

    _args_setup(config_dir=config_dir, vd_path=vd_path)

    local("mkisofs -output {0} -volid cidata -joliet -rock {1} {2}" \
          .format(env.vd_path, os.path.join(env.config_dir, 'user-data'), \
                  os.path.join(env.config_dir, 'meta-data')))

def set_up_vm(host_name=env.host_name, host_port=env.host_port, config_dir=env.config_dir,
              img_path=env.img_path, vd_path=env.vd_path, indico_inst_dir=env.indico_inst_dir,
              db_inst_dir=None, virtualization_cmd=env.virtualization_cmd, http_port=env.http_port,
              https_port=env.https_port):
    """
    Install and run Indico
    """

    config_cloud_init(config_dir, vd_path)
    run_vm(host_port, img_path, vd_path, virtualization_cmd, http_port, https_port)
    # something that makes the fabfile wait till the bootup is complete
    deploy(host_name, config_dir, indico_inst_dir, db_inst_dir, http_port, https_port)
    start(indico_inst_dir)
