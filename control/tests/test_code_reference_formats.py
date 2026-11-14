import unittest
from agents import code_refs

class ReferenceFormatTests(unittest.TestCase):
 def test_colon_and_chinese_line_formats(self):
  refs=code_refs.collect('script.js:4；script.js 第29行；script.js` 第 62 行；script.js 第140至145行',{'script.js':'\n'.join(['x']*168)})
  self.assertEqual([(r['start'],r['end']) for r in refs],[(4,4),(29,29),(62,62),(140,145)])
  self.assertTrue(all(r['valid'] for r in refs))
 def test_filename_has_no_fabricated_line(self):
  self.assertEqual(code_refs.collect('打开 script.js',{'script.js':'x'}),[])
  self.assertFalse(code_refs.collect('script.js 第99行',{'script.js':'x'})[0]['valid'])
