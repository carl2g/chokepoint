from django.core.management.base import BaseCommand, CommandError

from companies.models import Company
from companies.services.sec.company_builder import CompanyBuilder
from companies.services.sec.sector_builder import SecSectorBuilder
from fund_analyzer.services.analysis_renderer import DependenceViz
from fund_analyzer.services.company_sectorial_dependence_analyzer import (
    CompanySectorialDependenceAnalyzer,
)


class Command(BaseCommand):
    help = "Analyze a company's sector dependence for a given CIK."

    def add_arguments(self, parser):
        parser.add_argument("cik", help="SEC CIK to analyze, e.g. 73309 or 0000073309")
        parser.add_argument(
            "--output",
            default="dependence_simple.png",
            help="Path to the output image to generate.",
        )

    def handle(self, *args, **options):
        raw_cik = str(options["cik"]).strip()
        if not raw_cik:
            raise CommandError("A CIK value is required.")

        if raw_cik.isdigit():
            normalized_cik = raw_cik.zfill(10)
        else:
            normalized_cik = raw_cik

        try:
            company = Company.objects.get(cik=normalized_cik)
        except Company.DoesNotExist:
            company = None

        if company is None and raw_cik.isdigit():
            company = (
                Company.objects.filter(cik__endswith=raw_cik).order_by("cik").first()
            )
        if company is None and not raw_cik.isdigit():
            company = (
                Company.objects.filter(cik__icontains=raw_cik).order_by("cik").first()
            )

        if company is None:
            raise CommandError(f"No company found for CIK '{raw_cik}'.")

        builder = SecSectorBuilder()
        company.sectorial_revenues.all().delete()
        CompanyBuilder.update_companies_info([company])
        builder.build_for_company(company)

        analyzer = CompanySectorialDependenceAnalyzer()
        result = analyzer.analyze(company)

        output_path = options["output"]
        visualizer = DependenceViz(result)
        visualizer.save(output_path)

        self.stdout.write(
            self.style.SUCCESS(
                f"Analysis complete for {company.name} ({company.cik}). Output: {output_path}"
            )
        )
