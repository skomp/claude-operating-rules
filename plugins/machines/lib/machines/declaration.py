import re
from .errors import DeclarationError

_FENCE = re.compile(r"^```machine[ \t]*\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)

def extract_block(text):
    blocks = _FENCE.findall(text)
    if not blocks:
        raise DeclarationError("no ```machine block found")
    if len(blocks) > 1:
        raise DeclarationError(
            "found %d ```machine blocks; a bundle declares exactly one" % len(blocks)
        )
    return blocks[0]
