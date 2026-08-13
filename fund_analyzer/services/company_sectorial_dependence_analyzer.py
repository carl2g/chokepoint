from collections import defaultdict
from typing import List

from django.db.models.aggregates import Max
import pymrio

from companies.models import Company, Sector, SectorialRevenue
from fund_analyzer.lib.exiobase_io import ExiobaseIO


class CompanySectorialDependenceAnalyzer:

    def __init__(self):
        self.exiobase_io = ExiobaseIO.exiobase_io_system()

    def analyze(self, company: Company):
        sectorial_dependence = defaultdict(lambda: defaultdict(dict))
        company_sectorial_revenues = self.get_company_sectorial_revenues(company)

        for revenue in company_sectorial_revenues:
            sector = revenue.sector
            exiobase_sector_name = sector.external_sector.exiobase_segment_name
            if exiobase_sector_name is None:
                continue

            for (country_code, dep_exiobase_sector), value in self.exiobase_io.L[:][
                sector.country_code, exiobase_sector_name
            ].items():

                if (
                    country_code == sector.country_code
                    and dep_exiobase_sector == exiobase_sector_name
                ):
                    value = value - 1.0

                if value <= 0:
                    continue

                sectorial_dependence[exiobase_sector_name][country_code][
                    str(dep_exiobase_sector)
                ] = (value * revenue.revenue / 1e6)
        return sectorial_dependence

    def get_company_sectorial_revenues(self, company: Company):
        latest_year = company.sectorial_revenues.aggregate(Max("year"))["year__max"]
        return company.sectorial_revenues.select_related("sector").filter(
            year=latest_year
        )
