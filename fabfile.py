from fabric.api import *
from fabric.contrib.files import append, sed
from fabric.operations import put, run

env.user_name = 'root'
env.host_name = 'localhost'
env.hosts = ['%s@%s:2222' % (env.user_name, env.host_name)]
env.config_dir = 'config/'
env.img_dir = 'img/'
env.indico_conf_dir = '/opt/indico/etc/'
env.httpd_conf_dir = '/etc/httpd/conf/'
env.httpd_confd_dir = '/etc/httpd/conf.d/'
env.iptables_dir = '/etc/sysconfig/'
env.ssl_dir = '/etc/ssl/'

# Dependencies installation
def dependencies_inst():
	run('yum -y install python-devel.x86_64 gcc.x86_64 httpd.x86_64 mod_wsgi.x86_64 \
	    python-reportlab.x86_64 python-imaging.x86_64 python-lxml.x86_64 mod_ssl.x86_64')
	run('easy_install ZODB3==3.10.5 zc.queue==1.3')

# Indico installation and first setup
def indico_inst():
	run('easy_install indico')
	run('indico_initial_setup')


# Configure Indico and the database
def config_indico():
	# Moving the Indico Apache .conf file
	put('%sindico.conf' % env.config_dir, env.httpd_confd_dir)

	# Self-generating an ssl certificate
	run('mkdir -p %scerts' % env.ssl_dir)
	run('mkdir -p %sprivate' % env.ssl_dir)
	run('openssl req -new -x509 -nodes -out %scerts/self-gen.pem \
	    -keyout %sprivate/self-gen.key -days 3650 -subj \'/CN=%s\'' %
	    (env.ssl_dir, env.ssl_dir, env.host_name))

	# Adding a ServerName in httpd.conf
	sed('%shttpd.conf' % env.httpd_conf_dir, \
		'#ServerName www.example.com:80', \
		'ServerName %s' % env.host_name)

	# Adding the ports 80 and 443 to the iptables
	run('sed "11i\-A INPUT -m state --state NEW -m tcp -p tcp --dport 80 -j ACCEPT" \
		%siptables > %stemp' % (env.iptables_dir, env.iptables_dir))
	run('mv -f %stemp %siptables' % (env.iptables_dir, env.iptables_dir))
	run('sed "12i\-A INPUT -m state --state NEW -m tcp -p tcp --dport 443 -j ACCEPT" \
		%siptables > %stemp' % (env.iptables_dir, env.iptables_dir))
	run('mv -f %stemp %siptables' % (env.iptables_dir, env.iptables_dir))
	run('service iptables restart')

	# Adding the corresponding ports to indico.conf
	sed('%sindico.conf' % env.indico_conf_dir, \
		'BaseURL              = \"http://localhost/indico\"', \
		'BaseURL              = \"http://%s:8000/indico\"' % env.host_name)
	sed('%sindico.conf' % env.indico_conf_dir, \
		'BaseSecureURL        = \"https://localhost/indico\"', \
		'BaseSecureURL        = \"https://%s:8443/indico\"' % env.host_name)
	sed('%sindico.conf' % env.indico_conf_dir, \
		'#   LoginURL             = \"\"', \
		'LoginURL             = \"https://%s:8443/indico/signIn.py\"' % env.host_name)

	# Modifying the ssl.conf file
	put('%sssl.conf' % env.config_dir, env.httpd_confd_dir)

# Deploy Indico into the VM
def deploy():
	dependencies_inst()
	indico_inst()
	config_indico()

# Start the database
def start_db():
	run('zdaemon -C %szdctl.conf start' % env.indico_conf_dir)

# Disable SELinux
def disable_sel():
	run('echo 0 >/selinux/enforce')

# Start Apache
def start_httpd():
	run('service httpd start')

# Start Indico
def start():
	start_db()
	disable_sel()
	start_httpd()

# Run the Virtual Machine
def run_vm():
	local('kvm -m 256 -redir tcp:2222::22 -redir tcp:8000::80 -redir tcp:8443::443 \
		  -net nic -net user, -drive file=%sSLC6.qcow2,if=virtio -drive file=%sinit.iso,if=virtio' %
		  (env.img_dir, env.img_dir))

# Configure Cloud-Init files
def config_cloud_init():
	print("Building virtual drive...")
	local('genisoimage -output %sinit.iso -volid cidata -joliet -rock %suser-data %smeta-data' %
		(env.img_dir, env.config_dir, env.config_dir))
	print("Virtual drive built!")

# Install and run Indico
def prepare_vm():
	config_cloud_init()
	run_vm()
	# something that makes the fabfile wait till the bootup is complete
	deploy()
	start()
