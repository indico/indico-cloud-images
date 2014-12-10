# compatibility
from __future__ import print_function
try:
    input = raw_input
except NameError:
    pass

import argparse
import os
import re

from fabric.colors import cyan, green, red
from yaml import dump, load


tpl_dir = './tpl'


def _yes_no_input(message, default):
    c = '? '
    if default.lower() == 'y':
        c = ' [Y/n]? '
    elif default.lower() == 'n':
        c = ' [y/N]? '
    s = input(message+c) or default
    if s.lower() == 'y':
        return True
    else:
        return False


def _input_default(message, default):
    res = input("{0} [{1}]: ".format(message, default)) or default
    return res


def _read_file(fname):
    with open(fname, 'r') as f:
        return f.read()


def _add_tabs(old_content):
    new_content = ''
    for line in old_content.splitlines(True):
        new_line = line
        if line != '\n':
            new_line = '        ' + line
        new_content = new_content + new_line
    return new_content


def _get_ssh_key(fname):
    data = _read_file(fname).strip()
    if re.match(r'^ssh-\w+ [a-zA-Z0-9+/]+={0,2} \w+@\w+$', data):
        return data
    else:
        print(red("Key in '{0}' doesn't seem to be valid! It will be ignored.".format(fname)))
        return None


def config():
    # Interactive setup, so let's assume build dir to be ../build
    conf_dict = {
        'build_dir': '../build'
    }

    indico_inst_dir = _input_default('Insert the Indico installation directory path', '/opt/indico')
    db_inst_dir = _input_default('Insert the Indico DB installation directory path', '/opt/indico/db')

    httpd_conf_dir = _input_default('Insert the Apache conf directory', '/etc/httpd/conf')
    httpd_confd_dir = _input_default('Insert the Apache confd directory', '/etc/httpd/conf.d')

    ssl_certs_dir = _input_default('Insert the SSL cert directory', '/etc/ssl/certs')
    ssl_private_dir = _input_default('Insert the SSL private directory', '/etc/ssl/private')
    load_ssl = _yes_no_input('Do you want to load a personal SSL certificate', 'n')
    if load_ssl:
        pem_source = _input_default('Insert the source (local) path to the .pem file',
                                    'ssl/certs/ssl-cert-snakeoil.pem')
        key_source = _input_default('Insert the source (local) path to the .key file',
                                    'ssl/private/ssl-cert-snakeoil.key')
    else:
        pem_source = 'self-gen.pem'
        key_source = 'self-gen.key'

    enable_networking = _yes_no_input(
        'Do you want to enable networking on the machine (not needed for cloud deployment)', 'y')
    host_name = input('Insert the hostname: ')

    redis_host = _input_default('Insert the Redis hostname', 'localhost')
    redis_port = _input_default('Insert the Redis port', '6379')
    redis_pswd = input('Insert the Redis password: ')

    postfix = _yes_no_input('Do you want to use Postfix as mail server', 'y')
    if postfix:
        smtp_server_name = 'localhost'
    else:
        smtp_server_name = _input_default('Insert the SMTP server name', 'localhost')
    smtp_server_port = _input_default('Insert the SMTP server port', '25')
    smtp_login = input('Insert the SMTP login: ')
    smtp_pswd = input('Insert the SMTP password: ')

    conf_dict.update({
        'indico_inst_dir': indico_inst_dir,
        'enable_networking': enable_networking,
        'db_inst_dir': db_inst_dir,
        'httpd_conf_dir': httpd_conf_dir,
        'httpd_confd_dir': httpd_confd_dir,
        'ssl_certs_dir': ssl_certs_dir,
        'ssl_private_dir': ssl_private_dir,
        'load_ssl': load_ssl,
        'pem_source': pem_source,
        'key_source': key_source,
        'host_name': host_name,
        'redis_host': redis_host,
        'redis_port': redis_port,
        'redis_pswd': redis_pswd,
        'postfix': postfix,
        'smtp_server_name': smtp_server_name,
        'smtp_server_port': smtp_server_port,
        'smtp_login': smtp_login,
        'smtp_pswd': smtp_pswd
    })

    if _yes_no_input('Do you want to generate a configuration file from these data?', 'y'):
        conf_path = _input_default('Specify the configuration file path', 'gen-user-data.conf')

        d = os.path.dirname(conf_path)
        if (not os.path.exists(d)) & (d != ''):
            os.makedirs(d)

        with open(conf_path, 'w') as f:
            dump(conf_dict, f, default_flow_style=False)

    return conf_dict


def _gen_file(rules_dict, in_path, out_path):
    print("Generating {0}... ".format(os.path.basename(in_path)), end="")
    with open(in_path, 'r') as fin:
        with open(out_path, 'w+') as fout:
            fout.write(fin.read().format(**rules_dict))
    print(cyan("done".format(os.path.basename(in_path))))


def _gen_indico_httpd_conf(conf_dict):
    in_path = os.path.join(tpl_dir, 'indico_httpd.conf')
    out_path = os.path.join(conf_dict['build_dir'], 'indico_httpd.conf')
    rules_dict = {
        'indico_inst_dir': conf_dict['indico_inst_dir'],
        'ssl_pem_path': os.path.join(conf_dict['ssl_certs_dir'], os.path.basename(conf_dict['pem_source'])),
        'ssl_key_path': os.path.join(conf_dict['ssl_private_dir'], os.path.basename(conf_dict['key_source']))
    }

    _gen_file(rules_dict, in_path, out_path)


def _gen_indico_indico_conf(conf_dict):
    in_path = os.path.join(tpl_dir, 'indico_indico.conf')
    out_path = os.path.join(conf_dict['build_dir'], 'indico_indico.conf')
    rules_dict = {
        'redis_pswd': conf_dict['redis_pswd'],
        'redis_host': conf_dict['redis_host'],
        'redis_port': conf_dict['redis_port'],
        'host_name': conf_dict['host_name'],
        'indico_inst_dir': conf_dict['indico_inst_dir'],
        'smtp_server_name': conf_dict['smtp_server_name'],
        'smtp_server_port': conf_dict['smtp_server_port'],
        'smtp_login': conf_dict['smtp_login'],
        'smtp_pswd': conf_dict['smtp_pswd']
    }

    _gen_file(rules_dict, in_path, out_path)


def _gen_redis_conf(conf_dict):
    in_path = os.path.join(tpl_dir, 'redis.conf')
    out_path = os.path.join(conf_dict['build_dir'], 'redis.conf')
    rules_dict = {
        'redis_pswd': conf_dict['redis_pswd'],
        'redis_port': conf_dict['redis_port']
    }

    _gen_file(rules_dict, in_path, out_path)


def _gen_script(conf_dict):
    in_path = os.path.join(tpl_dir, 'user-data-script.sh')
    out_path = os.path.join(conf_dict['build_dir'], 'user-data-script.sh')
    rules_dict = {
        'indico_inst_dir': conf_dict['indico_inst_dir'],
        'db_inst_dir': conf_dict['db_inst_dir'],
        'httpd_conf_dir': conf_dict['httpd_conf_dir'],
        'httpd_confd_dir': conf_dict['httpd_confd_dir'],
        'host_name': conf_dict['host_name'],
        'ssl_certs_dir': conf_dict['ssl_certs_dir'],
        'ssl_private_dir': conf_dict['ssl_private_dir'],
        'load_ssl': str(conf_dict['load_ssl']).lower(),
        'ssl_pem_filename': os.path.basename(conf_dict['pem_source']),
        'ssl_key_filename': os.path.basename(conf_dict['key_source']),
        'postfix': str(conf_dict['postfix']).lower(),
        'smtp_server_port': conf_dict['smtp_server_port'],
        'enable_networking': str(conf_dict['enable_networking']).lower()
    }

    _gen_file(rules_dict, in_path, out_path)


def _gen_cloud_config_ssl(conf_dict):
    with open(conf_dict['pem_source'], 'r') as f:
        pem_content = _add_tabs(f.read())
    with open(conf_dict['key_source'], 'r') as f:
        key_content = _add_tabs(f.read())

    in_path = os.path.join(tpl_dir, 'cloud-config-ssl')
    out_path = os.path.join(conf_dict['build_dir'], 'cloud-config-ssl')
    rules_dict = {
        'pem_content': pem_content,
        'pem_filename': os.path.basename(conf_dict['pem_source']),
        'key_content': key_content,
        'key_filename': os.path.basename(conf_dict['key_source'])
    }

    _gen_file(rules_dict, in_path, out_path)


def _gen_cloud_config(conf_dict):
    content = {}

    for fname in ['indico_httpd.conf', 'indico_indico.conf', 'redis.conf']:
        content[fname] = _add_tabs(_read_file(os.path.join(conf_dict['build_dir'], fname)))

    content['ifcfg-ens3'] = _add_tabs(_read_file(os.path.join(tpl_dir, 'ifcfg-ens3')))

    if conf_dict['load_ssl']:
        _gen_cloud_config_ssl(conf_dict)
        ssl_files = _read_file(os.path.join(conf_dict['build_dir'], 'cloud-config-ssl'))
    else:
        ssl_files = ''

    key_list = conf_dict.get('ssh_keys', [])
    password = conf_dict.get('password')

    ssh_key_data = '\n'.join('  - {0}'.format(key) for key in (_get_ssh_key(k) for k in key_list) if key is not None)

    if ssh_key_data:
        ssh_key_data = "ssh_authorized_keys:\n{0}".format(ssh_key_data)

    in_path = os.path.join(tpl_dir, 'cloud-config')
    out_path = os.path.join(conf_dict['build_dir'], 'cloud-config')

    rules_dict = {
        'indico_httpd_conf_content': content['indico_httpd.conf'],
        'indico_indico_conf_content': content['indico_indico.conf'],
        'redis_conf_content': content['redis.conf'],
        'ifcfg_ens3_content': content['ifcfg-ens3'],
        'ssl_files': ssl_files,
        'ssh_key_data': ssh_key_data,
        'password': 'password: {0}'.format(password) if password else ''
    }

    _gen_file(rules_dict, in_path, out_path)


def _gen_config_files(conf_dict):
    _gen_indico_httpd_conf(conf_dict)
    _gen_indico_indico_conf(conf_dict)
    _gen_redis_conf(conf_dict)
    _gen_script(conf_dict)
    _gen_cloud_config(conf_dict)


def main():
    parser = argparse.ArgumentParser(description='Generate user-data file for cloud deployment of Indico.')
    parser.add_argument('--config', metavar='FILE', help='use an existing config file (YAML)')
    parser.add_argument('--output', metavar='FILE', default='user-data', help="output file (default: 'user-data')")

    args = parser.parse_args()

    if args.config:
        with open(args.config, 'r') as f:
            conf_dict = load(f)
    else:
        conf_dict = config()

    _gen_config_files(conf_dict)
    os.system("./write-mime-multipart --output {0}".format(args.output)
              + " {0}".format(os.path.join(conf_dict['build_dir'], 'user-data-script.sh'))
              + " {0}".format(os.path.join(conf_dict['build_dir'], 'cloud-config'))
              )
    print(green("Wrote '{}'.".format(args.output)))


if __name__ == '__main__':
    main()
