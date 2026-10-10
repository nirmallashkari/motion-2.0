"""Meaningful regression cases for the publication guard."""
from pathlib import Path
import unittest
from check_public_tree import findings

class PublicTreeTests(unittest.TestCase):
    def test_runtime_and_personal_media_are_rejected(self):
        for path in ('_SYSTEM/secrets/backup.dpapi', '_SYSTEM/work/frame.png',
                     'INPUT/story.txt', 'OUTPUT/final.mp4', '.env.production'):
            self.assertTrue(findings(Path(path), b'not a credential'), path)

    def test_realistic_credential_pattern_rejected_without_value_in_message(self):
        value = b'sk' + b'-' + b'Q' * 32
        result = findings(Path('settings.json'), value)
        self.assertIn('possible credential content', result)
        self.assertNotIn(value.decode(), str(result))

    def test_source_and_licensed_assets_are_allowed(self):
        for path in ('README.md', '_SYSTEM/assets/github/animated/brain.png', 'INPUT/README.txt'):
            self.assertEqual(findings(Path(path), b'public content'), [], path)

if __name__ == '__main__':
    unittest.main()
