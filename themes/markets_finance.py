from podkit.cli import run_theme
from podkit.themes import Theme

THEME = Theme(
    key="markets-finance",
    title="Marchés & Finance",
    icon="📈",
    accent="#10b981",
    summary="Bourse, tech, services publics et matières premières — France, US et le monde.",
    research_brief="""Daily markets and finance briefing centred on France and the United States,
plus any worldwide development that could influence them.

Cover, with concrete figures, prices and percentage moves:
- International stock markets, with a strong emphasis on technology: major indices
  (CAC 40, S&P 500, Nasdaq, Euro Stoxx), notable big-tech and semiconductor moves,
  earnings, AI-related news, IPOs and major rate / central-bank decisions (Fed, ECB).
- National / utility services in France and the US: water, energy (electricity, gas,
  nuclear, renewables) and transport (rail, airlines, public transit) — prices,
  outages, strikes, regulation, infrastructure and major operators (EDF, Engie, Veolia,
  SNCF, RATP and US equivalents).
- Commodities: gold, silver, copper and oil (Brent / WTI) — spot levels, drivers and
  outlook.
- Global news (geopolitics, trade, macro data, currencies) that can move the above.

Explain WHY things moved, not just that they moved.""",
    rss=[
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        "https://www.lemonde.fr/economie/rss_full.xml",
        "https://www.investing.com/rss/news_25.rss",
    ],
    language="fr",
    minutes=10,
)


if __name__ == "__main__":
    raise SystemExit(run_theme(THEME))
