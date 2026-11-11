# Security reporting and supported scope

The reviewed GitHub snapshot contains a legacy storage driver with an opaque
core. The [supplied local comparison](docs/local-reconciliation-2026-11-11.md)
has been reconciled; residual core/source and artifact identity limits remain.
Development changes and successful builds do not constitute hardware
qualification. Use the exact revisions and platform evidence recorded in
[qualification](docs/qualification.md).

## Reporting a vulnerability

Use GitHub's **Report a vulnerability** action in this repository's Security tab
when private vulnerability reporting is enabled. If it is unavailable, contact
the repository owner through their published contact channel to arrange private
disclosure before sharing exploit details or sensitive diagnostic data. Do not
put credentials, memory dumps, customer data, or device identifiers in public
issues or pull requests.

Include the source revision, kernel and configuration, affected interface,
required permissions, a minimal safe reproduction, and the observed impact.
Distinguish source/fixture evidence from an actual device/kernel result. Do not
run destructive or persistence experiments on production storage to complete a
report. Sanitized reports and fixes can be published after coordinated triage.

The maintainer must enable and monitor a concrete private reporting route;
this file alone does not enable a GitHub feature or guarantee a response SLA.

## Maintainer controls before release

Repository settings cannot be enforced by this source PR. The repository owner
must configure a main-branch ruleset requiring pull requests, the actual current
CI check names, independent review, and protection against force pushes/deletion.
Require checks on the final candidate and current base, including all supported
build/package paths. Enable private vulnerability reporting and keep ordinary
support links consistent with enabled Issues/Discussions features.

Public pull-request code runs only on ephemeral hosted CI. Hardware tests use
reviewed immutable artifacts on a separately controlled isolated lab host; never
give arbitrary public PR code access to persistent storage hosts or signing keys.
Release signing credentials remain outside untrusted PR execution.

See [binary assurance](docs/binary-assurance.md) for licensing/provenance limits
and [the remediation record](docs/security-modernization-2026-11-11.md) for
finding-level status and remaining qualification work.
