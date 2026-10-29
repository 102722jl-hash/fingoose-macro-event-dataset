from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


class EvidenceExcerptTests(unittest.TestCase):
    def test_html_excerpt_uses_the_configured_locator_anchor(self):
        from fingoose_macro_event_audit_v1 import extract_source_excerpt

        root = Path(__file__).resolve().parents[1] / '.test-tmp' / 'evidence-excerpt'
        root.mkdir(parents=True, exist_ok=True)
        (root / 'official.html').write_text(
            '<html><body><p>Before context.</p><p>Official event statement is here.</p><p>After context.</p></body></html>',
            encoding='utf-8',
        )
        excerpt = extract_source_excerpt(
            {
                'local_snapshot_path': 'official.html',
                'locator': {'type': 'html_text', 'value': 'Official event statement'},
                'summary': 'Fallback only.',
            },
            root=root,
        )

        self.assertEqual(excerpt['excerpt'], 'Official event statement is here.')
        self.assertEqual(excerpt['excerpt_origin'], 'snapshot_html_locator')

    def test_page_locator_is_not_presented_as_a_verbatim_quote_without_extraction(self):
        from fingoose_macro_event_audit_v1 import extract_source_excerpt

        excerpt = extract_source_excerpt(
            {
                'local_snapshot_path': 'missing.pdf',
                'locator': {'type': 'pdf_page', 'value': '1-2'},
                'summary': 'Official report summary.',
            },
            root=Path('.'),
        )

        self.assertEqual(excerpt['excerpt'], 'Official report summary.')
        self.assertEqual(excerpt['excerpt_origin'], 'source_summary_fallback')


if __name__ == '__main__':
    unittest.main()
