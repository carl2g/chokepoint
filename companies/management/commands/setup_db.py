from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand

from companies.models import Company, SectorialRevenue, Sector
from companies.services.sec.company_builder import CompanyBuilder

from companies.services.sec.sector_builder import SecSectorBuilder


class Command(BaseCommand):
    help = "Reset the database, recreate migrations, and seed companies and sectors using the existing builders."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-db",
            action="store_true",
            help="Delete db.sqlite3 and the existing companies migrations before rebuilding the schema.",
        )

    def handle(self, *args, **options):
        project_root = Path(__file__).resolve().parents[3]
        db_path = project_root / "db.sqlite3"
        migrations_dir = project_root / "companies" / "migrations"

        if options["reset_db"]:
            if db_path.exists():
                db_path.unlink()

            for migration_file in migrations_dir.glob("*.py"):
                if migration_file.name == "__init__.py":
                    continue
                migration_file.unlink()

            call_command("makemigrations", "companies", "--noinput")
            call_command("migrate", "--noinput", "--run-syncdb")

            self.stdout.write(
                self.style.SUCCESS("Database reset and migrations recreated.")
            )

        Company.objects.all().delete()
        SectorialRevenue.objects.all().delete()
        Sector.objects.all().delete()

        call_command(
            "load_sec_external_segment_types",
            csv_path=str(Path("companies/datasets/sec/sic_to_exiobase.csv")),
        )

        CompanyBuilder.create_companies()

        companies = list(Company.objects.all())
        CompanyBuilder.update_companies_info(companies)

        self.stdout.write(self.style.SUCCESS(f"Seeded {len(companies)} companies"))
