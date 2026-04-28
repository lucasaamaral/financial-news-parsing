"""Domain configuration: keyword sets, section lists, thresholds, and defaults."""

from __future__ import annotations

_COMMON_MARKET_SIGNAL_KEYWORDS = {
    "b3",
    "copom",
    "ibovespa",
    "selic",
}

_BRAZIL_CENTRAL_BANK_KEYWORDS = {
    "banco central do brasil",
    "banco central brasileiro",
    "bcb",
}

_BRAZIL_POLICY_SIGNAL_KEYWORDS = _COMMON_MARKET_SIGNAL_KEYWORDS | {
    "cvm",
    "ipca",
    "tesouro direto",
}

_BRAZIL_MARKET_REFERENCE_KEYWORDS = {
    "bovespa",
    "dolar",
    "dolar futuro",
    "ifix",
    "mercado brasileiro",
    "real brasileiro",
}

_DIRECT_BRAZIL_REFERENCE_KEYWORDS = {
    "bovespa",
    "ifix",
    "mercado brasileiro",
    "real brasileiro",
}

_DIRECT_BRAZIL_ENTITY_KEYWORDS = {
    "banco do brasil",
    "bb seguridade",
    "bndes",
    "credito imobiliario",
    "dis",
    "economia brasileira",
    "itau",
    "itau unibanco",
    "juros futuros",
    "ministerio da fazenda",
    "petrobras",
    "pib brasileiro",
    "tesouro nacional",
    "vale",
}

_EXCHANGE_AGAINST_REAL_KEYWORDS = {
    "ante o real",
    "contra o real",
    "frente ao real",
}

_FOCUSED_CENTRAL_BANK_TOPIC_KEYWORDS = {
    "banco central",
    "banco central do brasil",
    "bcb",
    "boletim focus",
    "focus",
}

_FOCUSED_MARKET_TOPIC_KEYWORDS = _COMMON_MARKET_SIGNAL_KEYWORDS | {
    "aluguel",
    "cambio",
    "cdi",
    "credito",
    "curva de juros",
    "debenture",
    "debentures",
    "dividendo",
    "dividendos",
    "dolar",
    "emprestimo",
    "financiamento",
    "indice futuro",
    "inflacao",
    "ipca",
    "juros",
    "mini-indice",
    "minicontratos",
    "pib",
    "pmi",
    "pmis",
    "provento",
    "proventos",
    "renda fixa",
    "spread",
    "swap cambial",
    "tesouro",
    "tesouro direto",
}

_LIVE_COVERAGE_TITLE_MARKERS = {
    "ao vivo",
    "cobertura ao vivo",
    "destaques",
    "minuto a minuto",
    "ultimas noticias",
    "ultimas notícias",
}

_RAW_PATH_DENY_SECTIONS = {
    "esg",
    "fundos",
    "mercado-imobiliario",
    "minhas-financas",
    "onde-investir",
    "stock-pickers",
}

FINANCE_KEYWORDS = _COMMON_MARKET_SIGNAL_KEYWORDS | {
    "acao",
    "acoes",
    "agronegocio",
    "balanco",
    "banco central",
    "bolsa",
    "cambio",
    "credito",
    "criptomoeda",
    "debenture",
    "dividendo",
    "dolar",
    "economia",
    "empresa",
    "etf",
    "fii",
    "fundo",
    "ifix",
    "inflacao",
    "investimento",
    "investimentos",
    "investidor",
    "investidores",
    "investir",
    "ipo",
    "juros",
    "lucro",
    "mercado",
    "petrobras",
    "real",
    "renda fixa",
    "risco",
    "tesouro",
    "vale",
}

BRAZIL_MARKET_KEYWORDS = (
    _BRAZIL_POLICY_SIGNAL_KEYWORDS
    | _BRAZIL_CENTRAL_BANK_KEYWORDS
    | _BRAZIL_MARKET_REFERENCE_KEYWORDS
    | {
        "anbima",
        "bndes",
        "brasil",
        "brasileira",
        "brasileiras",
        "brasileiro",
        "brasileiros",
        "ibc-br",
        "ministerio da fazenda",
    }
)

FOREIGN_CONTEXT_KEYWORDS = {
    "argentina",
    "argentino",
    "argentinos",
    "asia-pacifico",
    "bank of england",
    "bce",
    "boe",
    "buenos aires",
    "cepo",
    "china",
    "dow jones",
    "ecb",
    "eua",
    "europa",
    "fed",
    "federal reserve",
    "fomc",
    "fmi",
    "japao",
    "japones",
    "japonesa",
    "milei",
    "nasdaq",
    "nikkei",
    "powell",
    "s&p 500",
    "treasury",
    "wall street",
    "yuan",
    "zona do euro",
}

DIRECT_BRAZIL_CONTEXT_KEYWORDS = (
    _BRAZIL_POLICY_SIGNAL_KEYWORDS
    | _BRAZIL_CENTRAL_BANK_KEYWORDS
    | _DIRECT_BRAZIL_REFERENCE_KEYWORDS
    | _DIRECT_BRAZIL_ENTITY_KEYWORDS
    | _EXCHANGE_AGAINST_REAL_KEYWORDS
    | {"ibc-br"}
)

CORPORATE_RESULTS_METRIC_MARKERS = {
    "balanco",
    "ebitda",
    "guidance",
    "lucro",
    "prejuizo",
}

CORPORATE_RESULTS_PERIOD_MARKERS = {
    "1 tri",
    "1o tri",
    "1t",
    "2 tri",
    "2o tri",
    "2t",
    "3 tri",
    "3o tri",
    "3t",
    "4 tri",
    "4o tri",
    "4t",
    "ano",
    "anual",
    "primeiro trimestre",
    "quarto trimestre",
    "segundo trimestre",
    "semestre",
    "semestral",
    "terceiro trimestre",
    "trimestre",
    "trimestral",
}

AGGREGATE_RESULTS_MARKERS = {
    "bancos",
    "companhias",
    "empresas",
    "industria",
    "industrias",
    "setor",
    "setores",
}

FOCUSED_TOPIC_KEYWORDS = (
    _FOCUSED_CENTRAL_BANK_TOPIC_KEYWORDS
    | _FOCUSED_MARKET_TOPIC_KEYWORDS
)

SOURCE_PRIORITY: dict[str, int] = {
    "Valor Econômico": 0,
    "InfoMoney": 1,
    "Exame": 2,
}

GROSS_SECTION_ALLOWLIST: dict[str, set[str]] = {
    "InfoMoney": {
        "mercados",
        "economia",
        "negocios",
        "fundos",
        "cotacoes",
        "colunistas",
    },
    "Exame": {
        "invest",
        "economia",
        "mercado",
        "negocios",
    },
    "Valor Econômico": {
        "financas",
        "empresas",
        "politica",
        "brasil",
        "mundo",
        "agronegocios",
        "legislacao",
    },
}

GROSS_SECTION_DENYLIST: dict[str, set[str]] = {
    "InfoMoney": {
        "consumo",
        "esportes",
        "entretenimento",
        "tecnologia",
        "turismo",
        "variedades",
    },
    "Exame": {
        "casual",
        "carreira",
        "esg",
        "minhas-financas",
        "pop",
        "science-health",
    },
    "Valor Econômico": {
        "eu-e",
        "carreira",
        "cultura",
        "gastronomia",
    },
}

STRICT_SECTION_SIGNAL_THRESHOLD: dict[str, int] = {
    "empresas": 4,
    "negocios": 4,
    "politica": 6,
}

CORPORATE_ANNOUNCEMENT_TITLE_MARKERS: set[str] = {
    # Dividend / JCP payment announcements
    "anuncia dividendo",
    "aprova dividendo",
    "aprova jcp",
    "data ex-dividendo",
    "data ex dividendo",
    "declara jcp",
    "distribui dividendo",
    "distribuicao de dividendo",
    "dividend yield de",
    "dividendo por acao",
    "dividendos por acao",
    "jcp de r$",
    "pagamento de dividendo",
    "pagamento de dividendos",
    "retorno com dividendos de",
    # Results / earnings disclosures
    "apresenta resultado",
    "divulga balanco",
    "divulga resultado",
    "lucro liquido de",
    "registra lucro",
    "registra prejuizo",
    "reporta resultado",
    "reverte prejuizo",
    "reverte resultado",
    "lucra no",
    "lucra em",
    "lucra r$",
    "prejuizo no",
    "prejuizo em",
    "prejuizo r$",
    "resultado liquido",
    "resultado operacional",
    "balanco trimestral",
    "resultado trimestral",
    "resultado do trimestre",
    "lucro do trimestre",
    "prejuizo do trimestre",
    "receita do trimestre",
    "receita trimestral",
    "contas do trimestre",
    "apos o balanco",
    "apos balanco",
    # Capital raising / operational updates
    "anuncio de oferta de acoes",
    "anuncio de oferta primaria de acoes",
    "dados operacionais",
    "numeros operacionais",
    "oferta de acoes",
    "oferta primaria de acoes",
    "oferta subsequente de acoes",
    "volume medio negociado",
    "volume negociado em",
    # Debenture / bond issuances
    "coloca debenture",
    "emissao de debenture",
    "emite debenture",
    "oferta de debenture",
}

FINAL_SECTION_DENYLIST: set[str] = {
    "esg",
    "onde-investir",
}

RAW_PATH_DENYLIST_MARKERS: set[str] = {
    f"/{section}/" for section in _RAW_PATH_DENY_SECTIONS
}

GENERIC_TITLE_DENYLIST: set[str] = _LIVE_COVERAGE_TITLE_MARKERS

GENERIC_TITLE_MARKERS: set[str] = {
    "after market",
    "after-market",
    "comprar ou vender",
    "como investir",
    "eventos que o mercado deve olhar",
    "no radar",
    "vale a pena",
    "veja mais",
}

ROUNDUP_URL_MARKERS: set[str] = {
    "ao-vivo",
    "after-market",
    "comprar-ou-vender",
    "cobertura-ao-vivo",
    "destaques",
    "minuto-a-minuto",
    "no-radar",
    "ultimas-noticias",
}

OUTPUT_FIELDS: tuple[str, ...] = (
    "source",
    "url",
    "published_at",
    "week_key",
    "week_start",
    "week_end",
    "tags",
    "title",
    "description",
    "sentiment_text",
)

DEFAULT_REQUEST_DELAY: float = 0.2
DEFAULT_MAX_CONCURRENT_REQUESTS_PER_ORIGIN: int = 4
DEFAULT_RANDOM_SEED: int = 42
DEFAULT_ENRICH_WORKERS: int = 8
DEFAULT_SITEMAP_WORKERS: int = 16
