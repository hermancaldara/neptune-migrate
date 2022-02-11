# -*- coding: utf-8 -*-
import datetime
import os
import re
import unittest

from mock import MagicMock, Mock, call, patch
from rdflib.graph import ConjunctiveGraph

from neptune_migrate.config import Config
from neptune_migrate.core.exceptions import MigrationException
from neptune_migrate.main import Virtuoso
from neptune_migrate.neptune.client import NeptuneClient
from tests import BaseTest, create_file, delete_files


class VirtuosoTest(BaseTest):
    def setUp(self):
        super(VirtuosoTest, self).setUp()
        self.config = Config()
        self.config.put("database_migrations_dir", ".")
        self.config.put("database_ontology", "test.ttl")
        self.config.put("database_graph", "test")
        self.config.put("database_host", "localhost")
        self.config.put("database_user", "user")
        self.config.put("database_password", "password")
        self.config.put("database_port", 9999)
        self.config.put("database_endpoint", "endpoint")
        self.config.put("host_user", "host-user")
        self.config.put("host_password", "host-passwd")
        self.config.put("virtuoso_dirs_allowed", "/tmp")
        self.config.put("migration_graph", "http://example.com/")
        self.config.put("aws_access_key", "a-fake-access-key")
        self.config.put("aws_secret_access_key", "a-fake-secret-access-key")
        self.config.put("aws_neptune_url", "https://fake-neptune-host.com:8182")
        self.config.put("aws_neptune_host", "fake-neptune-host.com:8182")
        self.config.put("aws_region", "sa-east-1")
        create_file("test.ttl", "")

        self.data_ttl_content = """
@prefix : <http://example.com/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
<http://example.com/John> rdf:type <http://example.com/Person>.
"""

        create_file("data.ttl", self.data_ttl_content)

        self.structure_01_ttl_content = """
@prefix : <http://example.com/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

:Actor rdf:type owl:Class .
:SoapOpera rdf:type owl:Class .
"""

        create_file("structure_01.ttl", self.structure_01_ttl_content)

        self.structure_02_ttl_content = """
@prefix : <http://example.com/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

:Actor rdf:type owl:Class .
:SoapOpera rdf:type owl:Class .
:RoleOnSoapOpera rdf:type owl:Class .

:role rdf:type owl:Class ;
                rdfs:subClassOf [
                    rdf:type owl:Restriction ;
                    owl:onProperty :play_a_role ;
                    owl:onClass :RoleOnSoapOpera ;
                    owl:minQualifiedCardinality "1"^^xsd:nonNegativeInteger ;
                    owl:maxQualifiedCardinality "1"^^xsd:nonNegativeInteger
                ] .
"""

        create_file("structure_02.ttl", self.structure_02_ttl_content)

        self.structure_03_ttl_content = """
@prefix : <http://example.com/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

:Actor rdf:type owl:Class .
:SoapOpera rdf:type owl:Class .
:RoleOnSoapOpera rdf:type owl:Class .

:role rdf:type owl:Class ;
                rdfs:subClassOf [
                    rdf:type owl:Restriction ;
                    owl:onProperty :play_a_role ;
                    owl:onClass :RoleOnSoapOpera ;
                    owl:minQualifiedCardinality "1111"^^xsd:nonNegativeInteger
                ] ,
                [
                    rdf:type owl:Restriction ;
                    owl:onProperty :play_a_role ;
                    owl:onClass :RoleOnSoapOpera ;
                    owl:maxQualifiedCardinality "3333"^^xsd:nonNegativeInteger
                ] .
"""

        create_file("structure_03.ttl", self.structure_03_ttl_content)

        self.structure_04_ttl_content = """
@prefix : <http://example.com/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

:Actor rdf:type owl:Class .
:SoapOpera rdf:type owl:Class .
:RoleOnSoapOpera rdf:type owl:Class .

:role rdf:type owl:Class ;
                rdfs:subClassOf [
                    rdf:type owl:Restriction ;
                    owl:onProperty :play_a_role ;
                    owl:onClass :RoleOnSoapOpera ;
                    owl:minQualifiedCardinality "1"^^xsd:nonNegativeInteger
                ] .
"""

        create_file("structure_04.ttl", self.structure_02_ttl_content)

    def tearDown(self):
        super(VirtuosoTest, self).tearDown()
        delete_files("*.ttl")

    #    @patch('subprocess.Popen', return_value=Mock(**{"communicate.return_value": ("out", "err")}))
    #    def test_it_should_use_popen_to_run_a_command(self, popen_mock):
    #        Virtuoso(self.config).command_call("echo 1")
    #        popen_mock.assert_called_with('echo 1', shell=True, stderr=-1, stdout=-1)

    #    def test_it_should_return_stdout_and_stderr(self):
    #        stdout, _ = Virtuoso(self.config).command_call("echo 'out'")
    #        _, stderr = Virtuoso(self.config).command_call("python -V")
    #
    #        self.assertEqual('out\n', stdout)
    #        self.assertEqual('python', stderr.split(' ')[0].lower())

    @patch("subprocess.Popen.communicate", return_value=("", ""))
    @patch("subprocess.Popen.__init__", return_value=None)
    def test_it_should_use_isql_executable_to_send_commands_to_virtuoso(
        self, popen_mock, communicate_mock
    ):
        virtuoso = Virtuoso(self.config)
        virtuoso._run_isql("command")
        popen_mock.assert_called_with(
            'echo "command" | isql -U user -P password -H localhost -S 9999 -b 1',
            shell=True,
            stderr=-1,
            stdout=-1,
        )

    @patch("subprocess.Popen.communicate", return_value=("", ""))
    @patch("subprocess.Popen.__init__", return_value=None)
    def test_it_should_set_the_command_buffer_size_on_isql_calls_to_support_large_commands(
        self, popen_mock, communicate_mock
    ):
        virtuoso = Virtuoso(self.config)
        cmd = "0123456789" * 250000
        virtuoso._run_isql(cmd)
        popen_mock.assert_called_with(
            'echo "%s" | isql -U user -P password -H localhost -S 9999 -b 2500' % cmd,
            shell=True,
            stderr=-1,
            stdout=-1,
        )

    @patch("subprocess.Popen.communicate", return_value=("", ""))
    @patch("subprocess.Popen.__init__", return_value=None)
    def test_it_should_use_file_size_as_the_command_buffer_size_on_isql_calls(
        self, popen_mock, communicate_mock
    ):
        virtuoso = Virtuoso(self.config)
        create_file("big_file.ttl", "0123456789" * 480000)
        virtuoso._run_isql("big_file.ttl", True)
        popen_mock.assert_called_with(
            'isql -U user -P password -H localhost -S 9999 -b 4800 < "big_file.ttl"',
            shell=True,
            stderr=-1,
            stdout=-1,
        )

    #    @patch('neptune_migrate.virtuoso.Virtuoso.command_call',
    #           return_value=('', 'some error'))
    #    def test_it_should_raise_error_if_isql_status_return_error(self, command_call_mock):
    #        virtuoso = Virtuoso(self.config)
    #        self.assertRaisesWithMessage(Exception, 'could not connect to virtuoso: some error', virtuoso.connect)

    def test_it_should_log_stdout_when_executing_change(self):
        execution_log = Mock()
        virtuoso = Virtuoso(self.config)
        virtuoso.execute_change("sparql_up", "sparql_down", execution_log)
        execution_log.assert_called

    @patch.object(NeptuneClient, "execute_query")
    def test_it_should_get_current_version_none_when_database_is_empty(
        self, mock_execute_query
    ):
        mock_execute_query.return_value = {"results": {"bindings": []}}
        current, source = Virtuoso(self.config).get_current_version()

        mock_execute_query.assert_called_with(
            'prefix owl: <http://www.w3.org/2002/07/owl#>\nprefix xsd: <http://www.w3.org/2001/XMLSchema#>\nselect distinct ?version ?origen\nFROM <http://example.com/>\n{{\nselect distinct ?version ?origen ?data\nwhere {?s owl:versionInfo ?version;\n<http://example.com/commited> ?data;\n<http://example.com/produto> "test";\n<http://example.com/origen> ?origen.}\nORDER BY desc(?data) LIMIT 1\n}}'
        )
        self.assertIsNone(current)
        self.assertIsNone(source)

    @patch.object(NeptuneClient, "execute_query")
    def test_it_should_get_current_version_when_database_is_not_empty(
        self, mock_execute_query
    ):
        mock_execute_query.return_value = {
            "results": {
                "bindings": [
                    {
                        "version": {"type": "string", "value": 2},
                        "origen": {"type": "string", "value": "git"},
                    },
                    {
                        "version": {"type": "string", "value": 1},
                        "origen": {"type": "string", "value": "file"},
                    },
                ]
            }
        }

        current, source = Virtuoso(self.config).get_current_version()

        self.assertEqual("2", current)
        self.assertEqual("git", source)

    def test_it_should_get_sparql_statments_from_given_ontology(self):

        query_up, query_down = Virtuoso(self.config).get_sparql(
            destination_ontology=self.data_ttl_content, insert="data.ttl"
        )

        self.assertEqual(
            [
                'INSERT DATA { GRAPH <http://example.com/> { [] owl:versionInfo "None"; <http://example.com/endpoint> "endpoint"; <http://example.com/usuario> "user"; <http://example.com/ambiente> "localhost"; <http://example.com/produto> "test"; <http://example.com/commited> "%s"^^xsd:dateTime; <http://example.com/origen> "None"; <http://example.com/inserted> "data.ttl".} };'
                % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ],
            query_up,
        )
        self.assertEqual(
            [
                'WITH <http://example.com/> DELETE {?s ?p ?o} WHERE {?s owl:versionInfo "None"; <http://example.com/endpoint> "endpoint"; <http://example.com/usuario> "user"; <http://example.com/ambiente> "localhost"; <http://example.com/produto> "test"; <http://example.com/commited> "%s"^^xsd:dateTime; <http://example.com/origen> "None"; <http://example.com/inserted> "data.ttl"; ?p ?o.};'
                % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ],
            query_down,
        )

    def test_it_should_get_sparql_statments_from_given_ontology_when_breaking_a_blank_node_in_two(
        self,
    ):
        query_up, query_down = Virtuoso(self.config).get_sparql(
            current_ontology=self.structure_02_ttl_content,
            destination_ontology=self.structure_03_ttl_content,
        )

        self.assertTrue(len(query_up), 3)
        self.assertTrue(
            query_up[0].startswith(
                "WITH <{}> DELETE".format(self.config.get("database_graph"))
            )
        )
        self.assertTrue(query_up[1].startswith("INSERT DATA"))
        self.assertTrue(query_up[2].startswith("INSERT DATA"))

        self.assertTrue(len(query_down), 3)
        self.assertTrue(
            query_down[0].startswith(
                "WITH <{}> DELETE".format(self.config.get("database_graph"))
            )
        )
        self.assertTrue(
            query_down[1].startswith(
                "WITH <{}> DELETE".format(self.config.get("database_graph"))
            )
        )
        self.assertTrue(query_down[2].startswith("INSERT DATA"))

    def test_generate_migration_sparql_commands_when_only_a_triple_of_an_existing_blank_node_is_deleted(
        self,
    ):
        ttl_before = self.structure_02_ttl_content
        graph_before = ConjunctiveGraph()
        graph_before.parse(data=ttl_before, format="turtle")

        ttl_after = self.structure_04_ttl_content
        graph_after = ConjunctiveGraph()
        graph_after.parse(data=ttl_after, format="turtle")

        virtuoso_ = Virtuoso(self.config)

        query_up, query_down = virtuoso_._generate_migration_sparql_commands(
            origin_store=graph_after, destination_store=graph_before
        )
        expected_query_up = [
            'INSERT DATA { GRAPH <test> { <http://example.com/role> <http://www.w3.org/2000/01/rdf-schema#subClassOf> [<http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#Restriction> ; <http://www.w3.org/2002/07/owl#minQualifiedCardinality> "1"^^<http://www.w3.org/2001/XMLSchema#integer> ; <http://www.w3.org/2002/07/owl#onClass> <http://example.com/RoleOnSoapOpera> ; <http://www.w3.org/2002/07/owl#onProperty> <http://example.com/play_a_role> ; ] } };'
        ]
        expected_query_down = [
            'WITH <test> DELETE { <http://example.com/role> <http://www.w3.org/2000/01/rdf-schema#subClassOf>  ?s. ?s <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#Restriction> ; <http://www.w3.org/2002/07/owl#minQualifiedCardinality> "1"^^<http://www.w3.org/2001/XMLSchema#integer> ; <http://www.w3.org/2002/07/owl#onClass> <http://example.com/RoleOnSoapOpera> ; <http://www.w3.org/2002/07/owl#onProperty> <http://example.com/play_a_role>  } WHERE { <http://example.com/role> <http://www.w3.org/2000/01/rdf-schema#subClassOf>  ?s. ?s <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#Restriction> ; <http://www.w3.org/2002/07/owl#minQualifiedCardinality> "1"^^<http://www.w3.org/2001/XMLSchema#integer> ; <http://www.w3.org/2002/07/owl#onClass> <http://example.com/RoleOnSoapOpera> ; <http://www.w3.org/2002/07/owl#onProperty> <http://example.com/play_a_role>  };'
        ]
        self.assertEqual(query_up, expected_query_up)
        self.assertEqual(query_down, expected_query_down)

    def test_it_should_get_sparql_statments_when_forward_migration(self):
        query_up, query_down = Virtuoso(self.config).get_sparql(
            current_ontology=self.structure_01_ttl_content,
            destination_ontology=self.structure_02_ttl_content,
            origen="file",
            destination_version="02",
        )

        expected_lines_up = [
            "INSERT DATA { GRAPH <test> { <http://example.com/RoleOnSoapOpera> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#Class> . } };",
            "INSERT DATA { GRAPH <test> { <http://example.com/role> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#Class> . } };",
        ]

        expected_log_migration_up = """INSERT DATA { GRAPH <http://example.com/> { [] owl:versionInfo "02"; <http://example.com/endpoint> "endpoint"; <http://example.com/usuario> "user"; <http://example.com/ambiente> "localhost"; <http://example.com/produto> "test"; <http://example.com/commited> "%s"^^xsd:dateTime; <http://example.com/origen> "file"; <http://example.com/changes> "<log>".} };""" % datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        expected_lines_down = [
            "WITH <test> DELETE { <http://example.com/role> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#Class> . } WHERE { <http://example.com/role> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#Class> . }",
            "WITH <test> DELETE { <http://example.com/RoleOnSoapOpera> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#Class> . } WHERE { <http://example.com/RoleOnSoapOpera> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#Class> . }",
        ]

        expected_log_migration_down = """WITH <http://example.com/> DELETE {?s ?p ?o} WHERE {?s owl:versionInfo "02"; <http://example.com/endpoint> "endpoint"; <http://example.com/usuario> "user"; <http://example.com/ambiente> "localhost"; <http://example.com/produto> "test"; <http://example.com/commited> "%s"^^xsd:dateTime; <http://example.com/origen> "file"; <http://example.com/changes> "<log>"; ?p ?o.};""" % datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        self.assertEqual(4, len(query_up))
        [self.assertTrue(l in query_up) for l in expected_lines_up]
        self.assertEqual(
            query_up[-1],
            expected_log_migration_up.replace(
                "<log>",
                "\n".join(query_up[0:-1]).replace('"', '\\"').replace("\n", "\\n"),
            ),
        )

        matchObj = re.search(
            r"INSERT DATA { GRAPH <test> { <http://example.com/role> <http://www.w3.org/2000/01/rdf-schema#subClassOf> \[(.*)\] } };",
            "\n".join(query_up),
            re.MULTILINE,
        )
        sub_classes = [
            c.strip(" \t\n\r") for c in re.split(r" ; | \?s\. \?s ", matchObj.group(1))
        ]
        [
            self.assertTrue(c in sub_classes)
            for c in [
                '<http://www.w3.org/2002/07/owl#minQualifiedCardinality> "1"^^<http://www.w3.org/2001/XMLSchema#integer>',
                '<http://www.w3.org/2002/07/owl#maxQualifiedCardinality> "1"^^<http://www.w3.org/2001/XMLSchema#integer>',
                "<http://www.w3.org/2002/07/owl#onClass> <http://example.com/RoleOnSoapOpera>",
                "<http://www.w3.org/2002/07/owl#onProperty> <http://example.com/play_a_role>",
                "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#Restriction>",
            ]
        ]

        self.assertEqual(4, len(query_down))
        [self.assertTrue(l in query_down) for l in expected_lines_down]
        self.assertEqual(
            query_down[-1],
            expected_log_migration_down.replace(
                "<log>",
                "\n".join(query_up[0:-1]).replace('"', '\\"').replace("\n", "\\n"),
            ),
        )

        matchObj = re.search(
            r"WITH <test> DELETE {(.*)} WHERE {(.*)};",
            "\n".join(query_down),
            re.MULTILINE,
        )
        sub_classes_01 = [
            c.strip(" \t\n\r") for c in re.split(r" ; | \?s\. \?s ", matchObj.group(1))
        ]
        sub_classes_02 = [
            c.strip(" \t\n\r") for c in re.split(r" ; | \?s\. \?s ", matchObj.group(2))
        ]
        [
            self.assertTrue((c in sub_classes_01) and (c in sub_classes_02))
            for c in [
                "<http://example.com/role> <http://www.w3.org/2000/01/rdf-schema#subClassOf>",
                '<http://www.w3.org/2002/07/owl#minQualifiedCardinality> "1"^^<http://www.w3.org/2001/XMLSchema#integer>',
                '<http://www.w3.org/2002/07/owl#maxQualifiedCardinality> "1"^^<http://www.w3.org/2001/XMLSchema#integer>',
                "<http://www.w3.org/2002/07/owl#onClass> <http://example.com/RoleOnSoapOpera>",
                "<http://www.w3.org/2002/07/owl#onProperty> <http://example.com/play_a_role>",
                "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#Restriction>",
            ]
        ]

    def test_it_should_get_sparql_statments_when_backward_migration(self):

        query_up, query_down = Virtuoso(self.config).get_sparql(
            current_ontology=self.structure_02_ttl_content,
            destination_ontology=self.structure_01_ttl_content,
            origen="file",
            destination_version="01",
        )

        expected_lines_up = [
            "WITH <test> DELETE { <http://example.com/role> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#Class> . } WHERE { <http://example.com/role> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#Class> . }",
            "WITH <test> DELETE { <http://example.com/RoleOnSoapOpera> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#Class> . } WHERE { <http://example.com/RoleOnSoapOpera> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#Class> . }",
        ]

        expected_log_migration_up = """INSERT DATA { GRAPH <http://example.com/> { [] owl:versionInfo "01"; <http://example.com/endpoint> "endpoint"; <http://example.com/usuario> "user"; <http://example.com/ambiente> "localhost"; <http://example.com/produto> "test"; <http://example.com/commited> "%s"^^xsd:dateTime; <http://example.com/origen> "file"; <http://example.com/changes> "<log>".} };""" % datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        expected_lines_down = [
            "INSERT DATA { GRAPH <test> { <http://example.com/RoleOnSoapOpera> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#Class> . } };",
            "INSERT DATA { GRAPH <test> { <http://example.com/role> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#Class> . } };",
        ]

        expected_log_migration_down = """WITH <http://example.com/> DELETE {?s ?p ?o} WHERE {?s owl:versionInfo "01"; <http://example.com/endpoint> "endpoint"; <http://example.com/usuario> "user"; <http://example.com/ambiente> "localhost"; <http://example.com/produto> "test"; <http://example.com/commited> "%s"^^xsd:dateTime; <http://example.com/origen> "file"; <http://example.com/changes> "<log>"; ?p ?o.};""" % datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        """INSERT DATA { GRAPH <http://example.com/> { [] owl:versionInfo "01"; <http://example.com/endpoint> "endpoint"; <http://example.com/usuario> "user"; <http://example.com/ambiente> "localhost"; <http://example.com/produto> "test"; <http://example.com/commited> "%s"^^xsd:dateTime; <http://example.com/origen> "file"; <http://example.com/changes> "\\n<log>".} };""" % datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        self.assertEqual(4, len(query_up))
        [self.assertTrue(l in query_up) for l in expected_lines_up]
        self.assertEqual(
            query_up[-1],
            expected_log_migration_up.replace(
                "<log>",
                "\n".join(query_up[0:-1]).replace('"', '\\"').replace("\n", "\\n"),
            ),
        )

        matchObj = re.search(
            r"WITH <test> DELETE {(.*)} WHERE {(.*)};",
            "\n".join(query_up),
            re.MULTILINE,
        )
        sub_classes_01 = [
            c.strip(" \t\n\r") for c in re.split(r" ; | \?s\. \?s ", matchObj.group(1))
        ]
        sub_classes_02 = [
            c.strip(" \t\n\r") for c in re.split(r" ; | \?s\. \?s ", matchObj.group(2))
        ]
        [
            self.assertTrue((c in sub_classes_01) and (c in sub_classes_02))
            for c in [
                "<http://example.com/role> <http://www.w3.org/2000/01/rdf-schema#subClassOf>",
                '<http://www.w3.org/2002/07/owl#minQualifiedCardinality> "1"^^<http://www.w3.org/2001/XMLSchema#integer>',
                '<http://www.w3.org/2002/07/owl#maxQualifiedCardinality> "1"^^<http://www.w3.org/2001/XMLSchema#integer>',
                "<http://www.w3.org/2002/07/owl#onClass> <http://example.com/RoleOnSoapOpera>",
                "<http://www.w3.org/2002/07/owl#onProperty> <http://example.com/play_a_role>",
                "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#Restriction>",
            ]
        ]

        self.assertEqual(4, len(query_down))
        [self.assertTrue(l in query_down) for l in expected_lines_down]
        self.assertEqual(
            query_down[-1],
            expected_log_migration_down.replace(
                "<log>",
                "\n".join(query_up[0:-1]).replace('"', '\\"').replace("\n", "\\n"),
            ),
        )

        matchObj = re.search(
            r"INSERT DATA { GRAPH <test> { <http://example.com/role> <http://www.w3.org/2000/01/rdf-schema#subClassOf> \[(.*)\] } };",
            "\n".join(query_down),
            re.MULTILINE,
        )
        sub_classes = [
            c.strip(" \t\n\r") for c in re.split(r" ; | \?s\. \?s ", matchObj.group(1))
        ]
        [
            self.assertTrue(c in sub_classes)
            for c in [
                '<http://www.w3.org/2002/07/owl#minQualifiedCardinality> "1"^^<http://www.w3.org/2001/XMLSchema#integer>',
                '<http://www.w3.org/2002/07/owl#maxQualifiedCardinality> "1"^^<http://www.w3.org/2001/XMLSchema#integer>',
                "<http://www.w3.org/2002/07/owl#onClass> <http://example.com/RoleOnSoapOpera>",
                "<http://www.w3.org/2002/07/owl#onProperty> <http://example.com/play_a_role>",
                "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#Restriction>",
            ]
        ]

    #    @patch('neptune_migrate.virtuoso.Virtuoso.get_sparql')
    #    def test_it_should_get_statments_to_execute_when_comparing_the_given_file_with_the_current_version(self, get_sparql_mock):
    #        Virtuoso(self.config).get_statements("data.ttl", current_version='01', origen='file')
    #        get_sparql_mock.assert_called_with(None, self.data_ttl_content, '01', None, 'file', 'data.ttl')

    #    def test_it_should_raise_exception_when_getting_statments_of_an_unexistent_ttl_file(self):
    #        self.assertRaisesWithMessage(Exception, 'migration file does not exist (current_file.ttl)', Virtuoso(self.config).get_statements, "current_file.ttl", current_version='01', origen='file')

    def test_it_should_raise_exception_if_specified_ontology_does_not_exists_on_migrations_dir(
        self,
    ):
        self.config.update("database_ontology", "ontology.ttl")
        self.config.update("database_migrations_dir", ".")
        self.assertRaisesWithMessage(
            Exception,
            "migration file does not exist (./ontology.ttl)",
            Virtuoso(self.config).get_ontology_by_version,
            "01",
        )

    @patch("neptune_migrate.virtuoso.Git")
    def test_it_should_return_git_content(self, git_mock):
        execute_mock = Mock(**{"return_value": "content"})
        git_mock.return_value = Mock(**{"execute": execute_mock})

        content = Virtuoso(self.config).get_ontology_by_version("version")
        self.assertEqual("content", content)
        git_mock.assert_called_with(".")
        execute_mock.assert_called_with(["git", "show", "version:test.ttl"])

    def test_it_should_print_error_message_with_correct_encoding(self):
        graph = """
        :is_part_of rdf:type owl:ObjectProperty ;
                     rdfs:label "É parte de outro objeto" ;
                     rdfs:domain absent:Prefix ;
                     rdfs:range absent:Prefix .
        """

        expected_message = 'Error parsing graph at line 2 of <>:\nBad syntax (Prefix ":" not bound) at ^ in:\n"\n        ^:is_part_of rdf:type owl:ObjectProperty ;\n                  ..."'
        self.assertRaisesWithMessage(
            Exception,
            expected_message,
            Virtuoso(self.config).get_sparql,
            current_ontology=None,
            destination_ontology=graph,
        )


def export_git_file_side_effect(version):
    return "content_%s" % version


def temp_file_side_effect(content, reference):
    if reference == "file_down":
        return "filename_down.ttl"
    return "filename_up.ttl"


def command_call_side_effect(*args):
    if args[0].find("_up") > 0:
        return ("", "err")
    return ("out", "")


if __name__ == "__main__":
    unittest.main()
