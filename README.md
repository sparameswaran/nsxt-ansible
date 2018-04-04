# nsxt-ansible
Repository for NSX-T Ansible Modules

Forked from github.com/yasensim/nsxt-ansible

It is for Internal PoC. This is not VMware suppoted and might disappear at some point of time.
Use at your own risk!

Forked from github.com/yasensim/nsxt-ansible

## Getting started

I assume you already have ansible installed. Connecting VMs to NSX-T Logical Switches is supported from Ansible 2.6. Anyway, using the modules in this repo is also possible with eralier versions.
https://github.com/ansible/ansible/pull/37979

Download nsxt python sdk and vapi from here https://my.vmware.com/web/vmware/details?downloadGroup=NSX-T-210-SDK-PYTHON&productId=673

# nsxt python lib pre-reqs

You should have the following files locally:
```
nsx_python_sdk-2.1.0.0.0.7319425-py2.py3-none-any.whl
vapi_common-2.7.0-py2.py3-none-any.whl
vapi_common_client-2.7.0-py2.py3-none-any.whl
vapi_runtime-2.7.0-py2.py3-none-any.whl
```

Install the dependancies and the required packages.


```
apt-get -y update
apt-get -y install python-pip openssl libxml2 libxml2-dev libxslt1-dev libssl-dev libffi-dev python-dev build-essential

pip install --upgrade pip wheel setuptools 
pip install --upgrade lxml enum cffi
pip install --upgrade cryptography pyopenssl enum34

pip install nsx_python_sdk-2.1.0.0.0.7319425-py2.py3-none-any.whl
pip install vapi_runtime-2.7.0-py2.py3-none-any.whl 
pip install vapi_common-2.7.0-py2.py3-none-any.whl
pip install vapi_common_client-2.7.0-py2.py3-none-any.whl
```

```
git clone https://github.com/sparameswaran/nsxt-ansible.git
```
