"""Which job family does this title belong to?

The key insight from real data: **"Engineer" alone means nothing.** These all
contain it and none are software roles:

    GTM Engineer · Customer Success Engineer · Product Solution Engineer
    Service Delivery Engineer · Network Delivery Engineer

So classification runs in three stages:

1. **Strong signals** — unambiguous role names ("Software Engineer", "SRE",
   "Data Engineer") win immediately, so "Service Delivery Engineer, SRE" is
   correctly kept as devops.
2. **Routing** — business, sales, creative, finance and HR keywords send a title
   to the family it really belongs to. These used to be a reject list; they are
   a destination list now, so a design or product student sees their roles too.
   Whether a family is *wanted* is the user's choice (`preferences.role_families`),
   not this module's.
3. **Family keywords** — whatever is left is matched per technical family, most
   specific first (ai_ml → data → devops → software), so "ML Platform Engineer"
   lands in ai_ml rather than software.

Deterministic on purpose: ~0ms versus ~25s for an LLM call, free, explainable and
unit-testable. Same reasoning as the seniority pre-filter.
"""
import re

FAMILIES = (
    # technical
    "software",
    "ai_ml",
    "data",
    "devops",
    "security",
    "qa",
    "hardware",
    "research",
    # non-technical
    "product",
    "design",
    "sales",
    "marketing",
    "content",
    "hr",
    "finance",
    "operations",
)

# What a new user gets before touching Filters: the technical families a
# software-leaning fresher applies to. Everything else is one tick away.
DEFAULT_FAMILIES = ("software", "ai_ml", "data", "devops", "security", "qa")

# Unambiguous role names. Checked first, so they beat the routing table.
# Ordered most-specific-first: "Cloud Security Engineer" is security, not devops,
# and "Embedded Software Engineer" is hardware, not software.
_STRONG = (
    ("ai_ml", r"\b(machine learning engineer|ml engineer|ai engineer|data scientist|"
              r"applied scientist|research engineer|nlp engineer|computer vision engineer)\b"),
    ("data", r"\b(data engineer|analytics engineer|data platform engineer|"
             r"business intelligence engineer|bi engineer)\b"),
    ("security", r"\b(security engineer|security analyst|security operations|secops|"
                 r"application security|appsec|infosec|information security|soc analyst|"
                 r"penetration test\w*|cyber\s?security)\b"),
    ("qa", r"\b(qa engineer|qa analyst|quality assurance|sdet|test engineer|"
           r"test automation|automation test\w*)\b"),
    ("hardware", r"\b(embedded (software )?engineer|firmware engineer|hardware engineer|"
                 r"vlsi|rtl design|asic|fpga|electronics engineer|electrical engineer|"
                 r"mechanical engineer)\b"),
    # "platform engineer" is deliberately NOT here: it is ambiguous ("ML Platform
    # Engineer" is an ML role). It lives in the hints below, where the more
    # specific families get first refusal.
    ("devops", r"\b(sre|site reliability engineer|devops engineer|"
               r"infrastructure engineer|cloud engineer)\b"),
    ("software", r"\b(software engineer|software developer|sde|backend engineer|"
                 r"back-end engineer|frontend engineer|front-end engineer|fullstack engineer|"
                 r"full stack engineer|full-stack engineer|android engineer|ios engineer|"
                 r"mobile engineer|application developer|web developer|systems engineer)\b"),
)

# Where a title goes when it says "Engineer" or "Data" but isn't one.
# Order is precedence, so read it top to bottom:
#   * design before marketing — "Brand Designer" is design, "Brand Manager" isn't
#   * the job function beats the industry — "Customer Experience Specialist, Stock
#     Broking" is sales, so sales comes before finance
#   * finance before research — "Equity Research Analyst" is finance
#   * operations before marketing — "Growth StratOps Associate" is ops, not growth
_ROUTING = (
    ("design", r"\b(designer|design intern|ux|user experience|user interface|\bui/ux\b|"
               r"product design|visual design|graphic|motion design|illustrat\w+|"
               r"industrial design|thumbnail)\b"),
    # Deliberately narrow: "Product Solution Engineer" is a presales role, not a PM.
    ("product", r"\b(product (manager|owner|management|analyst|lead|intern|associate)|"
                r"associate product manager|apm|head of product|director[\s,-]+product|"
                r"product operations|product strategy)\b"),
    ("hr", r"\b(recruit\w*|talent|human (resources|capital)|hr|hrbp|"
           r"people (operations|experience|consultant|partner|analytics)|"
           r"compensation|employee engagement|learning (and|&) development|l&d|"
           r"teacher|instructor|tutor|faculty|trainer|mentor)\b"),
    ("sales", r"\b(gtm|go[\s-]?to[\s-]?market|sales|business development|bdr|sdr|"
              r"account (executive|manager|management|development)|"
              r"customer success|customer experience|client servicing|"
              r"solutions? (engineer|architect|consultant)|presales|pre[\s-]?sales|"
              r"implementation|technical account|partnership\w*|admissions|counsel\w+)\b"),
    ("finance", r"\b(finance|financial|accounting|accountant|audit\w*|taxation|treasury|"
                r"payroll|actuar\w+|underwrit\w+|collections|credit risk|risk management|"
                r"equity research|investment|fp&a|broking|wealth|"
                r"revenue (analyst|accountant|assurance))\b"),
    ("research", r"\b(research (scientist|associate|assistant|analyst|intern|specialist|"
                 r"executive)|scientist|phd)\b"),
    ("operations", r"\b(operations|strat\s?ops|stratops|strategy|supply chain|logistics|"
                   r"warehouse|procurement|manufacturing|chief of staff|"
                   r"(program|project) (manager|management|ops)|"
                   r"service delivery|delivery engineer|service desk|help\s?desk|"
                   r"customer (support|service\w*)|technical support|"
                   r"business (systems? )?analyst|executive assistant|"
                   r"legal|paralegal|privacy|compliance|governance|facilities|"
                   r"administrat\w+)\b"),
    ("marketing", r"\b(market(ing|er)|brand|growth|seo|sem|campaign|demand generation|"
                  r"public relations|social media|community manager|influencer)\b"),
    ("content", r"\b(content|copy\s?writer|copywriting|editor|writer|"
                r"video (editor|editing|produc\w+)|videographer)\b"),
)

# Looser per-family hints for titles that pass the routing table.
# `security` is a hint rather than a strong signal so that "Security Sales
# Specialist" is routed to sales first, while "Security Consultant" still lands here.
_HINTS = (
    ("security", r"\b(security|cyber|vulnerability|threat)\b"),
    ("ai_ml", r"\b(machine learning|deep learning|\bml\b|artificial intelligence|"
              r"\bai\b|\bnlp\b|\bllm\b|computer vision|generative)\b"),
    ("data", r"\b(data|analytics|etl|warehouse|business intelligence|\bbi\b)\b"),
    ("devops", r"\b(devops|infrastructure|kubernetes|cloud|reliability|observability|"
               r"platform|deployment)\b"),
    # "Member of Technical Staff" is what Pure Storage, VMware, Nutanix, Oracle
    # and several AI labs call a software engineer, and it contains none of the
    # words above. Twenty four of them were sitting in "other" on a real
    # database, which is to say filtered out of a fresher's list entirely.
    #
    # A hint rather than a strong signal, so the specific families still win:
    # "Member of Technical Staff - Firmware Engineer" is hardware and "Member of
    # Technical Staff, Fleet Reliability" is devops, both decided before this.
    ("software", r"\b(engineer|engineering|developer|programming|software|backend|frontend|"
                 r"fullstack|android|ios|mobile|api|web|"
                 r"member of (the )?technical staff|mts)\b"),
)


def classify(title: str) -> str:
    """Return one of FAMILIES, or "other" when the title fits none of them."""
    text = title or ""

    for family, pattern in _STRONG:
        if re.search(pattern, text, re.IGNORECASE):
            return family

    for family, pattern in _ROUTING:
        if re.search(pattern, text, re.IGNORECASE):
            return family

    for family, pattern in _HINTS:
        if re.search(pattern, text, re.IGNORECASE):
            return family

    return "other"
