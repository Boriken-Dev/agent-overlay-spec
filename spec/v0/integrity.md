# Integrity

**Optional Extension, Proposed.** Digests let a consumer check that the bytes it uses are the bytes
it was given.

## Digest form

A digest is written `sha256:` followed by 64 hexadecimal digits: the SHA-256 of the input, as
lowercase hexadecimal when written. A reader compares the hexadecimal digits without regard to case,
and MUST refuse a digest with another prefix or length. `sha256` is the only algorithm this edition
defines.
