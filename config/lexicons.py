"""Word lists and pattern libraries used by the analyzers.

These are deliberately plain data so they can be extended without touching
analysis logic.
"""
from __future__ import annotations

FILLER_PHRASES = [
    "in today's fast-paced world", "in today's digital age", "it goes without saying",
    "needless to say", "at the end of the day", "game-changer", "game changer", "game-changing",
    "cutting-edge", "cutting edge", "state-of-the-art", "world-class", "best-in-class",
    "next-level", "take it to the next level", "unlock the power", "revolutionary", "seamless",
    "robust solution", "one-stop shop", "second to none", "look no further", "ever-evolving",
    "delve into", "in conclusion", "as we all know", "synergy", "holistic approach",
    "passionate about", "industry-leading", "innovative solutions", "tailored solutions",
    "unparalleled", "empower your", "supercharge", "elevate your",
]

ATTRIBUTION_PATTERNS = [
    r"\baccording to\b", r"\bsources?:",
    r"\b(study|survey|report|research|analysis|whitepaper|white paper|audit)\s+(by|from|of|published)\b",
    r"\b(published|reported|found|estimated|stated|measured)\s+(by|in)\b",
    r"\[\d+\]", r"\(\s*(?:19|20)\d{2}\s*\)", r"\bdata from\b",
    r"\bas (?:reported|noted|stated|cited) (?:by|in)\b", r"\bcited\b",
]

SUPERLATIVE_CUES = [
    r"\bbest\b", r"\bleading\b", r"#1\b", r"\bnumber one\b", r"\bfastest\b", r"\bmost trusted\b",
    r"\btop[- ]rated\b", r"\baward[- ]winning\b", r"\bmarket leader\b", r"\bproven\b",
    r"\blargest\b", r"\bonly\b", r"\bguaranteed\b", r"\bmost popular\b", r"\bhighest[- ]rated\b",
]

RECOMMEND_CUES = [
    r"\bbest\b", r"\btop (?:pick|choice)\b", r"\brecommend(?:ed|s)?\b", r"\bideal\b",
    r"\bgreat (?:choice|option|fit)\b", r"\bleading\b", r"\bgo-to\b", r"\bstands? out\b",
    r"\bour pick\b", r"\bperfect for\b", r"\bexcellent\b", r"\bis a strong\b", r"\bpopular choice\b",
]

DEPENDENT_OPENERS = (
    r"^(?:this|that|these|those|it|they|he|she|however|moreover|additionally|also|furthermore|"
    r"as mentioned|as noted|in addition|therefore|thus|such|similarly|likewise|meanwhile)\b"
)

RELATIONSHIPS: dict[str, str] = {
    "partnership": r"partner(?:s|ed|ship)? (?:with|of)|in partnership with|teams? up with|collaborat\w+ with",
    "integration": r"integrat\w+ with|connects? (?:to|with)|works? with|compatible with|syncs? with",
    "competition": r"compet\w+ (?:with|against)|alternative to|versus|\bvs\.?\b|compared (?:to|with)|rival",
    "ownership": r"acquired by|acquired|owned by|subsidiary of|part of|parent company|merged with",
    "founding": r"founded by|co-founded by|created by|built by|developed by|launched by|started by",
    "location": r"based in|headquartered in|located in|offices? in|operates in|available in",
    "usage": r"used by|trusted by|customers include|clients include|serves|supplies|powers",
    "recognition": r"awarded by|certified by|accredited by|recogni[sz]ed by|featured in|listed on|reviewed by|ranked by",
}

ORG_SUFFIXES = {
    "inc", "ltd", "limited", "llc", "llp", "corp", "corporation", "co", "company", "group",
    "holdings", "pty", "gmbh", "plc", "technologies", "labs", "partners", "associates",
    "university", "institute", "foundation", "agency", "bank", "council", "association", "society",
    "ministry", "department", "authority", "commission",
}

PERSON_TITLES = {
    "dr", "mr", "mrs", "ms", "prof", "professor", "ceo", "cto", "cfo", "coo", "founder",
    "co-founder", "director", "manager", "chair", "president", "head", "analyst",
}

COUNTRIES = {
    "new zealand", "australia", "united states", "usa", "united kingdom", "uk", "canada", "india",
    "nepal", "china", "japan", "singapore", "germany", "france", "ireland", "south africa", "brazil",
    "mexico", "spain", "italy", "netherlands", "sweden", "norway", "denmark", "philippines",
    "malaysia", "indonesia", "thailand", "vietnam", "uae", "united arab emirates", "europe", "asia",
    "africa", "pacific", "fiji", "samoa", "tonga",
}

CITIES = {
    "auckland", "wellington", "christchurch", "hamilton", "dunedin", "tauranga", "queenstown",
    "sydney", "melbourne", "brisbane", "perth", "adelaide", "canberra", "london", "manchester",
    "new york", "san francisco", "los angeles", "chicago", "seattle", "austin", "boston", "toronto",
    "vancouver", "mumbai", "delhi", "bangalore", "kathmandu", "singapore", "tokyo", "berlin",
    "paris", "dublin", "amsterdam", "dubai", "hong kong", "shanghai", "beijing",
}

# Capitalised words that are not entities when they begin a sentence or stand alone
NON_ENTITY_WORDS = {
    "the", "this", "that", "these", "those", "there", "their", "they", "then", "than", "thus", "though",
    "however", "moreover", "also", "and", "but", "for", "with", "without", "from", "into", "our", "your",
    "its", "his", "her", "who", "what", "when", "where", "why", "how", "which", "while", "whether",
    "some", "many", "most", "all", "any", "each", "every", "both", "either", "neither", "other",
    "another", "such", "here", "now", "if", "in", "on", "at", "by", "as", "of", "to", "it", "is", "are",
    "was", "were", "be", "been", "has", "have", "had", "do", "does", "did", "can", "could", "should",
    "would", "will", "may", "might", "must", "we", "you", "he", "she", "one", "two", "three", "first",
    "second", "third", "next", "last", "more", "less", "best", "top", "key", "step", "note",
    "see", "read", "learn", "get", "start", "try", "use", "yes", "no", "not", "so", "or", "because",
    "after", "before", "during", "since", "until", "about", "above", "below", "over", "under",
    "january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
    "november", "december", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "overview", "introduction", "conclusion", "summary", "faq", "faqs", "pricing", "features", "contact",
}

TECH_ACRONYMS_EXCLUDE = {"A", "I", "OK", "US", "UK", "NZ", "AU", "EU", "FAQ", "FAQS", "PDF", "URL", "ID", "TV", "PM", "AM"}

# Ordered rules for source-type classification. First match wins.
SOURCE_TYPE_RULES: list[tuple[str, list[str]]] = [
    ("encyclopaedia", ["wikipedia.org", "britannica.com", "wikidata.org"]),
    ("community_forum", ["reddit.com", "quora.com", "stackexchange.com", "stackoverflow.com",
                         "news.ycombinator.com", "forum.", "community."]),
    ("social_video", ["linkedin.com", "facebook.com", "x.com", "twitter.com", "instagram.com",
                      "youtube.com", "tiktok.com"]),
    ("review_directory", ["g2.com", "capterra.com", "trustpilot.com", "softwareadvice.com", "getapp.com",
                          "yelp.com", "producthunt.com", "crunchbase.com", "tripadvisor.com",
                          "glassdoor.com", "clutch.co", "sitejabber.com", "bbb.org", "review", "compar"]),
    ("academic_government", [".edu", ".gov", ".govt.", ".ac.", "arxiv.org", "nih.gov", "nature.com",
                             "sciencedirect.com", "springer.com", "jstor.org"]),
    ("news_media", ["bbc.", "nytimes.com", "reuters.com", "theguardian.com", "forbes.com", "techcrunch.com",
                    "nzherald.co.nz", "stuff.co.nz", "rnz.co.nz", "bloomberg.com", "cnn.com", "wsj.com",
                    "theverge.com", "wired.com", "afr.com", "abc.net.au", "smh.com.au", "businessinsider.com",
                    "cnbc.com", "ft.com", "news"]),
]

SOURCE_TYPE_LABELS = {
    "own_site": "Own website",
    "competitor_site": "Competitor website",
    "encyclopaedia": "Encyclopaedia",
    "community_forum": "Community or forum",
    "social_video": "Social or video platform",
    "review_directory": "Review site or directory",
    "academic_government": "Academic or government",
    "news_media": "News or media",
    "other_web": "Other web source",
}

# Query-adaptive subtopic facets: (label, keywords)
FACET_SETS: dict[str, list[tuple[str, list[str]]]] = {
    "commercial": [
        ("What it is (definition and overview)", ["is a", "is an", "refers to", "overview", "designed to"]),
        ("Key features and capabilities", ["feature", "includes", "offers", "functionality", "capability", "integration"]),
        ("Pricing and plans", ["price", "pricing", "cost", "plan", "per month", "free", "subscription", "trial", "$"]),
        ("Benefits and strengths", ["benefit", "advantage", "strength", "helps", "saves", "improves"]),
        ("Limitations and trade-offs", ["limitation", "drawback", "downside", "however", "not suitable", "lacks", "trade-off"]),
        ("Comparison with alternatives", ["alternative", "compared", "versus", "vs", "competitor", "instead of", "rather than"]),
        ("Use cases and target audience", ["for small", "suited", "ideal for", "use case", "designed for", "who it"]),
        ("Selection criteria", ["choose", "criteria", "consider", "factors", "what to look for", "decide"]),
        ("Evidence, reviews and proof", ["review", "rating", "rated", "tested", "study", "survey", "case study", "customers"]),
        ("Availability, support and setup", ["support", "available", "region", "country", "onboarding", "setup", "implementation"]),
    ],
    "transactional": [
        ("Pricing and plans", ["price", "pricing", "cost", "plan", "per month", "free", "$"]),
        ("What is included", ["includes", "included", "features", "package"]),
        ("How to buy or sign up", ["buy", "sign up", "get started", "order", "book", "subscribe", "trial"]),
        ("Comparison with alternatives", ["alternative", "compared", "versus", "vs", "instead of"]),
        ("Guarantees, terms and support", ["guarantee", "refund", "terms", "support", "warranty", "cancel"]),
        ("Reviews and proof", ["review", "rating", "customers", "case study", "testimonial"]),
    ],
    "informational": [
        ("Definition", ["is a", "is an", "refers to", "means", "defined as"]),
        ("How it works", ["how it works", "works by", "process", "mechanism", "steps"]),
        ("Components or types", ["types of", "components", "consists of", "categories", "kinds of"]),
        ("Benefits and applications", ["benefit", "used for", "application", "use case", "advantage"]),
        ("Examples", ["for example", "for instance", "example", "such as"]),
        ("Risks and limitations", ["risk", "limitation", "challenge", "drawback", "downside"]),
        ("Evidence and data", ["study", "research", "data", "survey", "statistics", "found that"]),
        ("Related concepts", ["related", "similar to", "differs from", "compared with", "alternative"]),
    ],
    "howto": [
        ("Prerequisites", ["prerequisite", "before you", "you will need", "requirements"]),
        ("Step-by-step process", ["step", "first", "next", "then", "finally"]),
        ("Tools and resources", ["tool", "software", "template", "resource", "equipment"]),
        ("Common mistakes", ["mistake", "avoid", "pitfall", "common error"]),
        ("Time and cost", ["takes", "minutes", "hours", "cost", "budget"]),
        ("Examples", ["for example", "example", "sample"]),
        ("Troubleshooting", ["troubleshoot", "fix", "problem", "issue", "if it fails"]),
    ],
    "local": [
        ("Location and service area", ["located", "address", "service area", "based in", "serves"]),
        ("Services offered", ["services", "we offer", "offers", "specialis"]),
        ("Opening hours and contact", ["hours", "open", "phone", "email", "contact"]),
        ("Pricing", ["price", "pricing", "cost", "from $", "quote"]),
        ("Reviews and credentials", ["review", "rating", "licensed", "certified", "accredited", "years of experience"]),
    ],
    "navigational": [
        ("About the organisation", ["about", "founded", "mission", "team", "history"]),
        ("Products and services", ["product", "service", "solutions", "offers"]),
        ("Pricing", ["price", "pricing", "plan", "cost"]),
        ("Support and contact", ["support", "contact", "help", "phone", "email"]),
    ],
}
