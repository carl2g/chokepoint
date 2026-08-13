from django.db import models


# Create your models here.
class Company(models.Model):
    name = models.CharField(max_length=255)
    tickers = models.JSONField(default=list, unique=True, null=True)
    sic = models.CharField(max_length=10, null=True)
    cik = models.CharField(max_length=10, null=True)
    hq_country_code = models.CharField(max_length=2, default=None, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["cik"],
                name="unique_company_cik",
            )
        ]


class ExternalSegmentType(models.Model):
    SOURCE_SEC_SIC = "sec_sic"
    SOURCES = [SOURCE_SEC_SIC]

    MAPPING_TYPE_AI = "ai"
    MAPPING_TYPE_MANUAL = "manual"
    MAPPING_TYPE = [MAPPING_TYPE_AI, MAPPING_TYPE_MANUAL]

    source = models.CharField(max_length=255, null=False)
    original_name = models.CharField(max_length=255, null=False)
    external_id = models.CharField(max_length=255, null=False)
    description = models.TextField(null=True)
    exiobase_segment_name = models.CharField(max_length=255, null=True, default=None)
    mapping_type = models.CharField(max_length=255, null=True, default=None)
    validated = models.BooleanField(default=False)
    skipped = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "external_id"],
                name="unique_source_external_id",
            )
        ]


class Sector(models.Model):
    year = models.IntegerField(null=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=False)
    country_code = models.CharField(max_length=255)
    external_sector = models.ForeignKey(
        ExternalSegmentType, null=False, on_delete=models.DO_NOTHING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "year", "country_code", "external_sector"],
                name="unique_company_year_country_code_external_sector",
            )
        ]


class SectorialRevenue(models.Model):
    revenue = models.FloatField(null=False)
    currency = models.CharField(max_length=5, null=False)
    year = models.IntegerField(null=False)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=False, related_name="sectorial_revenues"
    )
    sector = models.ForeignKey(
        Sector, on_delete=models.CASCADE, null=False, related_name="sectorial_revenues"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "sector"],
                name="unique_company_sector",
            )
        ]
