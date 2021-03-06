import sys
from getpass import getpass

import neptune_migrate

from .cli import CLI
from .config import Config, FileConfig
from .main import Main


def run_from_argv(args=sys.argv[1:]):
    if not args:
        args = ["-h"]
    (options, _) = CLI.parse(args)
    run(options.__dict__)


def run(options):
    """Initial Module. Treat Parameters and call Main Module for execution"""
    try:
        if options.get("simple_virtuoso_migrate_version"):
            msg = "simple-virtuoso-migrate v%s" % neptune_migrate.__version__
            CLI.info_and_exit(msg)

        if options.get("show_colors"):
            CLI.show_colors()

        # Create config
        if options.get("config_file"):
            config = FileConfig(options.get("config_file"), options.get("environment"))
        else:
            config = Config()

        config.update("schema_version", options.get("schema_version"))
        config.update("show_sparql", options.get("show_sparql"))
        config.update("show_sparql_only", options.get("show_sparql_only"))
        config.update("file_migration", options.get("file_migration"))
        config.update("migration_graph", options.get("migration_graph"))
        config.update("load_ttl", options.get("load_ttl"))
        config.update("log_dir", options.get("log_dir"))
        config.update("database_user", options.get("database_user"))
        config.update("database_password", options.get("database_password"))
        config.update("host_user", options.get("host_user"))
        config.update("host_password", options.get("host_password"))
        config.update("virtuoso_dirs_allowed", options.get("virtuoso_dirs_allowed"))
        config.update("database_host", options.get("database_host"))
        config.update("database_port", options.get("database_port"))
        config.update("database_endpoint", options.get("database_endpoint"))
        config.update("database_graph", options.get("database_graph"))
        config.update("database_ontology", options.get("database_ontology"))
        if options.get("database_migrations_dir"):
            config.update(
                "database_migrations_dir",
                Config._parse_migrations_dir(options.get("database_migrations_dir")),
            )

        config.update(
            "database_migrations_dir", config.get("database_migrations_dir")[0]
        )
        config.update("log_level", int(options.get("log_level")))

        if options.get("run_after"):
            config.update("run_after", options.get("run_after"))

        # Ask the password for user if configured
        if config.get("database_password") == "<<ask_me>>":
            CLI.msg(
                "\nPlease inform password to connect to "
                'virtuoso (DATABASE) "%s@%s:%s"'
                % (
                    config.get("database_user"),
                    config.get("database_host"),
                    config.get("database_endpoint"),
                )
            )
            passwd = getpass()
            config.update("database_password", passwd)

        is_local = config.get("database_host", "").lower() in ["localhost", "127.0.0.1"]
        if (
            config.get("load_ttl", None)
            and config.get("virtuoso_dirs_allowed", None) is None
            and not is_local
        ):
            if config.get("host_password") == "<<ask_me>>":
                CLI.msg(
                    "\nPlease inform password to connect to "
                    'virtuoso (HOST) "%s@%s"'
                    % (config.get("host_user"), config.get("database_host"))
                )
                passwd = getpass()
                config.update("host_password", passwd)
        # If CLI was correctly parsed, execute db-virtuoso.
        Main(config).execute()
    except KeyboardInterrupt:
        CLI.info_and_exit("\nExecution interrupted by user...")
    except Exception as e:
        CLI.error_and_exit(str(e))


if __name__ == "__main__":
    "Begin of execution"

    run_from_argv()
