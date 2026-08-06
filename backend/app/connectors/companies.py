"""Seed list of companies to look for across every supported ATS platform.

This is a *search space*, not a claim that each of these has a public board.
`app.ingestion.discover` turns candidate names into slugs, probes all platforms,
keeps what resolves, and — because slugs collide (Ashby's "navi" is a US startup,
not the Indian neobank) — verifies the board actually returns India-relevant jobs
before it is written to the registry.

Grouped only for human readability; discovery treats the list as flat.
"""

SEED_COMPANIES: list[str] = [
    # --- Fintech / payments / neobanks ---
    "Razorpay", "PhonePe", "Paytm", "CRED", "Groww", "Zerodha", "Upstox", "Angel One",
    "Navi", "Slice", "Jupiter", "Fi Money", "OneCard", "Uni Cards", "KreditBee",
    "MoneyView", "LendingKart", "Capital Float", "Rupeek", "Indifi", "Perfios",
    "Signzy", "HyperVerge", "Setu", "Decentro", "M2P Fintech", "Juspay", "Cashfree",
    "PayU", "BharatPe", "Pine Labs", "Mswipe", "Instamojo", "Zolve", "Smallcase",
    "Tickertape", "Sensibull", "Dhan", "Fyers", "INDmoney", "Scripbox", "Kuvera",
    "ETMoney", "Khatabook", "OkCredit", "Refyne", "Jar", "Stable Money",
    # --- Banks / financial services / insurance ---
    "HDFC Bank", "ICICI Bank", "Axis Bank", "Kotak", "Yes Bank", "IDFC First Bank",
    "AU Small Finance Bank", "Bajaj Finserv", "PolicyBazaar", "Acko", "Digit Insurance",
    "Turtlemint", "InsuranceDekho", "Plum", "Onsurity", "Nova Benefits",
    # --- Consumer internet / marketplaces ---
    "Flipkart", "Myntra", "Meesho", "Swiggy", "Zomato", "Zepto", "Blinkit", "Dunzo",
    "BigBasket", "Licious", "Country Delight", "Rapido", "Ola", "Uber", "Porter",
    "Delhivery", "Shiprocket", "Ecom Express", "Udaan", "Zetwerk", "Moglix",
    "Ninjacart", "OYO", "MakeMyTrip", "Ixigo", "RedBus", "Cleartrip", "Yatra",
    "Urban Company", "NoBroker", "Housing", "MagicBricks", "CarDekho", "Cars24",
    "Spinny", "Droom", "Nykaa", "Purplle", "Mamaearth", "boAt", "Sugar Cosmetics",
    "Lenskart", "FirstCry", "Pepperfry", "Wakefit", "Bombay Shaving Company",
    # --- Edtech ---
    "Unacademy", "BYJUS", "Vedantu", "PhysicsWallah", "upGrad", "Simplilearn",
    "Great Learning", "Scaler", "Newton School", "Coding Ninjas", "GeeksforGeeks",
    "InterviewBit", "Emeritus", "Eruditus", "Toppr", "Cuemath", "WhiteHat Jr",
    "LEAD School", "Teachmint", "Classplus", "AlmaBetter", "Masai School",
    # --- Healthtech ---
    "PharmEasy", "Tata 1mg", "Practo", "HealthifyMe", "Cult Fit", "MFine",
    "Innovaccer", "Qure AI", "Niramai", "SigTuple", "Portea", "Medibuddy",
    # --- SaaS / B2B products ---
    "Freshworks", "Zoho", "Chargebee", "BrowserStack", "Postman", "Hasura",
    "MindTickle", "Whatfix", "Capillary Technologies", "Darwinbox", "Keka",
    "Zenoti", "Icertis", "Druva", "Netskope", "Sprinklr", "Gupshup", "Exotel",
    "Kaleyra", "Netcore", "MoEngage", "CleverTap", "WebEngage", "LeadSquared",
    "Wingify", "VWO", "Zluri", "Rocketlane", "Devrev", "Atlan", "Hevo Data",
    "Fractal Analytics", "Mu Sigma", "Tredence", "LatentView", "Course5i",
    "Amagi", "Sirion Labs", "Yellow AI", "Haptik", "Verloop", "Locobuzz",
    "FarEye", "Locus", "Shipsy", "Vymo", "Eightfold AI", "Uniphore", "Observe AI",
    "Skit AI", "Zolvit", "Kissflow", "Vtiger", "Wiz Freshers", "Cloudsek",
    "Seclore", "Lucideus", "Safe Security", "Sequretek", "Instasafe",
    # --- AI / ML / data ---
    "Sarvam AI", "Krutrim", "Two AI", "CoRover", "Gnani AI", "Vernacular AI",
    "Mad Street Den", "Arya AI", "Tonbo Imaging", "Ati Motors", "Ola Krutrim",
    "Turing", "Scale AI", "Weights and Biases", "Hugging Face", "Anthropic",
    # --- Gaming / entertainment / social ---
    "Dream11", "MPL", "Gameskraft", "Zupee", "WinZO", "Nazara", "Games24x7",
    "ShareChat", "Josh", "Moj", "Glance", "Inshorts", "DailyHunt", "Koo",
    "Hoichoi", "JioCinema", "Hotstar", "Pocket FM", "Kuku FM", "Stage",
    # --- Big tech / global with India offices ---
    "Google", "Microsoft", "Amazon", "Meta", "Apple", "Netflix", "Adobe",
    "Salesforce", "Oracle", "SAP", "IBM", "Intel", "Nvidia", "Qualcomm",
    "Cisco", "VMware", "Dell", "HP", "Intuit", "PayPal", "Stripe", "Visa",
    "Mastercard", "American Express", "Goldman Sachs", "Morgan Stanley",
    "JPMorgan Chase", "Wells Fargo", "Barclays", "Deutsche Bank", "UBS",
    "Walmart", "Target", "Expedia", "Booking", "Airbnb", "Atlassian",
    "ServiceNow", "Workday", "Splunk", "Databricks", "Snowflake", "MongoDB",
    "Elastic", "Confluent", "HashiCorp", "GitLab", "GitHub", "DigitalOcean",
    "Cloudflare", "Fastly", "Akamai", "Twilio", "SendGrid", "Okta", "Auth0",
    "Datadog", "New Relic", "PagerDuty", "Grafana Labs", "Sentry", "Sumo Logic",
    "Zscaler", "Palo Alto Networks", "CrowdStrike", "Fortinet", "Trellix",
    "Rubrik", "Cohesity", "Nutanix", "Pure Storage", "NetApp", "Arista Networks",
    "Juniper Networks", "Broadcom", "AMD", "Micron", "Texas Instruments",
    "Analog Devices", "Synopsys", "Cadence", "Siemens", "Philips", "GE Healthcare",
    "Thoughtworks", "Publicis Sapient", "EPAM", "Globant", "Infosys", "Wipro",
    "TCS", "HCLTech", "Tech Mahindra", "LTIMindtree", "Mphasis", "Persistent Systems",
    "Zensar", "Cognizant", "Accenture", "Capgemini", "Deloitte", "PwC", "EY", "KPMG",
    # --- Remote-first / global startups that hire in India ---
    "Automattic", "Zapier", "Doist", "Buffer", "Toggl", "Hotjar", "Aha",
    "Canonical", "Mozilla", "Grammarly", "Notion", "Figma", "Linear", "Vercel",
    "Netlify", "Supabase", "PlanetScale", "Neon", "Render", "Railway",
    "Replit", "Retool", "Airtable", "Miro", "Asana", "Monday", "ClickUp",
    "Loom", "Calendly", "Typeform", "Webflow", "Contentful", "Sanity",
    "Algolia", "Meilisearch", "Pinecone", "Weaviate", "LangChain", "Together AI",
    "Deel", "Remote", "Oyster HR", "Rippling", "Gusto", "Brex", "Ramp", "Mercury",
    "Plaid", "Modern Treasury", "Checkr", "Persona", "Alloy", "Unit21",
    "Coinbase", "Kraken", "Chainalysis", "Consensys", "Polygon", "CoinDCX",
    "CoinSwitch", "WazirX",
    # --- Deeptech / mobility / spacetech ---
    "Ather Energy", "Ola Electric", "Bounce", "Yulu", "Euler Motors",
    "Agnikul Cosmos", "Skyroot Aerospace", "Pixxel", "Dhruva Space", "Bellatrix",
    "GalaxEye", "Digantara", "Log9 Materials", "Chara Technologies",
    # --- Enterprise India / other ---
    "Jio", "Airtel", "Vodafone Idea", "Tata Digital", "Reliance Retail",
    "Aditya Birla", "Mahindra", "Bajaj Auto", "Maruti Suzuki", "Hero MotoCorp",
    "Asian Paints", "ITC", "HUL", "Britannia", "Marico", "Dabur",
    # --- Global capability centres ---
    #
    # The multinationals that do real engineering in Bengaluru, Hyderabad, Pune
    # and Chennai, and hire freshers into it. They were missing from a list that
    # was otherwise a good map of Indian startups, which is why the app could
    # read two thousand jobs without one from a GCC.
    #
    # Almost all of them are on Workday, which has no slug to probe, so most
    # arrive through the careers page step in `discover` or through a pasted
    # link rather than through the slug guesses.
    "NVIDIA", "Hewlett Packard Enterprise", "Dell Technologies", "Marvell",
    "Applied Materials", "Western Digital", "Seagate", "Lam Research", "KLA",
    "Citi", "HSBC", "Standard Chartered", "Bank of America", "Nasdaq", "LSEG",
    "Fidelity Investments", "S&P Global", "Fiserv", "FIS", "Discover Financial",
    "Optum", "UnitedHealth Group", "Medtronic", "Stryker", "AstraZeneca",
    "GSK", "Novartis", "Sanofi", "Zoetis",
    "Tesco", "Lowe's", "Nike", "Unilever", "PepsiCo", "Mondelez",
    "Colgate-Palmolive", "Kimberly-Clark",
    "Shell", "Maersk", "Honeywell", "Caterpillar", "John Deere", "Cummins",
    "Emerson", "Schneider Electric", "ABB", "Bosch", "3M",
    "Rolls-Royce", "Airbus", "Baker Hughes",
    "Thomson Reuters", "Verizon", "Ericsson", "Nokia",
    "Genpact", "Kyndryl", "DXC Technology",
    "Micron Technology", "eBay", "Expedia Group", "Autodesk",
]
