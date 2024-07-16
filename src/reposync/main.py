#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import logging
import os
import sys
from operator import attrgetter
from pathlib import Path

import git
from github import Github
from more_itertools import unique_everseen

from reposync import __version__

__author__ = "Robin Bowes"
__copyright__ = "Robin Bowes"
__license__ = "mit"

_logger = logging.getLogger(__name__)


class AppendQueryTermAction(argparse.Action):
    """A custom action to help with creating github queries

    Use like this:

    parser.add_argument(
        '--name',
        dest='query_terms',
        action=AppendQueryTermAction,
        term_format='{value} in:name'
        )

    The "term_format" parmeter is a format string, into which the variable
    "value" will be substituted.
    """

    def _copy_items(self, items):
        """
        Taken from:
            https://github.com/python/cpython/blob/3.7/Lib/argparse.py#L136-L145
        """
        if items is None:
            return []
        # The copy module is used only in the 'append' and 'append_const'
        # actions, and it is needed only when the default value isn't a list.
        # Delay its import for speeding up the common case.
        if type(items) is list:
            return items[:]
        import copy

        return copy.copy(items)

    def __init__(self, option_strings, term_format, *args, **kwargs):
        self._term_format = term_format
        super(AppendQueryTermAction, self).__init__(
            option_strings=option_strings, *args, **kwargs
        )

    def __call__(self, parser, namespace, values, option_string=None):
        if type(values) is list:
            new_values = [self._term_format.format(value=value) for value in values]
        else:
            new_values = self._term_format.format(value=values)
        items = getattr(namespace, self.dest, None)
        items = self._copy_items(items)
        items.append(new_values)
        setattr(namespace, self.dest, items)


def read_token(token_file):
    """Read github auth token from token_file"""
    with open(token_file, "r") as f:
        return f.read().chomp()


def parse_args(args):
    """Parse command line parameters

    Args:
      args ([str]): command line parameters as list of strings

    Returns:
      :obj:`argparse.Namespace`: command line parameters namespace
    """
    parser = argparse.ArgumentParser(
        description="Synchronise github repositories locally"
    )
    parser.add_argument(
        "--version", action="version", version="reposync {ver}".format(ver=__version__)
    )
    parser.add_argument(
        "--org",
        help="github organisation",
        type=str,
        metavar="ORG",
        dest="query_terms",
        action=AppendQueryTermAction,
        term_format="org:{value}",
    )
    parser.add_argument(
        "--name",
        help="String to match against repository name",
        type=str,
        metavar="NAME",
        dest="query_terms",
        action=AppendQueryTermAction,
        term_format="{value} in:name",
    )
    parser.add_argument(
        "--archived",
        help="Search only archived repositories (excluded by default)",
        action="store_true",
    )
    parser.add_argument("--dry-run", help="Search but do not sync", action="store_true")
    parser.add_argument(
        "--fork", help="Include forks (excluded by default)", action="store_true"
    )
    parser.add_argument(
        "--update",
        help="Update any repos that are already cloned (no update by default)",
        action="store_true",
    )
    parser.add_argument(
        "--or",
        help="insert an OR",
        dest="query_terms",
        action="append_const",
        const="OR",
    )
    parser.add_argument(
        "--not",
        help="insert a NOT",
        dest="query_terms",
        action="append_const",
        const="NOT",
    )
    parser.add_argument(
        "--sort",
        help="Sort the list of matched repositories before processing",
        action="store_true",
    )
    parser.add_argument("--token", help="github auth token", type=str, metavar="TOKEN")
    parser.add_argument(
        "--token-file",
        help="Location of file from which to read github auth token",
        type=argparse.FileType("r"),
        dest="token_file",
        metavar="FILE",
        default=os.path.expanduser("~/.github_token"),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="loglevel",
        help="set loglevel to INFO",
        action="store_const",
        const=logging.INFO,
    )
    parser.add_argument(
        "-vv",
        "--very-verbose",
        dest="loglevel",
        help="set loglevel to DEBUG",
        action="store_const",
        const=logging.DEBUG,
    )
    new_args = parser.parse_args(args)

    if new_args.query_terms is None:
        print("Error: At least one query term must be supplied", file=sys.stderr)
        parser.print_usage(file=sys.stderr)
        sys.exit(1)

    if new_args.archived:
        new_args.query_terms.append("archived:true")
    else:
        new_args.query_terms.append("archived:false")

    if new_args.fork:
        new_args.query_terms.append("fork:true")
    else:
        new_args.query_terms.append("fork:false")

    if new_args.token is None:
        new_args.token = new_args.token_file.read().rstrip()

    return new_args


def setup_logging(loglevel):
    """Setup basic logging

    Args:
      loglevel (int): minimum loglevel for emitting messages
    """
    logformat = "[%(asctime)s] %(levelname)s:%(name)s:%(message)s"
    logging.basicConfig(
        level=loglevel, stream=sys.stdout, format=logformat, datefmt="%Y-%m-%d %H:%M:%S"
    )


def login_to_github(token):
    """Login to github

    Args:
      token (str): Github auth token
    """
    ghc = Github(token)
    return ghc


def main(args):
    """Main entry point allowing external calls

    Args:
      args ([str]): command line parameter list
    """
    args = parse_args(args)
    setup_logging(args.loglevel)
    ghc = login_to_github(args.token)
    _logger.info("Logged into github")

    query_expression = " ".join(args.query_terms)
    _logger.info("Query expression: " + query_expression)

    repos = list(ghc.search_repositories(query_expression))
    _logger.info("Repos found: " + ", ".join(repo.name for repo in repos))

    if args.sort:
        repos.sort(key=lambda x: x.name)

    # Loop over all search results, eliminating duplicates
    for repo in unique_everseen(repos, key=attrgetter("full_name")):
        full_name = repo.full_name
        if args.dry_run:
            print("Found repo: {name}".format(name=full_name))
        else:
            print("Processing repo: {name}".format(name=full_name))
            p = Path(full_name)
            default_branch = repo.default_branch
            if p.is_dir():
                if args.update:
                    _logger.info("Working dir exists, updating")
                    repo = git.Repo(full_name)
                    _logger.info(f"Checking out default branch ({default_branch})")
                    repo.heads[default_branch].checkout()
                    _logger.info("Pulling...")
                    repo.remotes.origin.pull()
                else:
                    _logger.info("Working dir exists, skipping")
            else:
                _logger.debug("Working dir not found, cloning")
                # use https URL, by default
                # To-do: add option to specify ssh or https URL
                url = repo.clone_url
                git.Repo.clone_from(url, repo.full_name, branch=default_branch)

            _logger.debug("Done")


def run():
    """Entry point for console_scripts"""
    main(sys.argv[1:])


if __name__ == "__main__":
    run()
