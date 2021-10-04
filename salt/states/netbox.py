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

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "Attributes are set to be changed on {}".format(name)
        ret["changes"] = changes
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
