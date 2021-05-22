from typing import NamedTuple


class MemcmpOpts(NamedTuple):
    """Option to compare a provided series of bytes with program account data at a particular offset."""

    offset: int
    """Offset into program account data to start comparison: <usize>."""
    bytes: str
    """Data to match, as base-58 encoded string: <string>."""