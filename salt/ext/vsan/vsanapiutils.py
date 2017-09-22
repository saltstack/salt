#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright 2016 VMware, Inc.  All rights reserved.

This module defines basic helper functions used in the sampe codes
"""

# pylint: skip-file
__author__ = 'VMware, Inc'

from pyVmomi import vim, vmodl, SoapStubAdapter
#import the VSAN API python bindings
import vsanmgmtObjects

VSAN_API_VC_SERVICE_ENDPOINT = '/vsanHealth'
VSAN_API_ESXI_SERVICE_ENDPOINT = '/vsan'

#Constuct a stub for VSAN API access using VC or ESXi sessions from  existing
#stubs. Correspoding VC or ESXi service endpoint is required. VC service
#endpoint is used as default
def _GetVsanStub(
      stub, endpoint=VSAN_API_VC_SERVICE_ENDPOINT,
      context=None, version='vim.version.version10'
   ):

   hostname = stub.host.split(':')[0]
   vsanStub = SoapStubAdapter(
      host=hostname,
      path=endpoint,
      version=version,
      sslContext=context
   )
   vsanStub.cookie = stub.cookie
   return vsanStub

#Construct a stub for access VC side VSAN APIs
def GetVsanVcStub(stub, context=None):
   return _GetVsanStub(stub, endpoint=VSAN_API_VC_SERVICE_ENDPOINT,
                       context=context)

#Construct a stub for access ESXi side VSAN APIs
def GetVsanEsxStub(stub, context=None):
   return _GetVsanStub(stub, endpoint=VSAN_API_ESXI_SERVICE_ENDPOINT,
                       context=context)

#Construct a stub for access ESXi side VSAN APIs
def GetVsanVcMos(vcStub, context=None):
   vsanStub = GetVsanVcStub(vcStub, context)
   vcMos = {
      'vsan-disk-management-system' : vim.cluster.VsanVcDiskManagementSystem(
                                         'vsan-disk-management-system',
                                         vsanStub
                                      ),
      'vsan-stretched-cluster-system' : vim.cluster.VsanVcStretchedClusterSystem(
                                           'vsan-stretched-cluster-system',
                                           vsanStub
                                        ),
      'vsan-cluster-config-system' : vim.cluster.VsanVcClusterConfigSystem(
                                        'vsan-cluster-config-system',
                                        vsanStub
                                     ),
      'vsan-performance-manager' : vim.cluster.VsanPerformanceManager(
                                      'vsan-performance-manager',
                                      vsanStub
                                   ),
      'vsan-cluster-health-system' : vim.cluster.VsanVcClusterHealthSystem(
                                        'vsan-cluster-health-system',
                                        vsanStub
                                     ),
      'vsan-upgrade-systemex' : vim.VsanUpgradeSystemEx(
                                   'vsan-upgrade-systemex',
                                    vsanStub
                                ),
      'vsan-cluster-space-report-system' : vim.cluster.VsanSpaceReportSystem(
                                              'vsan-cluster-space-report-system',
                                              vsanStub
                                           ),

      'vsan-cluster-object-system' : vim.cluster.VsanObjectSystem(
                                        'vsan-cluster-object-system',
                                        vsanStub
                                     ),
   }

   return vcMos

#Construct a stub for access ESXi side VSAN APIs
def GetVsanEsxMos(esxStub, context=None):
   vsanStub = GetVsanEsxStub(esxStub, context)
   esxMos = {
      'vsan-performance-manager' : vim.cluster.VsanPerformanceManager(
                                      'vsan-performance-manager',
                                      vsanStub
                                   ),
      'ha-vsan-health-system' : vim.host.VsanHealthSystem(
                                        'ha-vsan-health-system',
                                        vsanStub
                                     ),
      'vsan-object-system' : vim.cluster.VsanObjectSystem(
                                        'vsan-object-system',
                                        vsanStub
                                     ),
   }

   return esxMos

#Convert a VSAN Task to a Task MO binding to VC service
#@param vsanTask the VSAN Task MO
#@param stub the stub for the VC API
def ConvertVsanTaskToVcTask(vsanTask, vcStub):
  vcTask = vim.Task(vsanTask._moId, vcStub)
  return vcTask

def WaitForTasks(tasks, si):
   """
   Given the service instance si and tasks, it returns after all the
   tasks are complete
   """

   pc = si.content.propertyCollector

   taskList = [str(task) for task in tasks]

   # Create filter
   objSpecs = [vmodl.query.PropertyCollector.ObjectSpec(obj=task)
                                                            for task in tasks]
   propSpec = vmodl.query.PropertyCollector.PropertySpec(type=vim.Task,
                                                         pathSet=[], all=True)
   filterSpec = vmodl.query.PropertyCollector.FilterSpec()
   filterSpec.objectSet = objSpecs
   filterSpec.propSet = [propSpec]
   filter = pc.CreateFilter(filterSpec, True)

   try:
      version, state = None, None

      # Loop looking for updates till the state moves to a completed state.
      while len(taskList):
         update = pc.WaitForUpdates(version)
         for filterSet in update.filterSet:
            for objSet in filterSet.objectSet:
               task = objSet.obj
               for change in objSet.changeSet:
                  if change.name == 'info':
                     state = change.val.state
                  elif change.name == 'info.state':
                     state = change.val
                  else:
                     continue

                  if not str(task) in taskList:
                     continue

                  if state == vim.TaskInfo.State.success:
                     # Remove task from taskList
                     taskList.remove(str(task))
                  elif state == vim.TaskInfo.State.error:
                     raise task.info.error
         # Move to next version
         version = update.version
   finally:
      if filter:
         filter.Destroy()
