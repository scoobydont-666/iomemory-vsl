# Binary inputs, licensing, and provenance

## What is pinned

[`binary-artifacts.json`](../binary-artifacts.json) records the SHA-256, size,
ELF architecture/class/type, and assurance limits of all nine committed libkfio
object variants and `root/usr/lib/fio/libvsl.so` at review baseline
`13145f4abf6caa575c1dcb149925bef7a90e7f1f`. The `latest` core object is byte-identical
to the `cc63` variant. No opaque object is modified by the modernization changes.

Run `python3 tools/verify_binary_artifacts.py` before building. CI rejects changed,
missing, additional, wrongly identified, or symlinked inputs in these inventory
locations. A legitimate binary update must include a reviewed manifest update,
its source archive/provenance, transformation evidence, and renewed qualification.
Changing a hash in the manifest is not independent authentication.

This is a binary-input inventory, not a complete firmware/dependency SBOM. The
cross-platform NOTICE lists do not establish which components are linked into
each Linux binary. Compiler version strings, symbols, and strings are useful
clues but are insufficient to assign dependency versions or CVEs reliably.

## Source and license boundaries

The maintainer reports an updated/customized local driver and firmware copy with
additional source/licensing context. That copy and its release documents are
pending comparison. The statements here describe the reviewed GitHub snapshot
only and must be updated when those materials are available. Company status
alone is not the evidence used to classify these files.

The adapter sources carry their existing file-level notices. The kfio README
describes the core objects as proprietary; the RPM metadata also records
Proprietary. Preserve all original notices and archives.

The existing `MODULE_LICENSE("GPL")` compatibility metadata is retained in this
repair. It does not relicense the opaque core, prove redistribution permission,
or establish that the linked driver has been fully source-audited. The former
`fake_license` source rewrite is removed. A mechanical switch to a different
module tag would also change kernel symbol-access/taint behavior; it cannot
settle the underlying licensing question.

Before distributing a new release, the maintainer must establish the rights and
required notices for the exact shipped inputs and resolve the module-metadata
policy. No original-vendor signature or complete chain of custody was verified
by this review. These are unresolved release-assurance conditions, not claims
of infringement, malicious code, or a specific vulnerability.

## Build transformations and validation

Record the selected input object hash, compiler, kernel release/configuration,
generated capability header, objtool command/diagnostics, resulting module hash,
vermagic, version, license metadata, and signer. Keep any renaming or binary
transformation recipe with that evidence. Unreviewed mutation of shipped objects
must fail the input check.

The narrow objtool exception is a documented limitation of validation over the
opaque core. First-party objects must still undergo the full relevant kernel
validation. Unknown diagnostics, missing tools, and failed transformations must
stop every supported build route.

## Runtime boundaries

The core implements material hardware, firmware, control-channel, and persistence
behavior. Adapter fixes cannot establish complete ioctl authorization or device
lifetime safety inside it. Validate native/compat control commands, expected
node permissions, removal concurrency, card/firmware compatibility, and
persistence on an isolated host before accepting a platform.

Record residual binary-core risk explicitly in the release decision. Preserve a
known-good kernel/module and a tested recovery procedure. A passing checksum
manifest establishes byte identity only.

Primary references:

- [Kernel license metadata](https://docs.kernel.org/process/license-rules.html)
- [Kernel module signing](https://docs.kernel.org/admin-guide/module-signing.html)
- [Original binary explanation](../root/usr/src/iomemory-vsl-3.2.16/kfio/README.md)
