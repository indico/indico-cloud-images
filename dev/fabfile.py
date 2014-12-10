import os
import re
import uuid
import socket
import time

from fabric.api import *
from fabric.contrib.files import sed
from fabric.operations import put, run
from fabric.context_managers import settings
from fabric.colors import yellow, green


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


def _wait_for(fin, pattern, log_file):
    for line in fin:
        log_file.write(line)
        log_file.flush()
        if re.match(pattern, line):
            break


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

    socket_path = './log_socket'

    local("rm -f {0} {1}".format(socket_path, env.qemu_log))

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    # if in debug mode, redirect to local port (for testing)
    if env.debug_vm:
        redir = " -redir tcp:{0}::{1} -redir tcp:{2}::{3}" \
                .format(env.host_machine['http_port'], env.guest_machine['http_port'],
                        env.host_machine['https_port'], env.guest_machine['https_port'])
    else:
        redir = ""

    local(("{0} -m 1024 -redir tcp:{4}::{5}{6} -net nic -net user, -drive file={1}" +
          ",if=virtio -drive file='{2}',if=virtio -serial unix:{3},server &")
          .format(env.virtualization_cmd, env.img_path, env.vd_path, socket_path,
                  env.host_machine['ssh_port'], env.guest_machine['ssh_port'], redir))

    print(yellow("Connecting to VM log..."))

    # Wait for QEMU to create the Unix socket
    time.sleep(2)

    sock.connect(socket_path)

    print(green("Connected to system log. See '{0}' for details.".format(env.qemu_log)))

    sock_f = sock.makefile()

    with open(env.qemu_log, 'w') as log_file:
        _wait_for(sock_f, r'^cloud-init', log_file)
        print(green('Cloud-init running'))

        _wait_for(sock_f, r'.*indico-cloud-init: start config', log_file)
        print(green('Indico configuration started'))

        _wait_for(sock_f, r'.*indico-cloud-init: config done', log_file)
        print(green('Indico configuration finished!'))

    print(green("VM running!"))


@task
def config_no_cloud(user_data, **params):
    """
    cloud-init no-cloud fake config
    """

    _update_params(**params)

    local("mkisofs -output {0} -volid cidata -joliet -rock {1} {2}"
          .format(env.vd_path, user_data,
                  os.path.join(env.conf_dir, 'meta-data')))


def cleanup_vm():
    with settings(warn_only=True):
        sudo('rm -f /etc/sysconfig/network-scripts/ifcfg-ens3')
    sudo('shutdown -h now')


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
def create_vm_img(user_data, **params):
    """
    Creates a Virtual Image ready to be deployed on the cloud
    """

    config_no_cloud(user_data, **params)
    launch_vm(**params)
    cleanup_vm()
