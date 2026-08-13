from __future__ import annotations
from collections import defaultdict
import pprint
from forex_python.converter import CurrencyRates
from edgar import XBRL, Company as EdgarCompany, set_identity
from edgar.entity.filings import EntityFilings

from companies.services.sec.company_builder import CompanyBuilder

set_identity("carl.degentile@gmail.com")

from decimal import Decimal


from typing import Dict, List, Optional, Tuple

from companies.core.country import GEO_ISO_COUNTRIES
from companies.models import Company, ExternalSegmentType, SectorialRevenue, Sector

# from companies.services.sec.sec_num_parser import SecNumParser


class SecSectorBuilder:
    """Create sector and revenue records from SEC num.txt data."""

    REVENUE_TAGS = [
        # --- Tier 1: clean company-wide revenue, standard definition ---
        "RevenueFromContractWithCustomerExcludingAssessedTax",  # canonical, ex-tax
        "Revenues",
        "Revenue",
        "RevenueFromContractsWithCustomers",
        # --- Tier 2: common variants, slightly different scope ---
        "NetSales",
        "NetRevenue",
        "RevenueFromContractWithCustomerIncludingAssessedTax",  # includes sales tax
        "RevenueFromSaleOfGoods",  # goods only, may miss services
        "RevenuesGross",  # before deductions
        # --- Tier 3: broad/mixed, use only if nothing above exists ---
        "TotalRevenuesAndIncome",  # includes non-revenue income
        "RevenueAndOperatingIncome",  # mixes revenue + income
        "OtherOperatingRevenue",  # residual
    ]
    PPE_TAGS = [
        # --- Tier 1: owned productive assets, cleanest ---
        "PropertyPlantAndEquipmentNet",  # net, owned — gold standard
        "PropertyPlantAndEquipmentNetExcludingLand",  # net, owned (land excluded, negligible diff)
        "PropertyPlantAndEquipmentExcludingConstructionInProgress",  # owned, excl. WIP
        "PropertyPlantAndEquipmentGross",  # owned, gross — proportions still valid
        "PropertyPlantAndEquipment",  # unspecified net/gross, still owned
        # --- Tier 2: owned + leased bundled (your accepted fallback, mild contamination) ---
        "PropertyPlantAndEquipmentIncludingRightofuseAssets",
        "PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization",
        "PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetBeforeAccumulatedDepreciationAndAmortization",
        "PropertyPlantAndEquipmentAndOperatingLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization",  # operating-lease = more demand-side, weaker
        # --- Tier 3: broad non-current assets, last resort before HQ ---
        "NoncurrentAssets",
        "AssetsNoncurrent",
        "OtherNoncurrentAssets",  # weak — residual bucket
        "OtherAssetsNoncurrent",  # weak — residual bucket
    ]
    BUSINESS_SEGMENT_LABEL = "BusinessSegments"
    GEOGRAPHICAL_LABEL = "StatementGeographicalAxis"

    def __init__(self):
        # self.archive_path = archive_path
        # self.year = year
        # self.parser = SecNumParser(archive_path)
        self.eur_rates = CurrencyRates().get_rates("EUR")

    def build_for_company(self, company: Company) -> List[Sector]:
        company_annual_report = EdgarCompany(company.cik).latest("10-K")

        if company.sic is None:
            pprint.pp(f"No SIC code found for {company.name} ({company.cik})")
            return []

        pprint.pp(f"{company.name}, {company.cik}")
        if not company_annual_report:
            print(f"No 10-K filing found for {company.name} ({company.cik})")
            return []

        xbrl_annual_report = company_annual_report.xbrl()
        if not xbrl_annual_report:
            print(f"No XBRL data found for {company.name} ({company.cik})")
            return []

        country_weights = self._build_country_weights(xbrl_annual_report, company)
        # pprint.pp(
        #     f"Geographical PPE: {len(country_weights.keys())}",
        # )

        if not country_weights:
            return []

        rev = self._total_revenue(xbrl_annual_report)
        # pprint.pp(f"Revenues segments: {rev}")

        if not rev:
            return []

        created = []
        pprint.pp(rev)
        total_revenue = rev["numeric_value"]

        if total_revenue is None or total_revenue <= 0:
            pprint.pp(f"No valid revenue found for {company.name} ({company.cik})")
            return []

        pprint.pp(country_weights)
        pprint.pp(total_revenue)
        for country_code, weight in country_weights.items():
            allocated_revenue = total_revenue * weight

            edgar_sector, _ = ExternalSegmentType.objects.get_or_create(
                source=ExternalSegmentType.SOURCE_SEC_SIC, external_id=company.sic
            )
            print(
                company.name,
                edgar_sector.original_name,
                rev["fiscal_year"],
                country_code,
                edgar_sector.exiobase_segment_name,
                allocated_revenue,
            )

            sector, _ = Sector.objects.update_or_create(
                company=company,
                year=rev["fiscal_year"],
                country_code=country_code,
                external_sector=edgar_sector,
            )
            created.append(sector)

            SectorialRevenue.objects.update_or_create(
                company=company,
                sector=sector,
                year=rev["fiscal_year"],
                defaults={"revenue": allocated_revenue, "currency": "EUR"},
            )

        return created

    def _total_revenue(self, xbrl_annual_report: XBRL) -> List[Dict[str, str]]:
        for tag in self.REVENUE_TAGS:
            revenues = (
                xbrl_annual_report.query()
                .by_fiscal_period("FY")
                .by_concept(f":{tag}$")
                .by_dimension(None)
                .to_dataframe()
            )

            if revenues.empty or "numeric_value" not in revenues.columns:
                continue

            lastest_period = revenues.sort_values("period_end").iloc[-1]["period_end"]
            # pprint.pp(revenues.to_dict(orient="records"))
            revenue = min(
                revenues[revenues["period_end"] == lastest_period].to_dict(
                    orient="records"
                ),
                key=lambda x: x["decimals"],
            )
            pprint.pp(f"Revenue tag: {tag}")
            # pprint.pp(revenue)
            return revenue
        return None

    def _build_country_weights(
        self,
        xbrl_annual_report: XBRL,
        company: Company,
    ) -> Dict[str, float]:
        geo_ppe_assets = self._ppe_assets_by_region(xbrl_annual_report, company)
        # pprint.pp(geo_ppe_assets)

        if len(geo_ppe_assets) == 0:
            return {company.hq_country_code: 1.0}

        country_values: Dict[str, float] = defaultdict(float)
        total_property = 0.0

        for row in geo_ppe_assets:
            country_code = row.get("geographical_area")

            value = float(row["value"])

            if value <= 0:
                continue
            country_values[country_code] += value
            total_property += value

        return {
            country: value / total_property for country, value in country_values.items()
        }

    def _ppe_assets_by_region(
        self, xbrl_annual_report: XBRL, company: Company
    ) -> List[Dict[str, str]]:
        for tag in self.PPE_TAGS:
            ppes = (
                xbrl_annual_report.query()
                .by_concept(f":{tag}$")
                .by_dimension(self.GEOGRAPHICAL_LABEL)
                .to_dataframe()
            )
            # pprint.pp(ppes.to_dict(orient="records"))
            if ppes.empty:
                continue

            lastest_period = ppes.sort_values("period_instant").iloc[-1][
                "period_instant"
            ]
            ppes = ppes[ppes["period_instant"] == lastest_period]
            pprint.pp(f"PPE tag: {tag}")
            break

        result = []
        for ppe in ppes.to_dict(orient="records"):
            raw = ppe.get("dim_srt_StatementGeographicalAxis")
            member = raw.split(":")[-1]
            area = member if member in GEO_ISO_COUNTRIES else company.hq_country_code
            if not area:
                print(
                    f"Warning: No country code found for {company.name} ({company.cik})"
                )
                continue
            pprint.pp(ppe)
            result.append(
                {
                    "value": self.convert_to_eur(
                        ppe["numeric_value"], ppe["currency"], "EUR"
                    ),
                    "currency": "EUR",
                    "geographical_area": area,
                }
            )
        return result

    def convert_to_eur(
        self, value: float, from_currency: str, to_currency: str
    ) -> float:
        if from_currency == to_currency:
            return value

        return value / self.eur_rates[from_currency]
