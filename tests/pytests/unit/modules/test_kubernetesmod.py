import salt.modules.kubernetesmod as kmod
import pytest, collections

def test_dict_to_service_spec_should_set_all_existent_attributes_on_spec():
    expected_spec = kmod.kubernetes.client.V1ServiceSpec()
    expected_spec.ports = []
    expected_spec.cluster_ip = "dummy"
    expected_spec.external_i_ps = "dummy"
    expected_spec.external_name = "dummy"
    expected_spec.external_traffic_policy = "dummy"
    expected_spec.health_check_node_port = "dummy"
    expected_spec.load_balancer_ip = "dummy"
    expected_spec.load_balancer_source_ranges = "dummy"
    expected_spec.selector = "dummy"
    expected_spec.session_affinity = "dummy"
    expected_spec.type = "dummy"
    data = {"test": "test"}
    data.update(expected_spec.to_dict())
    actual_spec = kmod.__dict_to_service_spec(spec=data)

    assert actual_spec.to_dict() == expected_spec.to_dict()

def test_dict_to_service_spec_with_ports():
    expected_spec = kmod.kubernetes.client.V1ServiceSpec()
    expected_spec.ports = {'name': 'tai-tomcat-service', 'protocol': 'TCP', 'port': 18080, 'targetPort': 18080}
    expected_spec.cluster_ip = "dummy"
    expected_spec.external_i_ps = "dummy"
    expected_spec.external_name = "dummy"
    expected_spec.external_traffic_policy = "dummy"
    expected_spec.health_check_node_port = "dummy"
    expected_spec.load_balancer_ip = "dummy"
    expected_spec.load_balancer_source_ranges = "dummy"
    expected_spec.selector = "dummy"
    expected_spec.session_affinity = "dummy"
    expected_spec.type = "dummy"
    data = {"test": "test"}
    data.update(expected_spec.to_dict())
    kmod.__dict_to_service_spec(spec=data)

def test_dict_to_service_spec_should_raise_exception():
    print(30*">", "This below should be successful")
    kube_port = kmod.kubernetes.client.V1ServicePort(port=42)
    print(30*">", "This below should raise exception on py module kubernetes==11.0.0")
    with pytest.raises(ValueError) as ve:
        kube_port = kmod.kubernetes.client.V1ServicePort()

