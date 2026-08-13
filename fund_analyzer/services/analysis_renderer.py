import matplotlib.pyplot as plt


class DependenceViz:
    """
    Visualise the upstream dependence of a company.

    Input (output of CompanySectorialDependenceAnalyzer.analyze) :
        { company_sector: { country: { upstream_sector: value } } }
    """

    COUNTRY_COLOR = "#2a9d8f"
    SECTOR_COLOR = "#415a77"

    def __init__(self, dependence, company_name="", top=10):
        self.dependence = dependence
        self.company_name = company_name
        self.top = top

    # ---- aggregation
    def _aggregate(self):
        countries, sectors = {}, {}
        for _company_sector, by_country in self.dependence.items():
            for country, by_supplier in by_country.items():
                for supplier_sector, value in by_supplier.items():
                    value = float(value)
                    if value <= 0:
                        continue
                    countries[country] = countries.get(country, 0) + value
                    sectors[supplier_sector] = sectors.get(supplier_sector, 0) + value
        return countries, sectors

    def _top(self, d):
        items = sorted(d.items(), key=lambda x: x[1], reverse=True)[: self.top]
        return [k for k, _ in items][::-1], [v for _, v in items][::-1]

    @staticmethod
    def _trim(labels, n=38):
        return [l[: n - 1] + "…" if len(l) > n else l for l in labels]

    # ---- rendering
    def figure(self):
        countries, sectors = self._aggregate()
        ck, cv = self._top(countries)
        sk, sv = self._top(sectors)

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
        ax1.barh(ck, cv, color=self.COUNTRY_COLOR)
        ax1.set_title("Country dependence")
        ax2.barh(self._trim(sk), sv, color=self.SECTOR_COLOR)
        ax2.set_title("Sector dependence")
        for ax in (ax1, ax2):
            ax.set_xlabel("value per Million euros")
        fig.suptitle(self.company_name, fontsize=13, weight="bold")
        fig.tight_layout()
        return fig

    def save(self, path):
        fig = self.figure()
        fig.savefig(path, dpi=130, bbox_inches="tight")
        plt.close(fig)
        return path

    def show(self):
        self.figure()
        plt.show()
