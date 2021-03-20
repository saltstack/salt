"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import salt.states.boto_elasticache as boto_elasticache
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class BotoElasticacheTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.boto_elasticache
    """

    def setup_loader_modules(self):
        return {boto_elasticache: {}}

    # 'present' function tests: 1

    def test_present(self):
        """
        Test to ensure the cache cluster exists.
        """
        name = "myelasticache"
        engine = "redis"
        cache_node_type = "cache.t1.micro"

        ret = {"name": name, "result": None, "changes": {}, "comment": ""}

        mock = MagicMock(side_effect=[None, False, False, True])
        mock_bool = MagicMock(return_value=False)
        with patch.dict(
            boto_elasticache.__salt__,
            {"boto_elasticache.get_config": mock, "boto_elasticache.create": mock_bool},
        ):
            comt = "Failed to retrieve cache cluster info from AWS."
            ret.update({"comment": comt})
            self.assertDictEqual(
                boto_elasticache.present(name, engine, cache_node_type), ret
            )

            with patch.dict(boto_elasticache.__opts__, {"test": True}):
                comt = "Cache cluster {} is set to be created.".format(name)
                ret.update({"comment": comt})
                self.assertDictEqual(
                    boto_elasticache.present(name, engine, cache_node_type), ret
                )

            with patch.dict(boto_elasticache.__opts__, {"test": False}):
                comt = "Failed to create {} cache cluster.".format(name)
                ret.update({"comment": comt, "result": False})
                self.assertDictEqual(
                    boto_elasticache.present(name, engine, cache_node_type), ret
                )

                comt = "Cache cluster {} is present.".format(name)
                ret.update({"comment": comt, "result": True})
                self.assertDictEqual(
                    boto_elasticache.present(name, engine, cache_node_type), ret
                )

    # 'absent' function tests: 1

    def test_absent(self):
        """
        Test to ensure the named elasticache cluster is deleted.
        """
        name = "new_table"

        ret = {"name": name, "result": True, "changes": {}, "comment": ""}

        mock = MagicMock(side_effect=[False, True])
        with patch.dict(boto_elasticache.__salt__, {"boto_elasticache.exists": mock}):
            comt = "{} does not exist in None.".format(name)
            ret.update({"comment": comt})
            self.assertDictEqual(boto_elasticache.absent(name), ret)

            with patch.dict(boto_elasticache.__opts__, {"test": True}):
                comt = "Cache cluster {} is set to be removed.".format(name)
                ret.update({"comment": comt, "result": None})
                self.assertDictEqual(boto_elasticache.absent(name), ret)

    # 'creategroup' function tests: 1

    def test_creategroup(self):
        """
        Test to ensure the a replication group is create.
        """
        name = "new_table"
        primary_cluster_id = "A"
        replication_group_description = "my description"

        ret = {"name": name, "result": True, "changes": {}, "comment": ""}

        mock = MagicMock(return_value=True)
        with patch.dict(
            boto_elasticache.__salt__, {"boto_elasticache.group_exists": mock}
        ):
            comt = "{} replication group exists .".format(name)
            ret.update({"comment": comt})
            self.assertDictEqual(
                boto_elasticache.creategroup(
                    name, primary_cluster_id, replication_group_description
                ),
                ret,
            )
