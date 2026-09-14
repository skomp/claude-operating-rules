import unittest
from machines.declaration import extract_block
from machines.errors import DeclarationError

ONE = "intro\n\n```machine\nmachine: x\n```\n\ntrailing prose\n"
NONE = "intro only, no block\n"
TWO = "```machine\na: 1\n```\ntext\n```machine\nb: 2\n```\n"
OTHER_FENCE = "```yaml\nmachine: x\n```\n"

class TestExtractBlock(unittest.TestCase):
    def test_returns_block_contents_without_the_fences(self):
        self.assertEqual(extract_block(ONE), "machine: x\n")

    def test_no_block_raises(self):
        with self.assertRaises(DeclarationError):
            extract_block(NONE)

    def test_two_blocks_raises(self):
        with self.assertRaises(DeclarationError):
            extract_block(TWO)

    def test_a_yaml_fence_is_not_a_machine_fence(self):
        with self.assertRaises(DeclarationError):
            extract_block(OTHER_FENCE)

if __name__ == "__main__":
    unittest.main()
