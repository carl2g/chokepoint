import csv
from pathlib import Path

from django.core.management.base import BaseCommand

from companies.models import ExternalSegmentType


class Command(BaseCommand):
    help = "Load SEC SIC-to-Exiobase mappings from a CSV into ExternalSegmentType rows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv-path",
            type=str,
            default=str(Path("companies/datasets/sec/sic_to_exiobase.csv")),
            help="Path to the SEC mapping CSV file.",
        )

    def handle(self, *args, **options):
        project_root = Path(__file__).resolve().parents[3]
        csv_path = Path(options["csv_path"])
        if not csv_path.is_absolute():
            csv_path = project_root / csv_path

        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        created_count = 0
        with csv_path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                sic_code = row.get("SIC Code").strip()
                exiobase_mapping = row.get("Exiobase mapping").strip()
                industry_title = row.get("Industry Title").strip()

                if not sic_code:
                    continue

                defaults = {
                    "original_name": industry_title,
                    "description": None,
                    "exiobase_segment_name": exiobase_mapping or None,
                    "mapping_type": ExternalSegmentType.MAPPING_TYPE_AI,
                    "validated": False,
                    "skipped": False,
                }

                _, created = ExternalSegmentType.objects.update_or_create(
                    source=ExternalSegmentType.SOURCE_SEC_SIC,
                    external_id=sic_code,
                    defaults=defaults,
                )
                if created:
                    created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {created_count} new SEC external segment mappings from {csv_path}."
            )
        )
