import unittest
import os
import shutil
import tempfile
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

from utils.storage import generate_html_file_path, save_raw_html, read_raw_html

class TestStorage(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_generate_html_file_path(self):
        url = "https://www.example.com/contact?q=test"
        path = generate_html_file_path(url, result_id=12345, base_dir=self.test_dir)
        
        self.assertTrue(path.startswith(self.test_dir))
        self.assertTrue(path.endswith("_12345.html.gz"))
        self.assertIn("www.example.com", path)
        
        # Check subdirectories structure: [base_dir]/[subdir1]/[subdir2]/[filename]
        parts = os.path.normpath(path).split(os.sep)
        self.assertGreaterEqual(len(parts), 4)

    def test_save_and_read_raw_html(self):
        url = "http://testdomain.cz/o-nas"
        html_content = "<html><body><h1>Test Page</h1></body></html>"

        rel_path, size = save_raw_html(url, html_content, result_id=67890, base_dir=self.test_dir)
        self.assertEqual(size, len(html_content.encode('utf-8')))
        self.assertTrue(os.path.exists(os.path.abspath(rel_path)))
        self.assertTrue(rel_path.endswith("_67890.html.gz"))

        # Read back using path string
        content_read = read_raw_html(rel_path)
        self.assertEqual(content_read, html_content)

        # Read back using dict item
        item = {"html_path": rel_path, "html": None}
        content_from_item = read_raw_html(item)
        self.assertEqual(content_from_item, html_content)

    def test_fallback_to_db_html(self):
        item = {"html_path": None, "html": "<html>DB HTML</html>"}
        content = read_raw_html(item)
        self.assertEqual(content, "<html>DB HTML</html>")

if __name__ == '__main__':
    unittest.main()
