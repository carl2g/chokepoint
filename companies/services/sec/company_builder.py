from collections import defaultdict
import pprint
from time import sleep
import requests
import yfinance as yf
from companies.core.sec_mapping import EDGAR_TO_ISO
from companies.models import Company


class CompanyBuilder:
    """
    A class to fill the database with companies from the SEC API.
    """

    @classmethod
    def create_companies(cls):
        """
        Create companies from the SEC API and store them in the database.
        """
        response = cls.json_response("https://www.sec.gov/files/company_tickers.json")

        grouped = defaultdict(lambda: {"title": None, "tickers": []})

        for item in response.values():
            cik = str(item["cik_str"]).zfill(10)
            grouped[cik]["title"] = item["title"]
            ticker = item["ticker"]
            if ticker not in grouped[cik]["tickers"]:
                grouped[cik]["tickers"].append(ticker)

        for cik, data in grouped.items():
            Company.objects.update_or_create(
                cik=cik,
                defaults={
                    "name": data["title"],
                    "tickers": data["tickers"],
                },
            )

    @classmethod
    def update_companies_info(cls, companies: list[Company]):
        for company in companies:
            pprint.pprint(
                f"Updating company info for {company.name} (CIK: {company.cik})"
            )
            response = cls.json_response(
                f"https://data.sec.gov/submissions/CIK{company.cik}.json"
            )
            company.sic = response["sic"]
            company.hq_country_code = cls._hq_country(response)
            company.save()

    @classmethod
    def _hq_country(cls, meta):
        edgar_country_code = (
            meta["addresses"]["business"]["countryCode"]
            or meta["addresses"]["business"]["stateOrCountry"]
        )

        return EDGAR_TO_ISO.get(edgar_country_code, None)

    @classmethod
    def json_response(cls, url):
        headers = {"User-Agent": "degentilecarl@gmail.com"}
        response = requests.get(
            url,
            headers=headers,
            timeout=5,
        )
        if response.status_code != 200:
            return None
        return response.json()
