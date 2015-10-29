
# -*- coding: utf-8 -*-
"""
:maintainer: Jean Praloran <jeanpralo@gmail.com>
:maturity: new
:depends: docker-compose>=1.5
:platform: all

Module to import docker-compose via saltstack
Author: Jean Praloran (jeanpralo@gmail.com)
All commands are not implemented yet (feel free to extend or PR):
  - build
  - run

  - logs
  - port
  - pull
  - scale
"""

import inspect
import logging
import os
import re

from operator import attrgetter
try:
	import compose
	from compose.cli.command import get_project
	from compose.service import ConvergenceStrategy
	HAS_DOCKERCOMPOSE = True
except ImportError:
	HAS_DOCKERCOMPOSE = False

MIN_DOCKERCOMPOSE = (1, 5, 0)
VERSION_RE = r'([\d.]+)'

log = logging.getLogger(__name__)
debug = True

__virtualname__ = 'dockercompose'
dc_filename = "docker-compose.yml"


def __virtual__():
	if HAS_DOCKERCOMPOSE:
		match = re.match(VERSION_RE, str(compose.__version__))
		if match:
			version = tuple([int(x) for x in match.group(1).split('.')])
			if MIN_DOCKERCOMPOSE >= version:
				return __virtualname__
		else:
			log.critical("Minimum version of docker-compose>=1.5.0")
	return False


def __standardize_result(status, message, data=None, debug_msg=None):
	"""
	Standardizes all responses

	:param status:
	:param message:
	:param data:
	:param debug_msg:
	:return:
	"""
	result = {
		'status': status,
		'message': message
	}

	if data is not None:
		result['return'] = data

	if debug_msg is not None and debug:
		result['debug'] = debug_msg

	return result


def __write_docker_compose(path, docker_compose):
	"""
	Write docker-compose to a temp directory
	in order to use it with docker-compose ( config check )

	:param path:

	docker_compose
		contains the docker-compose file

	:return:
	"""

	if os.path.isdir(path) is False:
		os.mkdir(path)
	f = open(os.path.join(path, dc_filename), 'w')
	if f:
		f.write(docker_compose)
		f.close()
	else:
		return __standardize_result(False, "Could not write docker-compose file in %s" % path, None, None)
	project = __load_project(path)
	if type(project) is dict:
		os.remove(os.path.join(path, dc_filename))
		return project
	return path


def __load_project(path):
	"""
	Load a docker-compose project from path

	:param path:
	:return:
	"""
	try:
		project = get_project(path)
	except Exception as inst:
		return __handle_except(inst)
	return project


def __handle_except(inst):
	"""
	Handle exception and return a standart result

	:param inst:
	:return:
	"""
	return __standardize_result(False, "Docker-compose command %s failed" % (inspect.stack()[1][3]), "%s" % (inst), None)


def _get_convergence_plans(project, service_names):
	"""
	Get action executed for each container

	:param project:
	:param service_names:
	:return:
	"""
	ret = {}
	plans = project._get_convergence_plans(project.get_services(service_names), ConvergenceStrategy.changed)
	for cont in plans:
		(action, container) = plans[cont]
		if action == 'create':
			ret[cont] = "Creating container"
		elif action == 'recreate':
			ret[cont] = "Re-creating container"
		elif action == 'start':
			ret[cont] = "Starting container"
		elif action == 'noop':
			ret[cont] = "Container is up to date"
	return ret


def create(path, docker_compose, **kwargs):
	"""
	Create and validate a docker-compose file into a directory

	path
		Path where the docker-compose file will be stored on the server

	docker_compose
		docker_compose file

	:param kwargs:
	:return:
	"""
	if docker_compose:
		ret = __write_docker_compose(path, docker_compose)
		if type(ret) is dict:
			return ret
	else:
		return __standardize_result(False, "Creating a docker-compose project failed, you must send a valid docker-compose file", None, None)
	return __standardize_result(True, "Successfully created the docker-compose file", {'compose.base_dir': path}, None)


def restart(path, service_names=None, **kwargs):
	"""
	Restart a docker-compose application

	path
		Path where the docker-compose file is stored on the server

	service_names
		If specified will restart only the specified services
	:return:
	"""

	project = __load_project(path)
	debug_ret = {}
	result = {}
	if type(project) is dict:
		return project
	else:
		try:
			project.restart(service_names)
			if debug:
				for container in project.containers():
					if service_names is None or container.get('Name')[1:] in service_names:
						container.inspect_if_not_inspected()
						debug_ret[container.get('Name')] = container.inspect()
						result[container.get('Name')] = 'restarted'
		except Exception as inst:
			return __handle_except(inst)
	return __standardize_result(True, 'Restarting containers via docker-compose', result, debug_ret)


def stop(path, service_names=None, **kwargs):
	"""
	Stop running containers

	path
		Path where the docker-compose file is stored on the server
	service_names
		If specified will restart only the specified services
	:return:
	"""

	project = __load_project(path)
	debug_ret = {}
	result = {}
	if type(project) is dict:
		return project
	else:
		try:
			project.stop(service_names)
			if debug:
				for container in project.containers(stopped=True):
					if service_names is None or container.get('Name')[1:] in service_names:
						container.inspect_if_not_inspected()
						debug_ret[container.get('Name')] = container.inspect()
						result[container.get('Name')] = 'stopped'
		except Exception as inst:
			return __handle_except(inst)
	return __standardize_result(True, 'Stopping containers via docker-compose', result, debug_ret)


def pause(path, service_names=None, **kwargs):
	"""
	Pause running containers

	path
		Path where the docker-compose file is stored on the server
	service_names
		If specified will restart only the specified services
	:return:
	"""

	project = __load_project(path)
	debug_ret = {}
	result = {}
	if type(project) is dict:
		return project
	else:
		try:
			project.pause(service_names)
			if debug:
				for container in project.containers():
					if service_names is None or container.get('Name')[1:] in service_names:
						container.inspect_if_not_inspected()
						debug_ret[container.get('Name')] = container.inspect()
						result[container.get('Name')] = 'paused'
		except Exception as inst:
			return __handle_except(inst)
	return __standardize_result(True, 'Pausing containers via docker-compose', result, debug_ret)


def unpause(path, service_names=None, **kwargs):
	"""
	Un-Pause paused containers

	path
		Path where the docker-compose file is stored on the server
	service_names
		If specified will restart only the specified services
	:return:
	"""

	project = __load_project(path)
	debug_ret = {}
	result = {}
	if type(project) is dict:
		return project
	else:
		try:
			project.unpause(service_names)
			if debug:
				for container in project.containers():
					if service_names is None or container.get('Name')[1:] in service_names:
						container.inspect_if_not_inspected()
						debug_ret[container.get('Name')] = container.inspect()
						result[container.get('Name')] = 'unpaused'
		except Exception as inst:
			return __handle_except(inst)
	return __standardize_result(True, 'Un-Pausing containers via docker-compose', result, debug_ret)


def start(path, service_names=None, **kwargs):
	"""
	Start stopped containers

	path
		Path where the docker-compose file is stored on the server
	service_names
		If specified will restart only the specified services
	:return:
	"""

	project = __load_project(path)
	debug_ret = {}
	result = {}
	if type(project) is dict:
		return project
	else:
		try:
			project.start(service_names)
			if debug:
				for container in project.containers():
					if service_names is None or container.get('Name')[1:] in service_names:
						container.inspect_if_not_inspected()
						debug_ret[container.get('Name')] = container.inspect()
						result[container.get('Name')] = 'started'
		except Exception as inst:
			return __handle_except(inst)
	return __standardize_result(True, 'Starting containers via docker-compose', result, debug_ret)


def kill(path, service_names=None, **kwargs):
	"""
	Kill running containers

	path
		Path where the docker-compose file is stored on the server
	service_names
		If specified will restart only the specified services
	:return:
	"""

	project = __load_project(path)
	debug_ret = {}
	result = {}
	if type(project) is dict:
		return project
	else:
		try:
			project.kill(service_names)
			if debug:
				for container in project.containers(stopped=True):
					if service_names is None or container.get('Name')[1:] in service_names:
						container.inspect_if_not_inspected()
						debug_ret[container.get('Name')] = container.inspect()
						result[container.get('Name')] = 'killed'
		except Exception as inst:
			return __handle_except(inst)
	return __standardize_result(True, 'Killing containers via docker-compose', result, debug_ret)


def rm(path, service_names=None, **kwargs):
	"""
	Remove stopped containers

	path
		Path where the docker-compose file is stored on the server
	service_names
		If specified will restart only the specified services
	:return:
	"""

	project = __load_project(path)
	if type(project) is dict:
		return project
	else:
		try:
			project.remove_stopped(service_names)
		except Exception as inst:
			return __handle_except(inst)
	return __standardize_result(True, 'Removing stopped containers via docker-compose', None, None)


def ps(path, **kwargs):
	"""
	Return a list of the running containers for the docker-compose app

	path
		Path where the docker-compose file is stored on the server
	:return:
	"""
	project = __load_project(path)
	result = {}
	if type(project) is dict:
		return project
	else:
		containers = sorted(
			project.containers(None, stopped=True) +
			project.containers(None, one_off=True),
			key=attrgetter('name'))
		for container in containers:
			command = container.human_readable_command
			if len(command) > 30:
				command = '%s ...' % command[:26]
			result[container.name] = {
				'id': container.id,
				'name': container.name,
				'command': command,
				'state': container.human_readable_state,
				'ports': container.human_readable_ports,
			}
	return __standardize_result(True, "Listing docker-compose containers", result, None)


def up(path, service_names=None, **kwargs):
	"""
	Create and start containers

	path
		Path where the docker-compose file is  stored on the server
	service_names
		If specified will restart only the specified services
	:return:
	"""

	debug_ret = {}
	project = __load_project(path)
	if type(project) is dict:
		return project
	else:
		try:
			result = _get_convergence_plans(project, service_names)
			ret = project.up(service_names)
			if debug:
				for container in ret:
					if service_names is None or container.get('Name')[1:] in service_names:
						container.inspect_if_not_inspected()
						debug_ret[container.get('Name')] = container.inspect()
		except Exception as inst:
			return __handle_except(inst)
	return __standardize_result(True, 'Adding containers via docker-compose', result, debug_ret)
