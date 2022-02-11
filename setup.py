from setuptools import find_packages, setup

import neptune_migrate

setup(
    name="neptune-migrate",
    version=neptune_migrate.SIMPLE_VIRTUOSO_MIGRATE_VERSION,
    packages=find_packages(exclude=("tests",)),
    author="Percy Rivera",
    author_email="priverasalas@gmail.com",
    description="simple-virtuoso-migrate is a Virtuoso database migration tool inspired on simple-db-migrate.",
    license="Apache License 2.0",
    keywords="database migration tool virtuoso",
    url="http://github.com/globocom/simple-virtuoso-migrate/",
    long_description="simple-virtuoso-migrate is a Virtuoso database migration tool inspired on simple-db-migrate. This tool helps you easily refactor and manage your ontology T-BOX. The main difference is that simple-db-migrate are intended to be used for mysql, ms-sql and oracle projects while simple-virtuoso-migrate makes it possible to have migrations for Virtuoso",
    tests_require=[
        "coverage==3.7",
        "mock==1.0.1",
    ],
    install_requires=[
        "cryptography==3.3",
        "GitPython==3.1.20",
        "paramiko==2.4.3",
        "rdflib==6.0.0",
        # pyparsing is here because of this: https://github.com/RDFLib/rdflib/pull/1366
        "pyparsing==2.*",
        "rdfextras==0.4",
        "gitdb==4.0.9",
        "aws-requests-auth==0.4.3",
        "requests==2.26.0",
    ],
    # generate script automatically
    entry_points={
        "console_scripts": [
            "neptune-migrate = neptune_migrate.run:run_from_argv",
        ],
    },
)
