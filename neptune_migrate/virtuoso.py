# -*- coding: utf-8 -*-

import datetime
import logging
import os
import shutil
import subprocess

import rdflib
from git import Git
from rdflib.graph import ConjunctiveGraph, Graph
from rdflib.plugins.parsers.notation3 import BadSyntax

from neptune_migrate.neptune.auth import get_aws_auth
from neptune_migrate.neptune.client import NeptuneClient

from . import ssh
from .core.exceptions import MigrationException
from .helpers import Utils

logging.basicConfig()

ISQL = "isql -U %s -P %s -H %s -S %s"
ISQL_CMD = 'echo "%s" | %s -b %d'
ISQL_CMD_WITH_FILE = '%s -b %d < "%s"'
ISQL_UP = "set echo on;\n\
            DB.DBA.TTLP_MT_LOCAL_FILE('%(ttl)s', '', '%(graph)s');"
ISQL_DOWN = "SPARQL CLEAR GRAPH <%(graph)s>;"
ISQL_SERVER = "select server_root();"


class Virtuoso(object):
    """Interact with Virtuoso Server"""

    def __init__(self, config):
        self.migration_graph = config.get("migration_graph")
        self.__virtuoso_host = config.get("database_host", "")
        self.__virtuoso_user = config.get("database_user")
        self.__virtuoso_passwd = config.get("database_password")
        self.__host_user = config.get("host_user", None)
        self.__host_passwd = config.get("host_password", None)
        self.__virtuoso_dirs_allowed = config.get("virtuoso_dirs_allowed", None)
        self.__virtuoso_port = config.get("database_port")
        self.__virtuoso_endpoint = config.get("database_endpoint")
        self.__virtuoso_graph = config.get("database_graph")
        self.__virtuoso_ontology = config.get("database_ontology")
        self._migrations_dir = config.get("database_migrations_dir")
        self._neptune_client = NeptuneClient(get_aws_auth(config), config)

        if self.__virtuoso_dirs_allowed:
            self._virtuoso_dir = os.path.realpath(self.__virtuoso_dirs_allowed)
        else:
            self._virtuoso_dir = self._run_isql(ISQL_SERVER)[0].split("\n\n")[-2]

    def _run_isql(self, cmd, archive=False):
        conn = ISQL % (
            self.__virtuoso_user,
            self.__virtuoso_passwd,
            self.__virtuoso_host,
            self.__virtuoso_port,
        )
        if archive:
            isql_cmd = ISQL_CMD_WITH_FILE % (
                conn,
                max(os.path.getsize(cmd) / 1000, 1),
                cmd,
            )
        else:
            isql_cmd = ISQL_CMD % (cmd, conn, max(len(cmd) / 1000, 1))
        process = subprocess.Popen(
            isql_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout_value, stderr_value = process.communicate()
        if stderr_value:
            raise Exception(stderr_value)
        return stdout_value, stderr_value

    def _copy_ttl_to_virtuoso_dir(self, ttl):
        _, fixture_file = os.path.split(ttl)

        if self._is_local() or self.__virtuoso_dirs_allowed:
            origin = os.path.realpath(ttl)
            dest = os.path.realpath(os.path.join(self._virtuoso_dir, fixture_file))
            if origin != dest:
                shutil.copyfile(origin, dest)
        else:
            s = ssh.Connection(
                host=self.__virtuoso_host,
                username=self.__host_user,
                password=self.__host_passwd,
            )
            s.put(ttl, os.path.join(self._virtuoso_dir, fixture_file))
            s.close()
        return fixture_file

    def _is_local(self):
        return self.__virtuoso_host.lower() in ["localhost", "127.0.0.1"]

    def _remove_ttl_from_virtuoso_dir(self, ttl):
        ttl_path = os.path.join(self._virtuoso_dir, ttl)
        os.remove(ttl_path)

    def _upload_single_ttl_to_virtuoso(self, fixture):
        fixture = self._copy_ttl_to_virtuoso_dir(fixture)
        file_to_upload = os.path.join(self._virtuoso_dir, fixture)
        isql_up = ISQL_UP % {"ttl": file_to_upload, "graph": self.__virtuoso_graph}
        out, err = self._run_isql(isql_up)

        if self._is_local() or self.__virtuoso_dirs_allowed:
            self._remove_ttl_from_virtuoso_dir(fixture)
        return out, err

    def upload_ttls_to_virtuoso(self, full_path_files):
        response_dict = {}
        for fname in full_path_files:
            response_dict[fname] = self._upload_single_ttl_to_virtuoso(fname)
        return response_dict

    def execute_change(self, sparql_up, sparql_down, execution_log=None):
        """Final Step. Execute the changes to the Database"""

        try:
            for index, query in enumerate(sparql_up):
                response = self._neptune_client.update_query(query)
                if execution_log:
                    execution_log(f"Everythin ok. Response was: {response}", "GREEN")
                    execution_log(
                        f"If needed, here it goes the rollback query:\n{sparql_down[index]}",
                        "GREEN",
                    )
        except Exception as e:
            if execution_log:
                execution_log(f"Some error happened. Erro was: {e}")

    def get_current_version(self):
        """Get Virtuoso Database Graph Current Version"""

        query = """\
prefix owl: <http://www.w3.org/2002/07/owl#>
prefix xsd: <http://www.w3.org/2001/XMLSchema#>
select distinct ?version ?origen
FROM <%(m_graph)s>
{{
select distinct ?version ?origen ?data
where {?s owl:versionInfo ?version;
<%(m_graph)scommited> ?data;
<%(m_graph)sproduto> "%(v_graph)s";
<%(m_graph)sorigen> ?origen.}
ORDER BY desc(?data) LIMIT 1
}}""" % {
            "m_graph": self.migration_graph,
            "v_graph": self.__virtuoso_graph,
        }

        result = self._neptune_client.execute_query(query)

        if not result["results"]["bindings"]:
            return None, None

        return (
            str(result["results"]["bindings"][0]["version"]["value"]),
            str(result["results"]["bindings"][0]["origen"]["value"]),
        )

    def _generate_migration_sparql_commands(self, origin_store, destination_store):
        diff = (origin_store - destination_store) or []
        checked = set()
        forward_migration = []
        backward_migration = []

        for subject, predicate, object_ in diff:

            if isinstance(subject, rdflib.term.BNode) and (not subject in checked):
                checked.add(subject)

                query_get_blank_node = """\
                prefix owl: <http://www.w3.org/2002/07/owl#>
                prefix xsd: <http://www.w3.org/2001/XMLSchema#>
                SELECT DISTINCT ?s ?p ?o WHERE
                {"""

                blank_node_as_an_object = ""
                triples_with_blank_node_as_object = sorted(
                    diff.subject_predicates(subject)
                )
                for (
                    triple_subject,
                    triple_predicate,
                ) in triples_with_blank_node_as_object:
                    query_get_blank_node = query_get_blank_node + "%s %s ?s . " % (
                        triple_subject.n3(),
                        triple_predicate.n3(),
                    )
                    blank_node_as_an_object = blank_node_as_an_object + "%s %s " % (
                        triple_subject.n3(),
                        triple_predicate.n3(),
                    )

                blank_node_as_a_subject = ""
                triples_with_blank_node_as_subject = sorted(
                    diff.predicate_objects(subject)
                )
                for (
                    triple_predicate,
                    triple_object,
                ) in triples_with_blank_node_as_subject:
                    query_get_blank_node = query_get_blank_node + "?s %s %s . " % (
                        triple_predicate.n3(),
                        triple_object.n3(),
                    )
                    blank_node_as_a_subject = blank_node_as_a_subject + "%s %s ; " % (
                        triple_predicate.n3(),
                        Utils.get_normalized_n3(triple_object),
                    )

                query_get_blank_node = query_get_blank_node + " ?s ?p ?o .} "

                blank_node_existing_triples = len(
                    destination_store.query(query_get_blank_node)
                )
                blank_node_existed_triples = len(
                    origin_store.query(query_get_blank_node)
                )

                blank_node_triples_changed = (
                    blank_node_existing_triples != blank_node_existed_triples
                )

                if not blank_node_existing_triples or blank_node_triples_changed:
                    forward_migration.append(
                        "INSERT DATA { GRAPH <%s> { %s[%s] } };"
                        % (
                            self.__virtuoso_graph,
                            blank_node_as_an_object,
                            blank_node_as_a_subject,
                        )
                    )
                    blank_node_as_a_subject = blank_node_as_a_subject[:-2]

                    backward_migration.append(
                        "WITH <%s> DELETE { %s ?s. ?s %s } WHERE "
                        "{ %s ?s. ?s %s };"
                        % (
                            self.__virtuoso_graph,
                            blank_node_as_an_object,
                            blank_node_as_a_subject,
                            blank_node_as_an_object,
                            blank_node_as_a_subject,
                        )
                    )

            if isinstance(subject, rdflib.term.URIRef) and not isinstance(
                object_, rdflib.term.BNode
            ):
                forward_migration.append(
                    "INSERT DATA { GRAPH <%s> { %s %s %s . } };"
                    % (
                        self.__virtuoso_graph,
                        subject.n3(),
                        predicate.n3(),
                        object_.n3(),
                    )
                )
                backward_migration.append(
                    "WITH <%s> DELETE { %s %s %s . } WHERE { %s %s %s . }"
                    % (
                        self.__virtuoso_graph,
                        subject.n3(),
                        predicate.n3(),
                        Utils.get_normalized_n3(object_),
                        subject.n3(),
                        predicate.n3(),
                        Utils.get_normalized_n3(object_),
                    )
                )

        return forward_migration, backward_migration

    def get_sparql(
        self,
        current_ontology=None,
        destination_ontology=None,
        current_version=None,
        destination_version=None,
        origen=None,
        insert=None,
    ):
        """Make sparql statements to be executed"""
        query_up = []
        query_down = []
        if insert is None:

            current_graph = ConjunctiveGraph()
            destination_graph = ConjunctiveGraph()
            # if insert is None:
            try:
                if current_ontology is not None:
                    current_graph.parse(data=current_ontology, format="turtle")
                destination_graph.parse(data=destination_ontology, format="turtle")
            except BadSyntax as e:
                e._str = e._str.decode("utf-8")
                raise MigrationException("Error parsing graph %s" % str(e))

            forward_insert, backward_delete = self._generate_migration_sparql_commands(
                destination_graph, current_graph
            )
            backward_insert, forward_delete = self._generate_migration_sparql_commands(
                current_graph, destination_graph
            )
            query_up = forward_delete + forward_insert
            query_down = backward_delete + backward_insert
        # Registry schema changes on migration_graph
        now = datetime.datetime.now()
        values = {
            "m_graph": self.migration_graph,
            "v_graph": self.__virtuoso_graph,
            "c_version": current_version,
            "d_version": destination_version,
            "endpoint": self.__virtuoso_endpoint,
            "user": self.__virtuoso_user,
            "host": self.__virtuoso_host,
            "origen": origen,
            "date": str(now.strftime("%Y-%m-%d %H:%M:%S")),
            "insert": insert,
            "query_up": "\n".join(query_up).replace('"', '\\"').replace("\n", "\\n"),
            "query_down": "\n".join(query_down)
            .replace('"', '\\"')
            .replace("\n", "\\n"),
        }
        if insert is not None:
            query_up.append(
                (
                    "INSERT DATA { GRAPH <%(m_graph)s> { "
                    '[] owl:versionInfo "%(c_version)s"; '
                    '<%(m_graph)sendpoint> "%(endpoint)s"; '
                    '<%(m_graph)susuario> "%(user)s"; '
                    '<%(m_graph)sambiente> "%(host)s"; '
                    '<%(m_graph)sproduto> "%(v_graph)s"; '
                    '<%(m_graph)scommited> "%(date)s"^^xsd:dateTime; '
                    '<%(m_graph)sorigen> "%(origen)s"; '
                    '<%(m_graph)sinserted> "%(insert)s".} };'
                )
                % values
            )
            query_down.append(
                (
                    "WITH <%(m_graph)s> DELETE {?s ?p ?o} "
                    'WHERE {?s owl:versionInfo "%(c_version)s"; '
                    '<%(m_graph)sendpoint> "%(endpoint)s"; '
                    '<%(m_graph)susuario> "%(user)s"; '
                    '<%(m_graph)sambiente> "%(host)s"; '
                    '<%(m_graph)sproduto> "%(v_graph)s"; '
                    '<%(m_graph)scommited> "%(date)s"^^xsd:dateTime; '
                    '<%(m_graph)sorigen> "%(origen)s"; '
                    '<%(m_graph)sinserted> "%(insert)s"; ?p ?o.};'
                )
                % values
            )
        else:
            query_up.append(
                (
                    "INSERT DATA { GRAPH <%(m_graph)s> { "
                    '[] owl:versionInfo "%(d_version)s"; '
                    '<%(m_graph)sendpoint> "%(endpoint)s"; '
                    '<%(m_graph)susuario> "%(user)s"; '
                    '<%(m_graph)sambiente> "%(host)s"; '
                    '<%(m_graph)sproduto> "%(v_graph)s"; '
                    '<%(m_graph)scommited> "%(date)s"^^xsd:dateTime; '
                    '<%(m_graph)sorigen> "%(origen)s"; '
                    '<%(m_graph)schanges> "%(query_up)s".} };'
                )
                % values
            )
            query_down.append(
                (
                    "WITH <%(m_graph)s> DELETE {?s ?p ?o} "
                    'WHERE {?s owl:versionInfo "%(d_version)s"; '
                    '<%(m_graph)sendpoint> "%(endpoint)s"; '
                    '<%(m_graph)susuario> "%(user)s"; '
                    '<%(m_graph)sambiente> "%(host)s"; '
                    '<%(m_graph)sproduto> "%(v_graph)s"; '
                    '<%(m_graph)scommited> "%(date)s"^^xsd:dateTime; '
                    '<%(m_graph)sorigen> "%(origen)s"; '
                    '<%(m_graph)schanges> "%(query_up)s"; ?p ?o.};'
                )
                % values
            )
        query_up = list(filter(None, query_up))
        query_down = list(filter(None, query_down))

        return query_up, query_down

    def get_ontology_by_version(self, version):
        file_name = self._migrations_dir + "/" + self.__virtuoso_ontology
        if not os.path.exists(file_name):
            raise Exception("migration file does not exist (%s)" % file_name)
        return Git(self._migrations_dir).execute(
            ["git", "show", version + ":" + self.__virtuoso_ontology]
        )

    def get_ontology_from_file(self, filename):
        if not os.path.exists(filename):
            raise Exception("migration file does not exist (%s)" % filename)
        f = open(filename, "rU")
        content = f.read()
        f.close()
        return content
