import logging
log = logging.getLogger(__name__)
# TODO:
# - When state needs a change a lot of round trips to netbox are made to
#   resolved names to id's. It would be a lot better to resolve once
#   and pass the ID's to execution module. fix this in the execution module.
def manufacturer(name):
    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    result = __salt__["netbox.get"](
        "dcim",
        "manufacturers",
        name=name
    )

    if result:
        ret["result"] = True
        ret["comment"] = "{0} is already present.".format(name)
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "Manufacturer {0} would be created in NetBox.".format(name)
        return ret

    result = __salt__["netbox.create_manufacturer"](name=name)
    if not result:
        ret["result"] = False
        ret["comment"] = "{0} could not be created.".format(name)
        ret["changes"] = {'netbox': 'should return stuff :/'}

    result = __salt__['netbox.get'](
        "dcim",
        "manufacturers",
        name=name
    )

    if result:
        ret["result"] = True
        ret["comment"] = "Manufacturer {0} is created in NetBox.".format(name)
        ret["changes"] = result

    return ret

def virtual_machine(
    name,
    cluster,
    status=None,
    role=None,
    tenant=None,
    platform=None,
    vcpus=None,
    memory=None,
    disk=None,
    comments=None):

    # 1. Set up the return dictionary and perform any necessary input validation (type checking, looking for use of mutually-exclusive arguments, etc.).
    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    # 2. Check if changes need to be made. 
    # This is best done with an information-gathering function in an accompanying execution module. 
    # The state should be able to use the return from this function to tell whether or not 
    # the minion is already in the desired state.
    changes = __salt__["netbox.check_virtual_machine"](
        name, 
        cluster,
        status=status,
        role=role,
        tenant=tenant,
        platform=platform,
        vcpus=vcpus,
        memory=memory,
        disk=disk,
        comments=comments
    )
    if changes == False:
        ret["result"] = False
        ret["comment"] = "Something went wrong inside netbox.check_virtual_machine"
        return ret
  
    # False: there was an error
    # None: No such virtual machine -> create
    # {} : No changes needed
    # {<data>} : apply changes

    # 3. If step 2 found that the minion is already in the desired state, 
    #    then exit immediately with a True result and without making any changes.

    if changes == {}:
        ret["result"] = True
        ret["comment"] = "{0} already in desired state".format(name)
        return ret

    # 4. If step 2 found that changes do need to be made, 
    # then check to see if the state was being run in test mode (i.e. with test=True). 
    # If so, then exit with a None result, a relevant comment, 
    # and (if possible) a changes entry describing what changes would be made.

    if __opts__["test"] and changes:
        ret["result"] = None
        ret["comment"] = "Attributes are set to be changed on {}".format(name)
        ret["changes"] = changes
        return ret
    if __opts__["test"] and not changes:
        ret["result"] = None
        ret["comment"] = "Virtual machine {} is set to be created.".format(name)
        ret["changes"] = {}
        return ret


    # 5. Make the desired changes. 
    # This should again be done using a function from an accompanying execution module. 
    # If the result of that function is enough to tell you whether or not an error occurred, 
    # then you can exit with a False result and a relevant comment to explain what happened.

    if changes == None:
        result = __salt__["netbox.create_virtual_machine"](
            name,
            cluster,
            status=status,
            role=role,
            tenant=tenant,
            platform=platform,
            vcpus=vcpus,
            memory=memory,
            disk=disk,
            comments=comments
        )

    if changes:
        result = __salt__["netbox.update_virtual_machine"](
            name,
            cluster,
            **changes
        )

    # 6. Perform the same check from step 2 again to confirm whether or not 
    # the minion is in the desired state. 
    # Just as in step 2, this function should be able to tell you by its 
    # return data whether or not changes need to be made.
    requested_changes = changes
    changes = __salt__["netbox.check_virtual_machine"](
        name, 
        cluster,
        status=status,
        role=role,
        tenant=tenant,
        platform=platform,
        vcpus=vcpus,
        memory=memory,
        disk=disk,
        comments=comments
    )

    # 7. Set the return data and return!
    if changes:
        ret["comment"] = "Failed to reconcile attributes {}".format(changes)
    else:
        ret["result"] = True
        ret["comment"] = "{} reconciled successfully".format(name)
        if requested_changes:
            ret["changes"] = requested_changes

    
    return ret

def vminterface(
    name,
    virtual_machine,
    cluster,
    enabled=True,
    parent=None,
    mtu=None,
    mac_address=None,
    mode=None,
    untagged_vlan=None,
    tagged_vlans=None,
    description=None
    ):

    # 1. Set up the return dictionary and perform any necessary input validation (type checking, looking for use of mutually-exclusive arguments, etc.).
    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    # 2. Check if changes need to be made. 
    # This is best done with an information-gathering function in an accompanying execution module. 
    # The state should be able to use the return from this function to tell whether or not 
    # the minion is already in the desired state.
    required_changes = __salt__["netbox.check_vminterface"](
        name,
        virtual_machine,
        cluster,
        enabled=enabled,
        parent=parent,
        mtu=mtu,
        mac_address=mac_address,
        mode=mode,
        untagged_vlan=untagged_vlan,
        tagged_vlans=tagged_vlans,
        description=description
    )
    if required_changes == False:
        ret["result"] = False
        ret["comment"] = "Something went wrong inside netbox.check_virtual_machine"
        return ret
  
    # False: there was an error
    # None: No such virtual machine -> create
    # {} : No changes needed
    # {<data>} : apply changes

    # 3. If step 2 found that the minion is already in the desired state, 
    #    then exit immediately with a True result and without making any changes.

    if required_changes == {}:
        ret["result"] = True
        ret["comment"] = "{0} already in desired state".format(name)
        return ret

    # 4. If step 2 found that changes do need to be made, 
    # then check to see if the state was being run in test mode (i.e. with test=True). 
    # If so, then exit with a None result, a relevant comment, 
    # and (if possible) a changes entry describing what changes would be made.

    #TODO: The difference between changes({}) and new(None) should be handled
    #      more elegant...
    if __opts__["test"] and required_changes:
        ret["result"] = None
        ret["comment"] = "Attributes are set to be changed on {}".format(name)
        ret["changes"] = required_changes
        return ret
    if __opts__["test"] and not required_changes:
        ret["result"] = None
        ret["comment"] = "VMInterface {} would be created".format(name)
        ret["changes"] = {}
        return ret


    # 5. Make the desired changes. 
    # This should again be done using a function from an accompanying execution module. 
    # If the result of that function is enough to tell you whether or not an error occurred, 
    # then you can exit with a False result and a relevant comment to explain what happened.

    if required_changes == None:
        result = __salt__["netbox.create_vminterface"](
            name,
            virtual_machine,
            cluster,
            enabled=enabled,
            parent=parent,
            mtu=mtu,
            mac_address=mac_address,
            mode=mode,
            untagged_vlan=untagged_vlan,
            tagged_vlans=tagged_vlans,
            description=description
        )

    if required_changes:
        result = __salt__["netbox.update_vminterface"](
            name,
            virtual_machine,
            cluster,
            **required_changes
        )

    # 6. Perform the same check from step 2 again to confirm whether or not 
    # the minion is in the desired state. 
    # Just as in step 2, this function should be able to tell you by its 
    # return data whether or not changes need to be made.
    outstanding_changes = __salt__["netbox.check_vminterface"](
        name,
        virtual_machine,
        cluster,
        enabled=enabled,
        parent=parent,
        mtu=mtu,
        mac_address=mac_address,
        mode=mode,
        untagged_vlan=untagged_vlan,
        tagged_vlans=tagged_vlans,
        description=description
    )

    # 7. Set the return data and return!
    if outstanding_changes:
        # update failed, after create/update there are still required changes
        ret["comment"] = "Failed to reconcile attributes {}".format(outstanding_changes)
    elif required_changes:
        # update succesfully
        ret["result"] = True
        ret["comment"] = "{} reconciled successfully".format(name)
        ret["changes"] = required_changes
    else:
        # created succesfully
        ret["result"] = True
        ret["comment"] = "{} created successfully".format(name)
        ret["changes"] = result
    return ret


def ip_address(
    address,
    name=None,
    interface=None,
    virtual_machine=None,
    cluster=None,
    device=None,
    vrf=None,
    tenant=None,
    status=None,
    role=None,
    nat_inside=None,
    dns_name=None,
    description=None
    ):

    # 1. Set up the return dictionary and perform any necessary input validation (type checking, looking for use of mutually-exclusive arguments, etc.).
    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    # 2. Check if changes need to be made. 
    # This is best done with an information-gathering function in an accompanying execution module. 
    # The state should be able to use the return from this function to tell whether or not 
    # the minion is already in the desired state.
    required_changes = __salt__["netbox.check_ipaddress"](
        address=address,
        interface=interface,
        virtual_machine=virtual_machine,
        cluster=cluster,
        device=device,
        vrf=vrf,
        tenant=tenant,
        status=status,
        role=role,
        nat_inside=nat_inside,
        dns_name=dns_name,
        description=description
    )
    if required_changes == False:
        ret["result"] = False
        ret["comment"] = "Something went wrong inside netbox.check_ipaddress"
        return ret
  
    # False: there was an error
    # None: No such virtual machine -> create
    # {} : No changes needed
    # {<data>} : apply changes

    # 3. If step 2 found that the minion is already in the desired state, 
    #    then exit immediately with a True result and without making any changes.

    if required_changes == {}:
        ret["result"] = True
        ret["comment"] = "{0} already in desired state".format(name)
        return ret

    # 4. If step 2 found that changes do need to be made, 
    # then check to see if the state was being run in test mode (i.e. with test=True). 
    # If so, then exit with a None result, a relevant comment, 
    # and (if possible) a changes entry describing what changes would be made.

    #TODO: The difference between changes({}) and new(None) should be handled
    #      more elegant...
    if __opts__["test"] and required_changes:
        ret["result"] = None
        ret["comment"] = "Attributes are set to be changed on {}".format(name)
        ret["changes"] = required_changes
        return ret
    if __opts__["test"] and not required_changes:
        ret["result"] = None
        ret["comment"] = "VMInterface {} would be created".format(name)
        ret["changes"] = {}
        return ret


    # 5. Make the desired changes. 
    # This should again be done using a function from an accompanying execution module. 
    # If the result of that function is enough to tell you whether or not an error occurred, 
    # then you can exit with a False result and a relevant comment to explain what happened.

    if required_changes == None:
        result = __salt__["netbox.create_ipaddress"](
            family="row row row your boat....",
            interface=interface,
            address=address,
            virtual_machine=virtual_machine,
            cluster=cluster,
            device=device,
            vrf=vrf,
            tenant=tenant,
            status=status,
            role=role,
            nat_inside=nat_inside,
            dns_name=dns_name,
            description=description
        )
        if result == False:
            log.error("Unable to create ip address")
            return False

    if required_changes:
        result = __salt__["netbox.update_ipaddress"](
            address,
            **required_changes
        )
        if result == False:
            log.error("Unable to update ip address")
            return False

    # 6. Perform the same check from step 2 again to confirm whether or not 
    # the minion is in the desired state. 
    # Just as in step 2, this function should be able to tell you by its 
    # return data whether or not changes need to be made.
    outstanding_changes = __salt__["netbox.check_ipaddress"](
        address=address,
        interface=interface,
        virtual_machine=virtual_machine,
        cluster=cluster,
        device=device,
        vrf=vrf,
        tenant=tenant,
        status=status,
        role=role,
        nat_inside=nat_inside,
        dns_name=dns_name,
        description=description
    )

    # 7. Set the return data and return!
    if outstanding_changes:
        # update failed, after create/update there are still required changes
        ret["comment"] = "Failed to reconcile attributes {}".format(outstanding_changes)
    elif required_changes:
        # update succesfully
        ret["result"] = True
        ret["comment"] = "{} updated".format(name)
        ret["changes"] = required_changes
    else:
        # created succesfully
        ret["result"] = True
        ret["comment"] = "{} created".format(name)
        ret["changes"] = result
    return ret


def cluster_type(
    name,
    description=None
    ):

    # 1. Set up the return dictionary and perform any necessary input validation (type checking, looking for use of mutually-exclusive arguments, etc.).
    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    # 2. Check if changes need to be made. 
    # This is best done with an information-gathering function in an accompanying execution module. 
    # The state should be able to use the return from this function to tell whether or not 
    # the minion is already in the desired state.
    required_changes = __salt__["netbox.check_cluster_type"](
        name,
        description=description
    )
    if required_changes == False:
        ret["result"] = False
        ret["comment"] = "Something went wrong inside netbox.check_cluster_type"
        return ret
  
    # False: there was an error
    # None: No such virtual machine -> create
    # {} : No changes needed
    # {<data>} : apply changes

    # 3. If step 2 found that the minion is already in the desired state, 
    #    then exit immediately with a True result and without making any changes.

    if required_changes == {}:
        ret["result"] = True
        ret["comment"] = "{0} already in desired state".format(name)
        return ret

    # 4. If step 2 found that changes do need to be made, 
    # then check to see if the state was being run in test mode (i.e. with test=True). 
    # If so, then exit with a None result, a relevant comment, 
    # and (if possible) a changes entry describing what changes would be made.

    #TODO: The difference between changes({}) and new(None) should be handled
    #      more elegant...
    if __opts__["test"] and required_changes:
        ret["result"] = None
        ret["comment"] = "Attributes are set to be changed on {}".format(name)
        ret["changes"] = required_changes
        return ret
    if __opts__["test"] and not required_changes:
        ret["result"] = None
        ret["comment"] = "cluster_type {} would be created".format(name)
        ret["changes"] = {}
        return ret


    # 5. Make the desired changes. 
    # This should again be done using a function from an accompanying execution module. 
    # If the result of that function is enough to tell you whether or not an error occurred, 
    # then you can exit with a False result and a relevant comment to explain what happened.

    if required_changes == None:
        result = __salt__["netbox.create_cluster_type"](
            name,
            description=description
        )
        if result == False:
            log.error("Unable to create cluster_type")
            return False

    if required_changes:
        result = __salt__["netbox.update_cluster_type"](
            name,
            **required_changes
        )
        if result == False:
            log.error("Unable to update cluster_type")
            return False

    # 6. Perform the same check from step 2 again to confirm whether or not 
    # the minion is in the desired state. 
    # Just as in step 2, this function should be able to tell you by its 
    # return data whether or not changes need to be made.
    outstanding_changes = __salt__["netbox.check_cluster_type"](
            name,
            description=description
    )

    # 7. Set the return data and return!
    if outstanding_changes:
        # update failed, after create/update there are still required changes
        ret["comment"] = "Failed to reconcile attributes {}".format(outstanding_changes)
    elif required_changes:
        # update succesfully
        ret["result"] = True
        ret["comment"] = "{} updated".format(name)
        ret["changes"] = required_changes
    else:
        # created succesfully
        ret["result"] = True
        ret["comment"] = "{} created".format(name)
        ret["changes"] = result
    return ret

def cluster(
    name,
    cluster_type=None,
    group=None,
    tenant=None,
    site=None,
    comments=None
    ):

    # 1. Set up the return dictionary and perform any necessary input validation (type checking, looking for use of mutually-exclusive arguments, etc.).
    ret = {"name": name, "result": False, "changes": {}, "comment": ""}
    if not cluster_type:
        ret['comment'] = "cluster_type is mandatory attribute for \"cluster\" state"
        return ret

    # 2. Check if changes need to be made. 
    # This is best done with an information-gathering function in an accompanying execution module. 
    # The state should be able to use the return from this function to tell whether or not 
    # the minion is already in the desired state.
    required_changes = __salt__["netbox.check_cluster"](
        name,
        cluster_type=cluster_type,
        group=group,
        tenant=tenant,
        site=site,
        comments=comments
    )
    if required_changes == False:
        ret["result"] = False
        ret["comment"] = "Something went wrong inside netbox.check_cluster"
        return ret
  
    # False: there was an error
    # None: No such virtual machine -> create
    # {} : No changes needed
    # {<data>} : apply changes

    # 3. If step 2 found that the minion is already in the desired state, 
    #    then exit immediately with a True result and without making any changes.

    if required_changes == {}:
        ret["result"] = True
        ret["comment"] = "{0} already in desired state".format(name)
        return ret

    # 4. If step 2 found that changes do need to be made, 
    # then check to see if the state was being run in test mode (i.e. with test=True). 
    # If so, then exit with a None result, a relevant comment, 
    # and (if possible) a changes entry describing what changes would be made.

    #TODO: The difference between changes({}) and new(None) should be handled
    #      more elegant...
    if __opts__["test"] and required_changes:
        ret["result"] = None
        ret["comment"] = "Attributes are set to be changed on {}".format(name)
        ret["changes"] = required_changes
        return ret
    if __opts__["test"] and not required_changes:
        ret["result"] = None
        ret["comment"] = "cluster {} would be created".format(name)
        ret["changes"] = {}
        return ret


    # 5. Make the desired changes. 
    # This should again be done using a function from an accompanying execution module. 
    # If the result of that function is enough to tell you whether or not an error occurred, 
    # then you can exit with a False result and a relevant comment to explain what happened.

    if required_changes == None:
        result = __salt__["netbox.create_cluster"](
            name,
            cluster_type=cluster_type,
            group=group,
            tenant=tenant,
            site=site,
            comments=comments,
        )
        if result == False:
            log.error("Unable to create cluster")
            return False

    if required_changes:
        result = __salt__["netbox.update_cluster"](
            name,
            **required_changes
        )
        if result == False:
            log.error("Unable to update cluster")
            return False

    # 6. Perform the same check from step 2 again to confirm whether or not 
    # the minion is in the desired state. 
    # Just as in step 2, this function should be able to tell you by its 
    # return data whether or not changes need to be made.
    outstanding_changes = __salt__["netbox.check_cluster"](
        name,
        cluster_type=cluster_type,
        group=group,
        tenant=tenant,
        site=site,
        comments=comments
    )

    # 7. Set the return data and return!
    if outstanding_changes:
        # update failed, after create/update there are still required changes
        ret["comment"] = "Failed to reconcile attributes {}".format(outstanding_changes)
    elif required_changes:
        # update succesfully
        ret["result"] = True
        ret["comment"] = "{} updated".format(name)
        ret["changes"] = required_changes
    else:
        # created succesfully
        ret["result"] = True
        ret["comment"] = "{} created".format(name)
        ret["changes"] = result
    return ret
