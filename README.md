# nsxt-ansible
Repository for NSX-T Ansible Modules
It is for Internal PoC and is not VMware suppoted!!!

For usage with NSX-T 2.1 please clone the v2.1 branch.
```
git clone -b v2.1 https://github.com/yasensim/nsxt-ansible.git
```

There might be changed in the master branch!


## Getting started

I assume you already have ansible installed. Connecting VMs to NSX-T Logical Switches is supported from Ansible 2.6. Anyway, using the modules in this repo is also possible with eralier versions.
https://github.com/ansible/ansible/pull/37979

Download nsxt python sdk and vapi from here https://my.vmware.com/web/vmware/details?downloadGroup=NSX-T-210-SDK-PYTHON&productId=673

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
git clone -b v2.1 https://github.com/yasensim/nsxt-ansible.git
```
