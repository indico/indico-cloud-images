# compatibility
from __future__ import print_function
try:
    input = raw_input
except NameError:
    pass

import argparse
import os

from fabric.colors import green
from yaml import dump, load

parser = argparse.ArgumentParser(description='Deploy Indico on the cloud.')
args = parser.parse_args()

conf_dir = '../conf'
tpl_dir = '../tpl'
vrule = '---------------------------------------------------'


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


def _add_tabs(old_content):
    new_content = ''
    for line in old_content.splitlines(True):
        new_line = line
        if line != '\n':
            new_line = '        ' + line
        new_content = new_content + new_line
    return new_content


def config():
    if _yes_no_input('Do you want to use a configuration file', 'n'):
        conf_path = _input_default('Specify the configuration file path', 'gen-user-data.conf')
        with open(conf_path, 'r') as f:
            conf_dict = load(f)
    else:
        indico_inst_dir = _input_default('Insert the Indico installation directory path', '/opt/indico')
        db_inst_dir = _input_default('Insert the Indico DB installation directory path', '/opt/indico/db')

        httpd_conf_dir = _input_default('Insert the Apache conf directory', '/etc/httpd/conf')
        httpd_confd_dir = _input_default('Insert the Apache confd directory', '/etc/httpd/conf.d')

        ssl_certs_dir = _input_default('Insert the SSL cert directory', '/etc/ssl/certs')
        ssl_private_dir = _input_default('Insert the SSL private directory', '/etc/ssl/private')
        load_ssl = _yes_no_input('Do you want to load a personal SSL certificate', 'n')
        if load_ssl:
            pem_source = _input_default('Insert the source (local) path to the .pem file', 'ssl/certs/ssl-cert-snakeoil.pem')
            key_source = _input_default('Insert the source (local) path to the .key file', 'ssl/private/ssl-cert-snakeoil.key')
        else:
            pem_source = 'self-gen.pem'
            key_source = 'self-gen.key'

        http_port = _input_default('Insert the http port', '80')
        https_port = _input_default('Insert the https port', '443')
        host_name = input('Insert the hostname: ')

        iptables_path = _input_default('Insert the iptables path', '/etc/sysconfig/iptables')

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

        yum_repos_dir = _input_default('Insert the YUM repositories directory', '/etc/yum.repos.d')
        puias_priority = _input_default('Insert the priority for the puias-unsupported repository', '19')

        conf_dict = {
            'indico_inst_dir': indico_inst_dir,
            'db_inst_dir': db_inst_dir,
            'httpd_conf_dir': httpd_conf_dir,
            'httpd_confd_dir': httpd_confd_dir,
            'ssl_certs_dir': ssl_certs_dir,
            'ssl_private_dir': ssl_private_dir,
            'load_ssl': load_ssl,
            'pem_source': pem_source,
            'key_source': key_source,
            'http_port': http_port,
            'https_port': https_port,
            'host_name': host_name,
            'iptables_path': iptables_path,
            'redis_host': redis_host,
            'redis_port': redis_port,
            'redis_pswd': redis_pswd,
            'yum_repos_dir': yum_repos_dir,
            'puias_priority': puias_priority,
            'postfix': postfix,
            'smtp_server_name': smtp_server_name,
            'smtp_server_port': smtp_server_port,
            'smtp_login': smtp_login,
            'smtp_pswd': smtp_pswd
        }

        if _yes_no_input('Do you want to generate a configuration file', 'y'):
            conf_path = _input_default('Specify the configuration file path', 'gen-user-data.conf')

            d = os.path.dirname(conf_path)
            if (not os.path.exists(d)) & (d != ''):
                os.makedirs(d)

            with open(conf_path, 'w') as f:
                dump(conf_dict, f, default_flow_style=False)

    return conf_dict


def _gen_file(rules_dict, in_path, out_path):
    print(vrule)
    print("Generating {0}".format(os.path.basename(in_path)))
    with open(in_path, 'r') as fin:
        with open(out_path, 'w+') as fout:
            fout.write(fin.read().format(**rules_dict))
    print(green("{0} generated".format(os.path.basename(in_path))))


def _gen_indico_httpd_conf(conf_dict):
    in_path = os.path.join(tpl_dir, 'indico_httpd.conf')
    out_path = os.path.join(conf_dir, 'indico_httpd.conf')
    rules_dict = {
        'virtualhost_http_port': "<VirtualHost *:{0}>".format(conf_dict['http_port']),
        'virtualhost_https_port': "<VirtualHost *:{0}>".format(conf_dict['https_port']),
        'indico_inst_dir': conf_dict['indico_inst_dir'],
        'ssl_pem_path': os.path.join(conf_dict['ssl_certs_dir'], os.path.basename(conf_dict['pem_source'])),
        'ssl_key_path': os.path.join(conf_dict['ssl_private_dir'], os.path.basename(conf_dict['key_source']))
    }

    _gen_file(rules_dict, in_path, out_path)


def _gen_indico_indico_conf(conf_dict):
    http = ':{0}'.format(conf_dict['http_port']) if conf_dict['http_port'] is not '80' else ''
    https = ':{0}'.format(conf_dict['https_port']) if conf_dict['https_port'] is not '443' else ''
    in_path = os.path.join(tpl_dir, 'indico_indico.conf')
    out_path = os.path.join(conf_dir, 'indico_indico.conf')
    rules_dict = {
        'redis_pswd': conf_dict['redis_pswd'],
        'redis_host': conf_dict['redis_host'],
        'redis_port': conf_dict['redis_port'],
        'host_name': conf_dict['host_name'],
        'http': http,
        'https': https,
        'indico_inst_dir': conf_dict['indico_inst_dir'],
        'smtp_server_name': conf_dict['smtp_server_name'],
        'smtp_server_port': conf_dict['smtp_server_port'],
        'smtp_login': conf_dict['smtp_login'],
        'smtp_pswd': conf_dict['smtp_pswd']
    }

    _gen_file(rules_dict, in_path, out_path)


def _gen_redis_conf(conf_dict):
    in_path = os.path.join(tpl_dir, 'redis.conf')
    out_path = os.path.join(conf_dir, 'redis.conf')
    rules_dict = {
        'redis_pswd': conf_dict['redis_pswd'],
        'redis_port': conf_dict['redis_port']
    }

    _gen_file(rules_dict, in_path, out_path)


def _gen_puias_repo(conf_dict):
    in_path = os.path.join(tpl_dir, 'puias.repo')
    out_path = os.path.join(conf_dir, 'puias.repo')
    rules_dict = {
        'puias_priority': conf_dict['puias_priority']
    }

    _gen_file(rules_dict, in_path, out_path)


def _gen_script(conf_dict):
    in_path = os.path.join(tpl_dir, 'user-data-script.sh')
    out_path = os.path.join(conf_dir, 'user-data-script.sh')
    rules_dict = {
        'indico_inst_dir': conf_dict['indico_inst_dir'],
        'yum_repos_dir': conf_dict['yum_repos_dir'],
        'db_inst_dir': conf_dict['db_inst_dir'],
        'httpd_conf_dir': conf_dict['httpd_conf_dir'],
        'httpd_confd_dir': conf_dict['httpd_confd_dir'],
        'host_name': conf_dict['host_name'],
        'ssl_certs_dir': conf_dict['ssl_certs_dir'],
        'ssl_private_dir': conf_dict['ssl_private_dir'],
        'load_ssl': str(conf_dict['load_ssl']).lower(),
        'ssl_pem_filename': os.path.basename(conf_dict['pem_source']),
        'ssl_key_filename': os.path.basename(conf_dict['key_source']),
        'iptables_path': conf_dict['iptables_path'],
        'http_port': conf_dict['http_port'],
        'https_port': conf_dict['https_port'],
        'postfix': str(conf_dict['postfix']).lower(),
        'smtp_server_port': conf_dict['smtp_server_port']
    }

    _gen_file(rules_dict, in_path, out_path)


def _gen_cloud_config_ssl(conf_dict):
    with open(conf_dict['pem_source'], 'r') as f:
        pem_content = _add_tabs(f.read())
    with open(conf_dict['key_source'], 'r') as f:
        key_content = _add_tabs(f.read())

    in_path = os.path.join(tpl_dir, 'cloud-config-ssl')
    out_path = os.path.join(conf_dir, 'cloud-config-ssl')
    rules_dict = {
        'pem_content': pem_content,
        'pem_filename': os.path.basename(conf_dict['pem_source']),
        'key_content': key_content,
        'key_filename': os.path.basename(conf_dict['key_source'])
    }

    _gen_file(rules_dict, in_path, out_path)


def _gen_cloud_config(conf_dict):
    with open(os.path.join(conf_dir, 'puias.repo'), 'r') as f:
        puias_repo_content = _add_tabs(f.read())
    with open(os.path.join(conf_dir, 'indico_httpd.conf'), 'r') as f:
        indico_httpd_conf_content = _add_tabs(f.read())
    with open(os.path.join(conf_dir, 'indico_indico.conf'), 'r') as f:
        indico_indico_conf_content = _add_tabs(f.read())
    with open(os.path.join(conf_dir, 'redis.conf'), 'r') as f:
        redis_conf_content = _add_tabs(f.read())
    with open(os.path.join(conf_dir, 'ssl.conf'), 'r') as f:
        ssl_conf_content = _add_tabs(f.read())

    ssl_files = ''
    if conf_dict['load_ssl']:
        _gen_cloud_config_ssl(conf_dict)
        with open(os.path.join(conf_dir, 'cloud-config-ssl'), 'r') as f:
            ssl_files = f.read()

    in_path = os.path.join(tpl_dir, 'cloud-config')
    out_path = os.path.join(conf_dir, 'cloud-config')
    rules_dict = {
        'puias_repo_content': puias_repo_content,
        'indico_httpd_conf_content': indico_httpd_conf_content,
        'indico_indico_conf_content': indico_indico_conf_content,
        'redis_conf_content': redis_conf_content,
        'ssl_conf_content': ssl_conf_content,
        'ssl_files': ssl_files
    }

    _gen_file(rules_dict, in_path, out_path)


def _gen_config_files(conf_dict):
    _gen_indico_httpd_conf(conf_dict)
    _gen_indico_indico_conf(conf_dict)
    _gen_redis_conf(conf_dict)
    _gen_puias_repo(conf_dict)
    _gen_script(conf_dict)
    _gen_cloud_config(conf_dict)


def main():
    conf_dict = config()
    mime_path = _input_default('Choose a path for the MIME file', "user-data")
    print('---------- Starting MIME file generation ----------')
    _gen_config_files(conf_dict)
    os.system("./write-mime-multipart --output {0}".format(mime_path)
              + " {0}".format(os.path.join(conf_dir, 'user-data-script.sh'))
              + " {0}".format(os.path.join(conf_dir, 'cloud-config'))
              )
    print(vrule)
    print(green('--------------- MIME file generated ---------------'))


if __name__ == '__main__':
    main()
