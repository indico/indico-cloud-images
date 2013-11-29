import argparse
import shutil
import os
import ast

parser = argparse.ArgumentParser(description='Deploy Indico on the cloud.')
args = parser.parse_args()

def _yes_no_input(message, default):
    c = '? '
    if default.lower() == 'y':
        c = ' [Y/n]? '
    elif default.lower() == 'n':
        c = ' [y/N]? '
    s = raw_input(message+c) or default
    if s.lower() == 'y':
        return True
    elif s.lower() == 'n':
        return False

def _input_default(message, default):
    res = raw_input("{0} [{1}]: ".format(message, default)) or default
    return res

def config():
    if _yes_no_input('Do you want to use a configuration file', 'n'):
        conf_path = _input_default('Specify the configuration file path', 'gen-user-data.conf')
        conf_file = open(conf_path)
        conf_dict = ast.literal_eval(conf_file.read())
        conf_file.close()
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

            f = open(conf_path, 'w+')
            # f.write("indico_inst_dir = {0}\n".format(indico_inst_dir) + \
            #         "db_inst_dir = {0}\n".format(db_inst_dir) + \
            #         "httpd_conf_dir = {0}\n".format(httpd_conf_dir) + \
            #         "httpd_confd_dir = {0}\n".format(httpd_confd_dir) + \
            #         "ssl_certs_dir = {0}\n".format(ssl_certs_dir) + \
            #         "ssl_private_dir = {0}\n".format(ssl_private_dir) + \
            #         "load_ssl = {0}\n".format(load_ssl) + \
            #         "pem_source = {0}\n".format(pem_source) + \
            #         "key_source = {0}\n".format(key_source) + \
            #         "http_port = {0}\n".format(http_port) + \
            #         "https_port = {0}\n".format(https_port) + \
            #         "host_name = {0}\n".format(host_name) + \
            #         "iptables_path = {0}\n".format(iptables_path) + \
            #         "redis_host = {0}\n".format(redis_host) + \
            #         "redis_port = {0}\n".format(redis_port) + \
            #         "redis_pswd = {0}\n".format(redis_pswd) + \
            #         "yum_repos_dir = {0}\n".format(yum_repos_dir) + \
            #         "puias_priority = {0}".format(puias_priority))
            f.write(str(conf_dict))

    return conf_dict

def _gen_indico_httpd_conf(conf_dict):
    fin = open('tpl/indico_httpd.conf', 'r')
    fout = open('config/indico_httpd.conf', 'w+')

    fout.write("#DestinationPath = {0}\n".format(os.path.join(conf_dict['httpd_confd_dir'], 'indico.conf')))
    for line in fin:
        line = line.replace('# VIRTUALHOST_HTTP_PORT #', "<VirtualHost *:{0}>".format(conf_dict['http_port']))
        line = line.replace('# VIRTUALHOST_HTTPS_PORT #', "<VirtualHost *:{0}>".format(conf_dict['https_port']))
        line = line.replace('# INDICO_INST_DIR #', conf_dict['indico_inst_dir'])
        line = line.replace('# SSL_PEM_PATH #', os.path.join(conf_dict['ssl_certs_dir'], os.path.basename(conf_dict['pem_source'])))
        line = line.replace('# SSL_KEY_PATH #', os.path.join(conf_dict['ssl_private_dir'], os.path.basename(conf_dict['key_source'])))
        fout.write(line)

    fin.close()
    fout.close()

def _gen_indico_indico_conf(conf_dict):
    fin = open('tpl/indico_indico.conf', 'r')
    fout = open('config/indico_indico.conf', 'w+')

    fout.write("#DestinationPath = {0}\n".format(os.path.join(conf_dict['indico_inst_dir'], 'etc/indico.conf')))
    for line in fin:
        line = line.replace('# REDIS_CONNECTION_URL #', "RedisConnectionURL = \'redis://unused:{0}@{1}:{2}/0\'" \
                                                        .format(conf_dict['redis_pswd'], conf_dict['redis_host'], conf_dict['redis_port']))
        line = line.replace('# BASE_URL #', "BaseURL = \"http://{0}:{1}/indico\"".format(conf_dict['host_name'], conf_dict['http_port']))
        line = line.replace('# BASE_SECURE_URL #', "BaseSecureURL = \"http://{0}:{1}/indico\"" \
                                                   .format(conf_dict['host_name'], conf_dict['https_port']))
        line = line.replace('# LOGIN_URL #', "LoginURL = \"https://{0}:{1}/indico/signIn.py\"" \
                                             .format(conf_dict['host_name'], conf_dict['https_port']))
        line = line.replace('# INDICO_INST_DIR #', conf_dict['indico_inst_dir'])
        line = line.replace('# REDIS_CACHE_URL #', "RedisCacheURL = \'redis://unused:{0}@{1}:{2}/1\'" \
                                                   .format(conf_dict['redis_pswd'], conf_dict['redis_host'], conf_dict['redis_port']))
        fout.write(line)

    fin.close()
    fout.close()

def _gen_redis_conf(conf_dict):
    fin = open('tpl/redis.conf', 'r')
    fout = open('config/redis.conf', 'w+')

    fout.write("#DestinationPath = /etc/redis.conf\n")
    for line in fin:
        line = line.replace('# REDIS_PSWD #', conf_dict['redis_pswd'])
        line = line.replace('# REDIS_PORT #', conf_dict['redis_port'])
        fout.write(line)

    fin.close()
    fout.close()

def _gen_ssl_conf(conf_dict):
    fin = open('tpl/ssl.conf', 'r')
    fout = open('config/ssl.conf', 'w+')

    fout.write("#DestinationPath = {0}\n".format(os.path.join(conf_dict['httpd_confd_dir'], 'ssl.conf')))
    for line in fin:
        fout.write(line)

    fin.close()
    fout.close()

def _gen_script(conf_dict):
    fin = open('tpl/user-data-script.sh', 'r')
    fout = open('config/user-data-script.sh', 'w+')

    for line in fin:
        line = line.replace('# INDICO_INST_DIR #', conf_dict['indico_inst_dir'])
        line = line.replace('# DB_INST_DIR #', conf_dict['db_inst_dir'])
        line = line.replace('# HTTPD_CONF_DIR #', conf_dict['httpd_conf_dir'])
        line = line.replace('# HOST_NAME #', conf_dict['host_name'])
        line = line.replace('# SSL_CERTS_DIR #', conf_dict['ssl_certs_dir'])
        line = line.replace('# SSL_PRIVATE_DIR #', conf_dict['ssl_private_dir'])
        line = line.replace('# LOAD_SSL #', conf_dict['load_ssl'].lower())
        line = line.replace('# SSL_PEM_PATH #', os.path.join(conf_dict['ssl_certs_dir'], os.path.basename(conf_dict['pem_source'])))
        line = line.replace('# SSL_KEY_PATH #', os.path.join(conf_dict['ssl_private_dir'], os.path.basename(conf_dict['key_source'])))
        line = line.replace('# IPTABLES_PATH #', conf_dict['iptables_path'])
        line = line.replace('# HTTP_PORT #', conf_dict['http_port'])
        line = line.replace('# HTTPS_PORT #', conf_dict['https_port'])
        fout.write(line)

    fin.close()
    fout.close()

def _gen_cloud_config(conf_dict):
    fin = open('tpl/cloud-config', 'r')
    fout = open('config/cloud-config', 'w+')

    for line in fin:
        line = line.replace('# PUIAS_PRIORITY #', conf_dict['puias_priority'])
        fout.write(line)

    fin.close()
    fout.close()

def _gen_config_files(conf_dict):
    _gen_indico_httpd_conf(conf_dict)
    _gen_indico_indico_conf(conf_dict)
    _gen_redis_conf(conf_dict)
    _gen_ssl_conf(conf_dict)
    _gen_script(conf_dict)
    _gen_cloud_config(conf_dict)

def main():
    conf_dict = config()
    _gen_config_files(conf_dict)
    mime_path = _input_default('Choose a path for the MIME file', "mime-user-data")
    os.system("./write-mime-multipart --output {0} config/cloud-config config/put-file-handler.py config/indico_httpd.conf:text/plain \
              config/indico_indico.conf:text/plain config/redis.conf:text/plain config/ssl.conf:text/plain config/user-data-script.sh" \
              .format(mime_path))

if __name__ == '__main__':
    main()
