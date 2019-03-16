-- MySQL dump 10.15  Distrib 10.0.22-MariaDB, for Linux (x86_64)
--
-- Host: localhost    Database: salt
-- ------------------------------------------------------
-- Server version	10.0.22-MariaDB

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `jids`
--

CREATE DATABASE if not exists  `salt`
DEFAULT CHARACTER SET utf8
DEFAULT COLLATE utf8_general_ci;

USE `salt`;


DROP TABLE IF EXISTS `jids`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `jids` (
  `jid` varchar(255) NOT NULL,
  `load` mediumtext NOT NULL,
  UNIQUE KEY `jid` (`jid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `jids`
--

LOCK TABLES `jids` WRITE;
/*!40000 ALTER TABLE `jids` DISABLE KEYS */;
INSERT INTO `jids` VALUES ('20160719134843873492','{\"tgt_type\": \"compound\", \"jid\": \"20160719134843873492\", \"tgt\": \"G@virtual:physical and G@os:smartos\", \"cmd\": \"publish\", \"ret\": \"\", \"user\": \"root\", \"arg\": [], \"fun\": \"test.ping\"}'),('20160719134848959936','{\"tgt_type\": \"compound\", \"jid\": \"20160719134848959936\", \"tgt\": \"G@virtual:physical and G@os:smartos\", \"cmd\": \"publish\", \"ret\": \"\", \"user\": \"root\", \"arg\": [\"20160719134843873492\"], \"fun\": \"saltutil.find_job\"}'),('20160719134910163074','{\"tgt_type\": \"glob\", \"jid\": \"20160719134910163074\", \"cmd\": \"publish\", \"tgt\": \"twd\", \"kwargs\": {\"delimiter\": \":\", \"show_timeout\": true, \"show_jid\": false}, \"ret\": \"\", \"user\": \"root\", \"arg\": [], \"fun\": \"test.ping\"}'),('20160719134919147347','{\"tgt_type\": \"glob\", \"jid\": \"20160719134919147347\", \"cmd\": \"publish\", \"tgt\": \"twd\", \"kwargs\": {\"delimiter\": \":\", \"show_timeout\": true, \"show_jid\": false}, \"ret\": \"\", \"user\": \"root\", \"arg\": [], \"fun\": \"network.interfaces\"}'),('20160719135029732667','{\"tgt_type\": \"glob\", \"jid\": \"20160719135029732667\", \"cmd\": \"publish\", \"tgt\": \"twd\", \"kwargs\": {\"delimiter\": \":\", \"show_timeout\": true, \"show_jid\": false}, \"ret\": \"\", \"user\": \"root\", \"arg\": [{\"refresh\": true, \"__kwarg__\": true}], \"fun\": \"pkg.upgrade\"}'),('20160719135034878238','{\"tgt_type\": \"glob\", \"jid\": \"20160719135034878238\", \"cmd\": \"publish\", \"tgt\": \"twd\", \"kwargs\": {\"delimiter\": \":\"}, \"ret\": \"\", \"user\": \"root\", \"arg\": [\"20160719135029732667\"], \"fun\": \"saltutil.find_job\"}'),('20160719135044921491','{\"tgt_type\": \"glob\", \"jid\": \"20160719135044921491\", \"cmd\": \"publish\", \"tgt\": \"twd\", \"kwargs\": {\"delimiter\": \":\"}, \"ret\": \"\", \"user\": \"root\", \"arg\": [\"20160719135029732667\"], \"fun\": \"saltutil.find_job\"}');
/*!40000 ALTER TABLE `jids` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `salt_events`
--

DROP TABLE IF EXISTS `salt_events`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `salt_events` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `tag` varchar(255) NOT NULL,
  `data` mediumtext NOT NULL,
  `alter_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `master_id` varchar(255) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `tag` (`tag`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `salt_events`
--

LOCK TABLES `salt_events` WRITE;
/*!40000 ALTER TABLE `salt_events` DISABLE KEYS */;
/*!40000 ALTER TABLE `salt_events` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `salt_returns`
--

DROP TABLE IF EXISTS `salt_returns`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `salt_returns` (
  `fun` varchar(50) NOT NULL,
  `jid` varchar(255) NOT NULL,
  `return` mediumtext NOT NULL,
  `id` varchar(255) NOT NULL,
  `success` varchar(10) NOT NULL,
  `full_ret` mediumtext NOT NULL,
  `alter_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY `id` (`id`),
  KEY `jid` (`jid`),
  KEY `fun` (`fun`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `salt_returns`
--

LOCK TABLES `salt_returns` WRITE;
/*!40000 ALTER TABLE `salt_returns` DISABLE KEYS */;
INSERT INTO `salt_returns` VALUES ('test.ping','20160719134910163074','true','twd','1','{\"fun_args\": [], \"jid\": \"20160719134910163074\", \"return\": true, \"retcode\": 0, \"success\": true, \"cmd\": \"_return\", \"_stamp\": \"2016-07-19T19:49:10.295047\", \"fun\": \"test.ping\", \"id\": \"twd\"}','2016-07-19 19:49:10'),('network.interfaces','20160719134919147347','{\"lo\": {\"hwaddr\": \"00:00:00:00:00:00\", \"up\": true, \"inet\": [{\"broadcast\": null, \"netmask\": \"255.0.0.0\", \"address\": \"127.0.0.1\", \"label\": \"lo\"}], \"inet6\": [{\"prefixlen\": \"128\", \"scope\": \"host\", \"address\": \"::1\"}]}, \"docker0\": {\"hwaddr\": \"02:42:bb:e2:f6:7e\", \"up\": true, \"inet\": [{\"broadcast\": null, \"netmask\": \"255.255.0.0\", \"address\": \"172.17.0.1\", \"label\": \"docker0\"}]}, \"eno16777984\": {\"hwaddr\": \"00:0c:29:e3:6b:c8\", \"up\": true}, \"br0\": {\"hwaddr\": \"00:0c:29:e3:6b:c8\", \"up\": true, \"inet\": [{\"broadcast\": \"172.16.207.255\", \"netmask\": \"255.255.255.0\", \"address\": \"172.16.207.136\", \"label\": \"br0\"}], \"inet6\": [{\"prefixlen\": \"64\", \"scope\": \"link\", \"address\": \"fe80::20c:29ff:fee3:6bc8\"}]}}','twd','1','{\"fun_args\": [], \"jid\": \"20160719134919147347\", \"return\": {\"lo\": {\"hwaddr\": \"00:00:00:00:00:00\", \"up\": true, \"inet\": [{\"broadcast\": null, \"netmask\": \"255.0.0.0\", \"address\": \"127.0.0.1\", \"label\": \"lo\"}], \"inet6\": [{\"prefixlen\": \"128\", \"scope\": \"host\", \"address\": \"::1\"}]}, \"docker0\": {\"hwaddr\": \"02:42:bb:e2:f6:7e\", \"up\": true, \"inet\": [{\"broadcast\": null, \"netmask\": \"255.255.0.0\", \"address\": \"172.17.0.1\", \"label\": \"docker0\"}]}, \"eno16777984\": {\"hwaddr\": \"00:0c:29:e3:6b:c8\", \"up\": true}, \"br0\": {\"hwaddr\": \"00:0c:29:e3:6b:c8\", \"up\": true, \"inet\": [{\"broadcast\": \"172.16.207.255\", \"netmask\": \"255.255.255.0\", \"address\": \"172.16.207.136\", \"label\": \"br0\"}], \"inet6\": [{\"prefixlen\": \"64\", \"scope\": \"link\", \"address\": \"fe80::20c:29ff:fee3:6bc8\"}]}}, \"retcode\": 0, \"success\": true, \"cmd\": \"_return\", \"_stamp\": \"2016-07-19T19:49:19.222588\", \"fun\": \"network.interfaces\", \"id\": \"twd\"}','2016-07-19 19:49:19'),('saltutil.find_job','20160719135034878238','{\"tgt_type\": \"glob\", \"jid\": \"20160719135029732667\", \"tgt\": \"twd\", \"pid\": 5557, \"ret\": \"\", \"user\": \"root\", \"arg\": [{\"refresh\": true, \"__kwarg__\": true}], \"fun\": \"pkg.upgrade\"}','twd','1','{\"fun_args\": [\"20160719135029732667\"], \"jid\": \"20160719135034878238\", \"return\": {\"tgt_type\": \"glob\", \"jid\": \"20160719135029732667\", \"tgt\": \"twd\", \"pid\": 5557, \"ret\": \"\", \"user\": \"root\", \"arg\": [{\"refresh\": true, \"__kwarg__\": true}], \"fun\": \"pkg.upgrade\"}, \"retcode\": 0, \"success\": true, \"cmd\": \"_return\", \"_stamp\": \"2016-07-19T19:50:34.967377\", \"fun\": \"saltutil.find_job\", \"id\": \"twd\"}','2016-07-19 19:50:34'),('saltutil.find_job','20160719135044921491','{\"tgt_type\": \"glob\", \"jid\": \"20160719135029732667\", \"tgt\": \"twd\", \"pid\": 5557, \"ret\": \"\", \"user\": \"root\", \"arg\": [{\"refresh\": true, \"__kwarg__\": true}], \"fun\": \"pkg.upgrade\"}','twd','1','{\"fun_args\": [\"20160719135029732667\"], \"jid\": \"20160719135044921491\", \"return\": {\"tgt_type\": \"glob\", \"jid\": \"20160719135029732667\", \"tgt\": \"twd\", \"pid\": 5557, \"ret\": \"\", \"user\": \"root\", \"arg\": [{\"refresh\": true, \"__kwarg__\": true}], \"fun\": \"pkg.upgrade\"}, \"retcode\": 0, \"success\": true, \"cmd\": \"_return\", \"_stamp\": \"2016-07-19T19:50:45.034813\", \"fun\": \"saltutil.find_job\", \"id\": \"twd\"}','2016-07-19 19:50:45'),('pkg.upgrade','20160719135029732667','{\"comment\": \"\", \"changes\": {}, \"result\": true}','twd','1','{\"fun_args\": [{\"refresh\": true}], \"jid\": \"20160719135029732667\", \"return\": {\"comment\": \"\", \"changes\": {}, \"result\": true}, \"retcode\": 0, \"success\": true, \"cmd\": \"_return\", \"_stamp\": \"2016-07-19T19:50:52.016142\", \"fun\": \"pkg.upgrade\", \"id\": \"twd\"}','2016-07-19 19:50:52');
/*!40000 ALTER TABLE `salt_returns` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2016-07-19 13:52:18
