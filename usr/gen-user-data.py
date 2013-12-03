import argparse
import os
import ast
from distutils.util import strtobool

parser = argparse.ArgumentParser(description='Deploy Indico on the cloud.')
args = parser.parse_args()

def _yes_no_input(message, default):
    c = '? '
    if default.lower() == 'y':
        c = ' [Y/n]? '
    elif default.lower() == 'n':
        c = ' [y/N]? '
    s = raw_input(message+c) or default
    return strtobool(s.lower())

def _input_default(message, default):
    res = raw_input("{0} [{1}]: ".format(message, default)) or default
    return res

def config():
    if _yes_no_input('Do you want to use a configuration file', 'n'):
        conf_path = _input_default('Specify the configuration file path', 'gen-user-data.conf')
        with open(conf_path) as f:
            conf_dict = ast.literal_eval(f.read())
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
        host_name = raw_input('Insert the hostname: ')

        iptables_path = _input_default('Insert the iptables path', '/etc/sysconfig/iptables')

        redis_host = _input_default('Insert the Redis hostname', 'localhost')
        redis_port = _input_default('Insert the Redis port', '6379')
        redis_pswd = raw_input('Insert the Redis password: ')

        yum_repos_dir = _input_default('Insert the YUM repositories directory', '/etc/yum.repos.d')
        puias_priority = _input_default('Insert the priority for the puias-unsupported repository', '19')

        conf_dict = {
            'indico_inst_dir'   :   indico_inst_dir,
            'db_inst_dir'       :   db_inst_dir,
            'httpd_conf_dir'    :   httpd_conf_dir,
            'httpd_confd_dir'   :   httpd_confd_dir,
            'ssl_certs_dir'     :   ssl_certs_dir,
            'ssl_private_dir'   :   ssl_private_dir,
            'load_ssl'          :   str(load_ssl),
            'pem_source'        :   pem_source,
            'key_source'        :   key_source,
            'http_port'         :   http_port,
            'https_port'        :   https_port,
            'host_name'         :   host_name,
            'iptables_path'     :   iptables_path,
            'redis_host'        :   redis_host,
            'redis_port'        :   redis_port,
            'redis_pswd'        :   redis_pswd,
            'yum_repos_dir'     :   yum_repos_dir,
            'puias_priority'    :   puias_priority
        }

        if _yes_no_input('Do you want to generate a configuration file', 'y'):
            conf_path = _input_default('Specify the configuration file path', 'gen-user-data.conf')

            d = os.path.dirname(conf_path)
            if (not os.path.exists(d)) & (d != ''):
                os.makedirs(d)

            with open(conf_path, 'w+') as f:
                f.write(str(conf_dict))

    return conf_dict

def _fill_values(rules_dict, line):
    for key in rules_dict.keys():
        line = line.replace(key, rules_dict[key])
    return line

def _gen_file(rules_dict, in_path, out_path):
    with open(in_path, 'r') as fin:
        with open(out_path, 'w+') as fout:
            for line in fin:
                line = _fill_values(rules_dict, line)
                fout.write(line)

def _gen_indico_httpd_conf(conf_dict):
    in_path = 'tpl/indico_httpd.conf'
    out_path = 'config/indico_httpd.conf'
    rules_dict = {
        '# VIRTUALHOST_HTTP_PORT #'     :   "<VirtualHost *:{0}>".format(conf_dict['http_port']),
        '# VIRTUALHOST_HTTPS_PORT #'    :   "<VirtualHost *:{0}>".format(conf_dict['https_port']),
        '# INDICO_INST_DIR #'           :   conf_dict['indico_inst_dir'],
        '# SSL_PEM_PATH #'              :   os.path.join(conf_dict['ssl_certs_dir'], os.path.basename(conf_dict['pem_source'])),
        '# SSL_KEY_PATH #'              :   os.path.join(conf_dict['ssl_private_dir'], os.path.basename(conf_dict['key_source']))
    }

    _gen_file(rules_dict, in_path, out_path)

def _gen_indico_indico_conf(conf_dict):
    in_path = 'tpl/indico_indico.conf'
    out_path = 'config/indico_indico.conf'
    rules_dict = {
        '# REDIS_CONNECTION_URL #'  :   "RedisConnectionURL = \'redis://unused:{0}@{1}:{2}/0\'" \
                                        .format(conf_dict['redis_pswd'], conf_dict['redis_host'], conf_dict['redis_port']),
        '# BASE_URL #'              :   "BaseURL = \"http://{0}:{1}/indico\"".format(conf_dict['host_name'], conf_dict['http_port']),
        '# BASE_SECURE_URL #'       :   "BaseSecureURL = \"http://{0}:{1}/indico\"".format(conf_dict['host_name'], conf_dict['https_port']),
        '# LOGIN_URL #'             :   "LoginURL = \"https://{0}:{1}/indico/signIn.py\"" \
                                        .format(conf_dict['host_name'], conf_dict['https_port']),
        '# INDICO_INST_DIR #'       :   conf_dict['indico_inst_dir'],
        '# REDIS_CACHE_URL #'       :   "RedisCacheURL = \'redis://unused:{0}@{1}:{2}/1\'" \
                                        .format(conf_dict['redis_pswd'], conf_dict['redis_host'], conf_dict['redis_port'])
    }

    _gen_file(rules_dict, in_path, out_path)

def _gen_redis_conf(conf_dict):
    in_path = 'tpl/redis.conf'
    out_path = 'config/redis.conf'
    rules_dict = {
        '# REDIS_PSWD #'    :   conf_dict['redis_pswd'],
        '# REDIS_PORT #'    :   conf_dict['redis_port']
    }
    
    _gen_file(rules_dict, in_path, out_path)

def _gen_script(conf_dict):
    in_path = 'tpl/user-data-script.sh'
    out_path = 'config/user-data-script.sh'
    rules_dict = {
        '# INDICO_INST_DIR #'   :   conf_dict['indico_inst_dir'],
        '# DB_INST_DIR #'       :   conf_dict['db_inst_dir'],
        '# HTTPD_CONF_DIR #'    :   conf_dict['httpd_conf_dir'],
        '# HOST_NAME #'         :   conf_dict['host_name'],
        '# SSL_CERTS_DIR #'     :   conf_dict['ssl_certs_dir'],
        '# SSL_PRIVATE_DIR #'   :   conf_dict['ssl_private_dir'],
        '# LOAD_SSL #'          :   conf_dict['load_ssl'].lower(),
        '# SSL_PEM_PATH #'      :   os.path.join(conf_dict['ssl_certs_dir'], os.path.basename(conf_dict['pem_source'])),
        '# SSL_KEY_PATH #'      :   os.path.join(conf_dict['ssl_private_dir'], os.path.basename(conf_dict['key_source'])),
        '# IPTABLES_PATH #'     :   conf_dict['iptables_path'],
        '# HTTP_PORT #'         :   conf_dict['http_port'],
        '# HTTPS_PORT #'        :   conf_dict['https_port']
    }

    _gen_file(rules_dict, in_path, out_path)

def _gen_cloud_config(conf_dict):
    with open('config/indico_httpd.conf', 'r') as f:
        indico_httpd_conf_content = f.read()
    with open('config/indico_indico.conf', 'r') as f:
        indico_indico_conf_content = f.read()
    with open('config/redis.conf', 'r') as f:
        redis_conf_content = f.read()
    with open('config/ssl.conf', 'r') as f:
        ssl_conf_content = f.read()

    in_path = 'tpl/cloud-config'
    out_path = 'config/cloud-config'
    rules_dict = {
        '# PUIAS_PRIORITY #'                :   conf_dict['puias_priority'],
        '# HTTPD_CONFD_DIR #'               :   conf_dict['httpd_confd_dir'],
        '# INDICO_INST_DIR #'               :   conf_dict['indico_inst_dir'],
        '# INDICO_HTTPD_CONF_CONTENT #'     :   indico_httpd_conf_content,
        '# INDICO_INDICO_CONF_CONTENT #'    :   indico_indico_conf_content,
        '# REDIS_CONF_CONTENT #'            :   redis_conf_content,
        '# SSL_CONF_CONTENT #'              :   ssl_conf_content
    }

    _gen_file(rules_dict, in_path, out_path)

def _gen_config_files(conf_dict):
    _gen_indico_httpd_conf(conf_dict)
    _gen_indico_indico_conf(conf_dict)
    _gen_redis_conf(conf_dict)
    _gen_script(conf_dict)
    _gen_cloud_config(conf_dict)

def main():
    conf_dict = config()
    _gen_config_files(conf_dict)
    mime_path = _input_default('Choose a path for the MIME file', "mime-user-data.gz")
    os.system("./write-mime-multipart -z --output {0}".format(mime_path) \
              + " config/user-data-script.sh" \
              + " config/cloud-config" \
              # + " config/put-file-handler.py" \
              # + " config/indico_httpd.conf:text/plain" \
              # + " config/indico_indico.conf:text/plain" \
              # + " config/redis.conf:text/plain" \
              # + " config/ssl.conf:text/plain"
    )

if __name__ == '__main__':
    main()
