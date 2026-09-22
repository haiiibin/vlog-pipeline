# Security Policy

## Supported versions

There are no tagged releases yet; the `main` branch receives fixes.

## Reporting a vulnerability

Please do not open a public issue for security problems. Report them privately
via [GitHub private vulnerability reporting](https://github.com/haiiibin/vlog-pipeline/security/advisories/new)
or email haibiny123@gmail.com. You can expect an initial response within a few
days.

## Scope notes

The pipeline runs locally on clips in a folder you point it at, writes under
`data/`, and serves a web UI on localhost. It calls the Anthropic API only when
`ANTHROPIC_API_KEY` is set and the default cut-list composer is used. Reports
about the web UI being reachable from outside the local machine, or about path
handling that could read or write outside `data/`, are particularly welcome.
