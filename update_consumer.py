from thoth.python import AIOSource
from thoth.python import Source
from thoth.common import init_logging
from process_message import process_mismatch, process_missing_package, process_missing_version

from prometheus_client import start_http_server, Counter

import asyncio
import logging
import faust
import os
import ssl
from urllib.parse import urlparse

from messages.missing_package import MissingPackageMessage
from messages.missing_version import MissingVersionMessage
from messages.hash_mismatch import HashMismatchMessage
from messages.message_base import MessageBase

"""Consume messages produced by package-update.py faust app."""

init_logging()

_LOGGER = logging.getLogger("thoth.package_update")

app = MessageBase.app
KAFKA_TOPIC_RETENTION_TIME_SECONDS = 60 * 60 * 24 * 45

start_http_server(8000)
# TODO: query prometheus scraper and get or create values for all metrics for now we will set them all to 0
# NOTE: these counters are temp metrics as they are already exposed by Kafka
hash_mismatch_counter = Counter(
    "thoth_package_update_hashmismatch_total",
    "Total number of hashmismatches found.",
)
missing_package_counter = Counter(
    "thoth_package_update_missingpackage_total",
    "Total number of hashmismatches found.",
)

missing_package_version_counter = Counter(
    "thoth_package_update_missingversion_total",
    "Total number of hashmismatches found.",
)

hash_mismatch_topic = app.topic(
    HashMismatchMessage.topic_name,
    value_type=HashMismatchMessage.MessageContents,
    retention=KAFKA_TOPIC_RETENTION_TIME_SECONDS,
    partitions=1,
    internal=True,
)

missing_package_topic = app.topic(
    MissingPackageMessage.topic_name,
    value_type=MissingPackageMessage.MessageContents,
    retention=KAFKA_TOPIC_RETENTION_TIME_SECONDS,
    partitions=1,
    internal=True,
)

missing_version_topic = app.topic(
    MissingVersionMessage.topic_name,
    value_type=MissingVersionMessage.MessageContents,
    retention=KAFKA_TOPIC_RETENTION_TIME_SECONDS,
    partitions=1,
    internal=True,
)

# TODO: for storages we need the following functions:
#       update_hash_mismatch(index_url, package_name, package_version, new_hash) unless this is done by solver


@app.agent(hash_mismatch_topic)
async def consume_hash_mismatch(hash_mismatches):
    """Dump the messages received."""
    async for mismatch in hash_mismatches:
        # TODO: update the hashes in the database? or is this done by solver
        hash_mismatch_counter.inc()

        # NOTE: This may work better as an argo work flow which looks something like:
        #   A B C
        #    ╲|╱
        #     D
        # Where A, B, C are all solvers and D is a container which warns all users of change
        process_mismatch(mismatch)


@app.agent(missing_package_topic)
async def consume_missing_package(missing_packages):
    """Dump the messages received."""
    async for package in missing_packages:
        missing_package_counter.inc()
        # TODO: determine how to mark an entire package as missing in the database

        # TODO: open issue if package is a direct dependency of the user, otherwise rerun thamos-advise/kebechet
        process_missing_package(package)


@app.agent(missing_version_topic)
async def consume_missing_version(missing_versions):
    """Dump the messages received."""
    async for version in missing_versions:
        missing_package_version_counter.inc()
        process_missing_version(version)

if __name__ == "__main__":
    start_http_server(8000)
    app.main()
