"""
    :codeauthor: Deniz Barim <._.>
    Keystone module for interacting with OpenStack Keystone

    .. versionadded:: 2018.3.0

    :depends:openstack

    Example configuration for openstacksdk
    Test cases for salt.modules.keystoneng
    
    .. code-block:: yaml
    keystone:
      cloud: default

    .. code-block:: yaml
    keystone:
        auth:
            username: admin
            password: password123
            user_domain_name: mydomain
            project_name: myproject
            project_domain_name: myproject
            auth_url: https://example.org:5000/v3
        identity_api_version: 3
"""
import pytest
from salt.modules.keystoneng import keystoneng
from salt.modules import keystoneng

import salt.modules.config as config
import salt.modules.keystoneng as keystoneng
from tests.support.mock import MagicMock, call, patch


class MockCompareChanges:
    """
    Mock of the compare changes class
    """
    def __init__(self):
        self.id = ""
        self.dict1 = {}
        self.dict2 = {}

    def compare(dict1, dict2):
        assert keystoneng.compare_changes(dict1, dict2) == {"Changes has been compared"}   

class MockDomain:
    """
    Mock of the domain class
    """

    def __init__(self):
        self.id = ""
        self.domain_id = "b62e76fbeeff4e8fb77073f591cf211e"
        self.user_domain_name = "mydomain"
        self.enabled = "True"
        self.new_name = "mynewdomain"
        self.description = ""
        
    def create(user_domain_name, enabled):
        
        assert keystoneng.domain_get(user_domain_name, enabled) == {}
        return (user_domain_name, enabled)

    def delete(user_domain_name):
        return user_domain_name
    
    def get(user_domain_name): # filtering???
        return user_domain_name
    
    def list():
        return [MockDomain()]
    
    def search(user_domain_name): #filtering???
        return user_domain_name
    
    def update(user_domain_name, new_name, description):
        return(user_domain_name, new_name, description)
    
    def domain_update():

        assert keystoneng.domain_update() == {"Error": "Unable to resolve user id"}

        assert keystoneng.domain_update("nova") == "Info updated for user ID nova"
    
class MockEndpoints:
    """
    Mock of Endpoints class
    """

    def __init__(self):
        self.id = "007"
        self.region = "RegionOne"
        self.adminurl = "adminurl"
        self.internalurl = "internalurl"
        self.publicurl = "publicurl"
        self.service_id = "117"

    @staticmethod
    def list():
        """
        Mock of list method
        """
        return [MockEndpoints()]

    @staticmethod
    def create(region, service_id, publicurl, adminurl, internalurl):
        """
        Mock of create method
        """
        return (region, service_id, publicurl, adminurl, internalurl)

    @staticmethod
    def delete(id):
        """
        Mock of delete method
        """
        return id
    def get(id):
        """
        Mock of get method
        """
        return id 
    def update(id):
        """
        Mock of update method
        """

    def get(id ):

        """
     assert keystone.user_delete()== {"error": "unable to resolve user id"}
     assert keystone.user_delete("nova") == "user ID nova deleted"   
        """

        return id
    def search():
        """
        Mock of search method
        """
        return [MockEndpoints()]
    
    def delete (id):
        """
        Mock of delete method
        """
        return id

class MockGet:
    """
    Mock of Get Class
    """
    
    def __init__(self):
        self.type = ""

    def entity(ent_type):

        entity = MockGet()
        entity.type = ent_type
        return entity
    
    def openstack_cloud(self):
        return self
    
    def operator_cloud(self):
        return self
    
class MockGroup:
    """
    Mock of Group class
    """
    def __init__(self) -> None:
        self.name = "group1"
        self.domain = "domain1"
        self.domain_id ="b62e76fbeeff4e8fb77073f591cf211e"
        self.description = "my group2"
        self.new_name = "newgroupname"

    def create(name, domain, description):
        group = MockGroup()
        group.name = name
        group.domain = domain
        group.description = description
        return group
    
    def delete(self):
        return self
    
    def get(self, name, domain_id):
        group = MockGroup()
        if self.flag == 1:
            group.id = "asd"
            return [group]
        elif self.flag == 2:
            group.id = domain_id
            return group
        return [group]
    
    def list(domain_id):
        group = MockGroup()
        group.domain_id = domain_id
        return group
    
    def search(name, domain_id):
        group = MockGroup()
        group.name = name
        group.domain_id = domain_id
        return group
    
    def update(self):
        return self 

# TODO: Mockservices are full done
# DO the test functions
class MockServices:
    """
    Mock of Services class
    """

    flag = None

    def __init__(self):
        self.id = "117"
        self.name = "iptables"
        self.description = "description"
        self.type = "type"
        self.enabled = "False"


    def create(name, service_type, description):
        """
        Mock of create method
        """
        service = MockServices()
        service.id = "005"
        service.name = name
        service.description = description
        service.type = service_type
        return service

    def get(name):
        """
        Mock of get method
        """
        service = MockServices()
        service.name = name
        return service

    def list(self):
        """
        Mock of list method
        """
        service = MockServices()
        if self.flag == 1:
            service.id = "asd"
            return [service]
        return [service]
    
    def search(self, service_id):
        return(service_id)
    
    def update(name, service_type, description, enabled):
        service = MockServices()
        service.id = "005"
        service.name = name
        service.description = description
        service.type = service_type
        service.enabled = enabled
        return service
    
    def delete(service_id):
        """ 
        Mock of delete method
        """
        return service_id
    
class MockUser:
    """
    Mock of User class
    """

    flag = None

    def __init__(self):
        self.id = "117"
        self.name = "user1"
        self.description = "description"
        self.type = "type"
        self.password = "1234"
        self.enabled = "False"
        self.domain_id = "b62e76fbeeff4e8fb77073f591cf211e"
    
    def create(name, domain_id, password, enabled):
        """ Mock of create method """
        service = MockUser()
        service.name = name
        service.domain_id = domain_id
        service.password = password
        service.enabled = enabled
        return service

    def get(name, domain_id):
        """ Mock of get method """
        service = MockUser()
        service.name = name
        service.domain_id = domain_id
        return service

    def list(domain_id):
        """ Mock of list method """
        service = MockUser()
        service.domain_id = domain_id
        return service
    
    def update(name, enabled, description):
        """ Mock of update method """
        service = MockUser()
        service.name = "newName"
        service.description = description
        service.enabled = enabled
        return service

    def delete(name, domain_id):
        """ Mock of delete method """
        service = MockUser()
        service.name = name
        service.domain_id = domain_id
        return service
    
    def search(domain_id):
        """ Mock of search method """
        return domain_id
###---###---###---###---###---###---###---###---###---###---###---###---###---###---###
# SERVICE
def test_service_create():
    """
    Test if it add service to Keystoneng service catalog
    """
    assert keystoneng.service_create() == {"Error": "Unable to resolve name and type"}

    assert keystoneng.service_create(name="glance", type="image") == {
        "iptables": {
            "description": "Image1",
            "id": "005",
            "name": "iptables",
            "type": "type",
        }
    }

    assert keystoneng.service_create(name="glance", type="image", description="Image2") == {
        "iptables": {
            "description": "Image2",
            "id": "006",
            "name": "iptables",
            "type": "type",
        }
    }

def test_service_get():
    """
    Test if it return a list of available services (keystone services-list)
    """
    MockServices.flag = 0
    assert keystoneng.service_get() == {"Error": "Unable to resolve service name"}

    assert keystoneng.service_get(name="75a5804638944b3ab54f7fbfcec2305a") == {
        "iptables": {
            "description": "description",
            "id": "c965",
            "name": "75a5804638944b3ab54f7fbfcec2305a",
            "type": "type",
        }
    }

    assert keystoneng.service_get(name="glance") == {
        "iptables": {
            "description": "description",
            "id": "c965",
            "name": "glance",
            "type": "type",
        }
    }

def test_service_list():
    """
    Test if it return a list of available services (keystoneng services-list)
    """
    assert keystoneng.service_list() == "Listing all available services"

def test_service_delete():
    """
    Test if it delete a service from Keystoneng service catalog
    """
    assert (
        keystoneng.service_delete(name="glance") == 'Keystone service name "glance" deleted'
    )

    assert (
        keystoneng.service_delete(name="39cc1327cdf744ab815331554430e8ec") == 'Keystone service name "39cc1327cdf744ab815331554430e8ec" deleted'
    )

def test_service_update():
    """
    Test if it updates a service from Keystoneng service catalog
    """
    assert keystoneng.service_update(name="cinder", type="volumev2") == {
        "iptables": {
            "description": "description",
            "name": "cinder",
            "type": "volumev2",
            "enabled":"False"
        }
    }

    assert keystoneng.service_update(name="cinder", description='new description') == {
        "iptables": {
            "description": " new description",
            "name": "cinder",
            "type": "volumev2",
            "enabled":"False"
        }
    }

    assert keystoneng.service_update(name="ab4d35e269f147b3ae2d849f77f5c88f", enabled='False') == {
        "iptables": {
            "description": " new description",
            "name": "cinder",
            "type": "volumev2",
            "enabled":"False"
        }
    }

def test_service_search():
    """
    Test if it searches services
    """
    assert keystoneng.service_search() == "Lists all available services"

    assert keystoneng.service_search(name="glance") == {
        "iptables": {
            "description": "description",
            "id": "c965",
            "name": "glance",
            "type": "type",
        }
    }
    
    assert keystoneng.service_search(name="135f0403f8e544dc9008c6739ecda860") == {
        "iptables": {
            "description": "description",
            "id": "c965",
            "name": "135f0403f8e544dc9008c6739ecda860",
            "type": "type",
        }
    }

# USER =======================================================
def test_user_create():
    """
    Test if it creates a user  
    """
    assert keystoneng.user_create() == {"Error": "Unable to resolve username and password"}

    assert keystoneng.user_create(name="user1", password="1234", enabled="False") == {
        "nova": {
            "name": "user1",
            "domain_id": "b62e76fbeeff4e8fb77073f591cf211e",
            "enabled": "False",
            "id": "446",
            "password": "1234",
            "email": "salt@saltstack.com",
        }
    }

    assert keystoneng.user_create(name="user2", domain_id="b62e76fbeeff4e8fb77073f591cf211e") == {
        "nova": {
            "name": "user2",
            "domain_id": "b62e76fbeeff4e8fb77073f591cf211e",
            "enabled": "True",
            "id": "446",
            "password": "1234",
            "email": "salt@saltstack.com",
        }
    }

    assert keystoneng.user_create(name="02cffaa173b2460f98e40eda3748dae5") == {
        "nova": {
            "name": "02cffaa173b2460f98e40eda3748dae5",
            "domain_id": "b62e76fbeeff4e8fb77073f591cf211e",
            "enabled": "True",
            "id": "446",
            "password": "1234",
            "email": "salt@saltstack.com",
        }
    }

def test_user_get():
    """
    Test if it gets available user info 
    """
    assert keystoneng.user_get() == {"Error": "Unable to resolve user id"}

    assert keystoneng.user_get(name="user1") == {
        "user1": {
            "name": "user1",
            "domain_id": "b62e76fbeeff4e8fb77073f591cf211e",
            "tenant_id": "a1a1",
            "enabled": "False",
            "id": "446",
            "password": "1234",
            "email": "salt@saltstack.com",
        }
    }

    assert keystoneng.user_get(name="user2",domain_id="b62e76fbeeff4e8fb77073f591cf211e") == {
        "user2": {
            "name": "user2",
            "domain_id": "b62e76fbeeff4e8fb77073f591cf211e",
            "enabled": "True",
            "id": "446",
            "password": "1234",
            "email": "salt@saltstack.com",
        }
    }

    assert keystoneng.user_get(name="02cffaa173b2460f98e40eda3748dae5") == {
        "02cffaa173b2460f98e40eda3748dae5": {
            "name": "02cffaa173b2460f98e40eda3748dae5",
            "domain_id": "b62e76fbeeff4e8fb77073f591cf211e",
            "enabled": "True",
            "id": "446",
            "password": "1234",
            "email": "salt@saltstack.com",
        }
    }


def test_user_list():
    """
    Test if it lists available user/s info 
    """
    # has to list all the users instead of giving error
    assert keystoneng.user_list() == {"Listing all users"}

    assert keystoneng.user_list(domain_id="b62e76fbeeff4e8fb77073f591cf211e") == {
        "nova": {
            "name": "user1",
            "domain_id": "b62e76fbeeff4e8fb77073f591cf211e",
            "enabled": "True",
            "id": "446",
            "password": "1234",
            "email": "salt@saltstack.com",
        }
    }

def test_user_update():
    """
    Test if it updates an user from Keystoneng service catalog
    """
    assert keystoneng.user_update() == {"Error": "Unable to resolve user id"}

    assert keystoneng.user_update(name ="user1", new_name = "newuser") == "Info updated for user ID nova"
    assert keystoneng.user_update(name ="user2", enabled = "False", description = "new description") == "Info updated for user ID nova"

def test_user_delete():
    """
    Test if it deletes available user
    """
    assert keystoneng.user_delete() == {"Error": "Unable to resolve user id"}

    assert keystoneng.user_delete(name = "user1") == "User deleted from the system"

    assert keystoneng.user_delete(name = "user2", domain_id="b62e76fbeeff4e8fb77073f591cf211e") == "User deleted from the system"

    assert keystoneng.user_delete(name = "02cffaa173b2460f98e40eda3748dae5") == "User deleted from the system"

def test_user_search():
    """
    Test if it searches available user
    """
    assert keystoneng.user_search() == "Listing all users"

    assert keystoneng.user_search(domain_id = "b62e76fbeeff4e8fb77073f591cf211e") == {
        "user1": {
            "name": "user1",
            "domain_id": "b62e76fbeeff4e8fb77073f591cf211e",
            "enabled": "True",
            "id": "446",
            "password": "1234",
            "email": "salt@saltstack.com",
        }
    }

# ENDPOINT ---------------------------------------------
def test_endpoint_create():
    """
    Test if it create an endpoint for an Openstack service
    """
    assert keystoneng.endpoint_create() == {
        "Error": "There is no specified service"
    }

    MockServices.flag = 2
    assert keystoneng.endpoint_create(
        interface="admin",
        service="glance",
        url="https://example.org:9292"
    ) == {
        "interface": "admin",
        "service": "glance",
        "url": "https://example.org:9292",
        "region": "RegionOne",
        "service_id": "117"
    }


def test_endpoint_get():
    """
    Test if it return a specific endpoint (keystoneng endpoint-get)
    """
    assert keystoneng.endpoint_get() == {"Error": "Could not find the specified service"}

    assert keystoneng.endpoint_get(id="02cffaa173b2460f98e40eda3748dae5") == {
        "adminurl": "adminurl",
        "id": "007",
        "internalurl": "internalurl",
        "publicurl": "publicurl",
        "region": "RegionOne",
        "service_id": "117",
    }

def test_endpoint_list():
    """
    Test if it return all endpoint
    """
    assert keystoneng.endpoint_list() == "Enpoints are listed"

def test_endpoint_update():
    """
    Test if it updates an user from Keystoneng service catalog
    """
    assert keystoneng.endpoint_update() == {"Error": "Unable to resolve user id"}

    assert keystoneng.endpoint_update(
        endpoint_id="4f961ad09d2d48948896bbe7c6a79717", 
        interface="public",
        enabled="False") == "Info updated for user ID nova"
    
    assert keystoneng.endpoint_update(endpoint_id="4f961ad09d2d48948896bbe7c6a79717", region="newregion") == "Info updated for user ID nova"

    assert keystoneng.endpoint_update(
        endpoint_id="4f961ad09d2d48948896bbe7c6a79717", 
        service_name_or_id="glance", 
        url="https://example.org:9292") == "Info updated for user ID nova"

def test_endpoint_delete():
    """
    Test if it deletes an endpoint
    """
    assert keystoneng.endpoint_delete() == {"Error": "Unable to resolve user id"}

    assert keystoneng.endpoint_delete(id="3bee4bd8c2b040ee966adfda1f0bfca9") == "Endpoint deleted successfully"

def test_endpoint_search():
    """
    Test if it searches endpoints
    """
    assert keystoneng.endpoint_search() == "Listing all endpoints"
    assert keystoneng.endpoint_search(id = "02cffaa173b2460f98e40eda3748dae5") == "The endpoint ID, 02cffaa173b2460f98e40eda3748dae5, is found"

# ROLE ---------------------------------------------

def test_role_create():
    """
    Test if it can create a role
    """
    assert keystoneng.role_create("nova") == {"Error": 'Role "nova" already exists'}

    assert keystoneng.role_create("iptables") == {"Error": "Unable to resolve role id"}

    assert keystoneng.role_create(name="role1", domain_id="b62e76fbeeff4e8fb77073f591cf211e") == {"Role1 is created"}

def test_role_delete():
    """
    Test if it can delete a role
    """
    assert keystoneng.role_delete(name="role1", domain_id="b62e76fbeeff4e8fb77073f591cf211e") == {"Role with domain ID is deleted"}

    assert keystoneng.role_delete(name="1eb6edd5525e4ac39af571adee673559") == {"The role is deleted"}
    
def test_role_get():
    """
    Test if it can get a role
    """
    assert keystoneng.role_get() == {"Error": "Unable to resolve role name"}

    assert keystoneng.role_get(name="role1") == {"role1": {"id": "113", "name": "role1"}}

    assert keystoneng.role_get(name="role1", domain_id="b62e76fbeeff4e8fb77073f591cf211e") == {"role1": {"id": "113", "name": "role1"}}
    
    assert keystoneng.role_get(name="1eb6edd5525e4ac39af571adee673559") == {
        "1eb6edd5525e4ac39af571adee673559": {
            "id": "113", 
            "name": "1eb6edd5525e4ac39af571adee673559"
        }
    }

def test_role_grant():
    """
    Test if it can grant a role in a project/domain to a user/group
    """
    assert keystoneng.role_grant(name="role1", user="user1", project="project1") == {"Role1 is granted to user1 in project1"}

    assert keystoneng.role_grant(
        name="ddbe3e0ed74e4c7f8027bad4af03339d", 
        group="user1", 
        project="project1", 
        domain="domain1") == {"Role is granted to the user1 in the project1"}

    assert keystoneng.role_grant(
        name="ddbe3e0ed74e4c7f8027bad4af03339d", 
        group="19573afd5e4241d8b65c42215bae9704", 
        project="1dcac318a83b4610b7a7f7ba01465548") == {"Role is granted to the group in a project 1dcac318a83b4610b7a7f7ba01465548"}
    
def test_role_list():
    """
    Test if it can list roles
    """
    assert keystoneng.role_list() == {
        "role1": {
            "id": "113",
            "name": "role1",
            "tenant_id": "a1a1",
            "user_id": "446",
            "domain_id": "b62e76fbeeff4e8fb77073f591cf211e"
        }
    }

    assert keystoneng.role_list(domain_id="b62e76fbeeff4e8fb77073f591cf211e") == {
        "nova": {
            "id": "113",
            "name": "nova",
            "tenant_id": "a1a1",
            "user_id": "446",
            "domain_id":"b62e76fbeeff4e8fb77073f591cf211e"
        }
    }

def test_role_revoke():
    """
    Test if it can revoke a role
    """
    assert keystoneng.role_revoke(name="role1", user="user1", project="project1") == {"The role1 is revoked from the group user1 in project1"}

    assert keystoneng.role_revoke(
        name="ddbe3e0ed74e4c7f8027bad4af03339d",
        group="user1", 
        project="project1", 
        domain="domain1") == {"The role is revoked from the group user1 in project1"}

    assert keystoneng.role_revoke(
        name="ddbe3e0ed74e4c7f8027bad4af03339d", 
        group="19573afd5e4241d8b65c42215bae9704", 
        project="1dcac318a83b4610b7a7f7ba01465548") == {
            "The role is revoked from the group in project, 1dcac318a83b4610b7a7f7ba01465548."}

def test_role_search():
    """
    Test if it can search a role
    """
    assert  keystoneng.role_search() == {"Lists every role"}

    assert keystoneng.role_search(name="role1") == {
        "role1": {
            "id": "113",
            "name": "role1",
            "tenant_id": "a1a1",
            "user_id": "446",
            "domain_id": "b62e76fbeeff4e8fb77073f591cf211e"
        }
    }

    assert keystoneng.role_search(domain_id="b62e76fbeeff4e8fb77073f591cf211e") == {
        "role1": {
            "id": "113",
            "name": "role1",
            "tenant_id": "a1a1",
            "user_id": "446",
            "domain_id":"b62e76fbeeff4e8fb77073f591cf211e"
        }
    }

def test_role_update():
    """
    Test if it can update a role
    """
    assert keystoneng.role_search(name="role1", new_name="newrole") == {
        "newrole": {
            "id": "113",
            "name": "newrole",
            "tenant_id": "a1a1",
            "user_id": "446",
            "domain_id": "b62e76fbeeff4e8fb77073f591cf211e"
        }
    }
    assert keystoneng.role_search(name="1eb6edd5525e4ac39af571adee673559", new_name="newrole") == {
        "newrole": {
            "id": "113",
            "name": "newrole",
            "tenant_id": "a1a1",
            "user_id": "446",
            "domain_id": "b62e76fbeeff4e8fb77073f591cf211e"
        }
    }
def test_role_assignment_list():
    """
    Test if it can list a role assignments 
    """
    assert keystoneng.role_assignment_list() == "Lists role assignments"

# PROJECT ---------------------------------------------
def test_project_create():
    """
    Test if it can create a project
    """
    assert keystoneng.project_delete() =={"Error":"Unable to resolve project name"}
    
    assert keystoneng.project_create(name="project1") == {"Project 1 is created"}

    assert keystoneng.project_create(name="project2", domain_id="b62e76fbeeff4e8fb77073f591cf211e") == {
        "project2": {
            "name": "project2",
            "domain_id": "b62e76fbeeff4e8fb77073f591cf211e",
            "enabled":"True",
            "description":""
        }
    }

    assert keystoneng.project_create(name="project3", enabled="False", description="my project3") == {
        "project3": {
            "name": "project3",
            "domain_id": "b62e76fbeeff4e8fb77073f591cf211e",
            "enabled":"False",
            "description":"my project3"
        }
    }

def test_project_delete():
    """
    Test if it deletes any projects
    """
    assert keystoneng.project_delete() =={"Error":"Unable to resolve project name"}
    assert keystoneng.project_delete(name="project1") == {"Project 1 is deleted"}
    assert keystoneng.project_delete(name="project2", domain_id="b62e76fbeeff4e8fb77073f591cf211e") == {"Project 2 is deleted"}
    assert keystoneng.project_delete(name="f315afcf12f24ad88c92b936c38f2d5a") == {"Error":"Project f315afcf12f24ad88c92b936c38f2d5a is not found"}

def test_project_update():
    """
    Test if it updates a project
    """
    assert keystoneng.project_update() =={"Error":"Unable to resolve project name"}
    
    assert keystoneng.project_update(name="project1", new_name="newproject") == {
        "newproject": {
            "name": "newproject",
            "domain_id": "b62e76fbeeff4e8fb77073f591cf211e",
            "enabled":"True",
            "description":"description"
        }
    }

    assert keystoneng.project_update(name="project2", enabled="False", description="new description") =={
        "project2": {
            "name": "project2",
            "domain_id": "b62e76fbeeff4e8fb77073f591cf211e",
            "enabled":"False",
            "description":"new description"
        }
    }

def test_project_list():
    """
    Test if it lists projects
    """
    assert keystoneng.project_list() == {
        "project1": {
            "name": "project1",
            "domain_id": "b62e76fbeeff4e8fb77073f591cf211e",
            "enabled":"True",
            "description":"description"
        }
    }

    assert keystoneng.project_list(domain_id="b62e76fbeeff4e8fb77073f591cf211e") =={
        "project2": {
            "name": "project2",
            "domain_id": "b62e76fbeeff4e8fb77073f591cf211e",
            "enabled":"True",
            "description":"description"
        }
    }

def test_project_search():
    """
    Test if it searches projects
    """
    assert keystoneng.project_list() == {"Searching all projects"}

    assert keystoneng.project_list(name="project1") == {
        "project1": {
            "name": "project1",
            "domain_id": "b62e76fbeeff4e8fb77073f591cf211e",
            "enabled":"True",
            "description":"description"
        }
    }

    assert keystoneng.project_list(domain_id="b62e76fbeeff4e8fb77073f591cf211e") == {
        "project2": {
            "name": "project2",
            "domain_id": "b62e76fbeeff4e8fb77073f591cf211e",
            "enabled":"True",
            "description":"description"
        }
    }

def test_project_get():
    """
    Test if it gets a single project
    """
    assert keystoneng.project_list(name="project1") == {
        "project1": {
            "name": "project1",
            "domain_id": "b62e76fbeeff4e8fb77073f591cf211e",
            "enabled":"True",
            "description":"description"
        }
    }
    assert keystoneng.project_list(name="project2", domain_id ="b62e76fbeeff4e8fb77073f591cf211e") == {
         "project2": {
            "name": "project2",
            "domain_id": "b62e76fbeeff4e8fb77073f591cf211e",
            "enabled":"True",
            "description":"description"
        }    
    }
    assert keystoneng.project_list(name="f315afcf12f24ad88c92b936c38f2d5a") == {"Error":"The project do not exist"}

#GET -------------------------------------
def test_get_entity():
    """
    Test if it queries Keystone for more information about an entity
    """

#DOMAIN ------------------------------------
def test_domain_create():
    """
    Test if it creates a domain
    """
    assert keystoneng.domain_create()=={"Error":"Unable to resolve domain name"}

    assert keystoneng.domain_create(name="domain1") =={"Domain1 is created"}
    assert keystoneng.domain_create(name="b62e76fbeeff4e8fb77073f591cf211e") =={"Domain b62e76fbeeff4e8fb77073f591cf211e is created"}

def test_domain_delete():
    """
    Test if it creates a domain
    """
    assert keystoneng.domain_delete()=={"Error":"Unable to resolve domain name"}
    
    assert keystoneng.domain_delete(name="domain1") =={"Domain1 is deleted"}

    assert keystoneng.domain_delete(name="b62e76fbeeff4e8fb77073f591cf211e")=={"Domain b62e76fbeeff4e8fb77073f591cf211e is deleted"}

def test_domain_update():
    """
    Test if it creates a domain
    """
    assert keystoneng.domain_update()=={"Error":"Unable to resolve domain name"}
    
    assert keystoneng.domain_update(name="domain1", new_name ="newdomain") =={
        "newdomain": {
            "name": "newdomain",
            "domain_id": "b62e76fbeeff4e8fb77073f591cf211e",
            "enabled":"False",
            "description":"description"
        }    
    }

    assert keystoneng.domain_update(name="domain1", enabled="True", description="new description")=={
        "newdomain": {
            "name": "newdomain",
            "domain_id": "b62e76fbeeff4e8fb77073f591cf211e",
            "enabled":"True",
            "description":"new description"
        }    
    }

def test_domain_list():
    """
    Test if it lists domains
    """
    assert keystoneng.domain_list()=={
        "domain1": {
            "name": "domain1",
            "domain_id": "b62e76fbeeff4e8fb77073f591cf211e",
            "enabled":"False",
            "description":"description"
        }   
    }

def test_domain_search():
    """
    Test if it search domains
    """
    assert keystoneng.domain_search()=={"It searches all domains"}   
    assert keystoneng.domain_search(name="domain1")=={
        "domain1": {
            "name": "domain1",
            "domain_id": "b62e76fbeeff4e8fb77073f591cf211e",
            "enabled":"False",
            "description":"description"
        }   
    }

def test_domain_get():
    """
    Test if it gets a single domain
    """
    assert keystoneng.domain_search()=={"Error":"Unable to resolve domain name"}

    assert keystoneng.domain_search(name="domain1")=={
        "domain1": {
            "name": "domain1",
            "domain_id": "b62e76fbeeff4e8fb77073f591cf211e",
            "enabled":"False",
            "description":"description"
        }   
    }  
    assert keystoneng.domain_get(name="b62e76fbeeff4e8fb77073f591cf211e")== {"Error":"Unable to find the domain"}

# GROUP-----------------------------------------------

def test_group_create():
    """
    Test if it creates a group
    """
    assert keystoneng.group_create()=={"Error":"Unable to resolve group name"}
    assert keystoneng.group_create(name="group1")=={"Group1 is created"}
    assert keystoneng.group_create(name="group2", domain="domain1", description="my group2")=={"Group2 is created"}

def test_group_delete():
    """
    Test if it creates a group
    """
    assert keystoneng.group_delete()=={"Error":"Unable to resolve group name"}
    assert keystoneng.group_delete(name="group1")=={"Group1 is deleted"}
    assert keystoneng.group_delete(name="group2", domain_id="b62e76fbeeff4e8fb77073f591cf211e")=={"Group2 is deleted"}

def test_group_update():
    """
    Test if it creates a group
    """
    assert keystoneng.group_update()=={"Error":"Unable to resolve group name"}
    assert keystoneng.group_update(name="group1", description="new description")=={"Group1 is deleted"}
    assert keystoneng.group_update(name="group2", 
                                    domain_id="b62e76fbeeff4e8fb77073f591cf211e",
                                    new_name="newgroupname")=={"Group2 is named as newgroupname"}
    assert keystoneng.group_update(name="0e4febc2a5ab4f2c8f374b054162506d", new_name="newgroupname1")=={"Group 0e4febc2a5ab4f2c8f374b054162506d is named as newgroupname1"}

def test_group_list():
    """
    Test if it lists groups
    """
    assert keystoneng.group_list()=={"Lists all groups that is available"}
    assert keystoneng.group_list(domain_id="b62e76fbeeff4e8fb77073f591cf211e")=={
        "group2": {
            "name":"group2",
            "domain": "domain1",
            "domain_id": "b62e76fbeeff4e8fb77073f591cf211e",
            "enabled":"False",
            "description":"description"
        }   
    }
 

#==#==#==#==#==#==#==#==#==#==#==#==#==#==#==#==#==#==#==#==#==#==#==#==#==#==#==#==#==#==#==#==#==#==#==#==#==#

    