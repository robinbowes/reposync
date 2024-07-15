# reposync

Synchronise github repos locally


## Description

reposync helps to clone and keep updated github repos.


## Usage

To access private repos, you will need an Oauth token. Visit https://github.com/settings/tokens to create one, and put it in ~/.github-token.

To get a list of repositories in YOUR_ORG_NAME matching PATTERN:

    reposync --name PATTERN --org YOUR_ORG_NAME

You may use --name multiple times:

    reposync --name PATTERN_1 --or --name PATTERN_2 --org YOUR_ORG_NAME

Note the use of --or.

Terms are used in the order specified on the commands line.

The syntax rules are the same as those used on github.
