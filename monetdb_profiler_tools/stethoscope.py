# This Source Code Form is subject to the terms of the Mozilla
# Public License, v. 2.0. If a copy of the MPL was not
# distributed with this file, You can obtain one at
# https://mozilla.org/MPL/2.0/.

"""This is the implementation of stethoscope, a tool to interact with MonetDB
profiler streams."""

import logging
import sys
import click
import pymonetdb
from monetdb_profiler_tools.filtering import include_filter, exclude_filter
from monetdb_profiler_tools.filtering import identity_filter
from monetdb_profiler_tools.formatting import line_formatter, raw_formatter
from monetdb_profiler_tools.formatting import json_formatter
from monetdb_profiler_tools.parsing import json_parser, identity_parser
from monetdb_profiler_tools.transformers import statement_transformer, identity_transformer
from monetdb_profiler_tools.transformers import dummy_transformer

LOGGER = logging.getLogger(__name__)


@click.command()
@click.argument("database")
@click.option("--include-keys", "-i", "include",
              help="A comma separated list of keys. Filter out all other keys.")
@click.option("--exclude-keys", "-e", "exclude",
              help="A comma separated list of keys to exclude")
@click.option("--raw", "-r", "raw", is_flag=True,
              help='Copy what the server sends to the output. Incompatible with other options.')
@click.option("--formatter", "-f", "fmt", multiple=True, help='json or line')
@click.option("--transformer", "-t", "trn", multiple=True, help='stmt')
@click.option("--output", "-o", "outfile", default="stdout", help='Output stream')
def stethoscope(database, include, exclude, fmt, trn, raw, outfile):
    """A flexible tool to manipulate MonetDB profiler streams"""

    logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)

    LOGGER.debug("Input arguments")
    LOGGER.debug("  Database: %s", database)
    LOGGER.debug("  Transformer: %s", trn)
    LOGGER.debug("  Include keys: %s", include)
    LOGGER.debug("  Exclude keys: %s", exclude)
    LOGGER.debug("  Formatter: %s", fmt)
    LOGGER.debug("  Raw: %s", raw)
    LOGGER.debug("  Output file: %s", outfile)

    cnx = pymonetdb.ProfilerConnection()
    cnx.connect(database, username='monetdb', password='monetdb', heartbeat=0)

    if not raw:
        parse_operator = json_parser()
    else:
        parse_operator = identity_parser()

    transformers = list()
    for t in trn:
        if t == 'statement':
            transformers.append(statement_transformer())
        elif t == 'dummy':
            transformers.append(dummy_transformer())
        else:
            transformers.append(identity_transformer())

    LOGGER.debug("transformers len = %d", len(transformers))

    if include:
        filter_operator = include_filter(include.split(','))
    elif exclude:
        filter_operator = exclude_filter(exclude.split(','))
    else:
        filter_operator = identity_filter()

    if fmt == "json":
        formatter = json_formatter
    elif fmt == "line":
        formatter = line_formatter
    else:
        formatter = raw_formatter

    if raw:
        if include:
            LOGGER.warning("Ignoring include keys because --raw was specified")
        if exclude:
            LOGGER.warning("Ignoring exclude keys because --raw was specified")
        if fmt and fmt != "json":
            LOGGER.warning("Ignoring formatter %s because --raw was specified", fmt)

        formatter = raw_formatter

    out_file = sys.stdout
    if outfile != "stdout":
        out_file = open(outfile, "w")

    while True:
        try:
            # read
            s = cnx.read_object()
            # parse
            json_object = parse_operator(s)
            # transform
            for t in transformers:
                json_object = t(json_object)
            json_object = filter_operator(json_object)
            # filter
            # format
            formatter(json_object, out_file)
        except Exception as e:
            LOGGER.warn("Failed operating on %s (%s)", s, e)
