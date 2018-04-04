# nsxt-ansible
Repository for NSX-T Ansible Modules

Forked from github.com/yasensim/nsxt-ansible

# Setup
apt-get -y update
apt-get -y install python-pip openssl libxml2 libxml2-dev libxslt1-dev libssl-dev libffi-dev python-dev build-essential

pip install --upgrade pip wheel setuptools
pip install --upgrade lxml enum cffi
pip install --upgrade cryptography pyopenssl enum34

pip install nsx_python_sdk-2.1.0.0.0.7319425-py2.py3-none-any.whl
pip install vapi_runtime-2.7.0-py2.py3-none-any.whl
pip install vapi_common-2.7.0-py2.py3-none-any.whl
pip install vapi_common_client-2.7.0-py2.py3-none-any.whl
