import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from companies.models import ExternalSegmentType


class ImportExternalSegmentTypesCommandTests(TestCase):
    def test_imports_csv_rows_as_external_segment_types(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="") as handle:
            handle.write("SIC Code,Exiobase mapping,Industry Title\n")
            handle.write("123,Test mapping,Test industry\n")
            csv_path = Path(handle.name)

        call_command(
            "load_sec_external_segment_types",
            csv_path=str(csv_path),
            stdout=StringIO(),
            stderr=StringIO(),
        )

        mapping = ExternalSegmentType.objects.get(source="sec", external_id="123")
        self.assertEqual(mapping.original_name, "Test industry")
        self.assertEqual(mapping.exiobase_segment_name, "Test mapping")
        self.assertEqual(mapping.mapping_type, ExternalSegmentType.MAPPING_TYPE_AI)
        self.assertFalse(mapping.validated)
        self.assertFalse(mapping.skipped)
