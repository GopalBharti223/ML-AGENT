"""
Country metadata helpers used across the pipeline.

Provides a single shared source of truth for:
  - ISO 3166-1 alpha-2 codes  (for drawing flag icons on charts)
  - canonical display names    (for titles that name the winning country)
  - derived hashtags           (for consistent YouTube description tags)

Name matching is lenient: input is normalized to lowercase alphanumerics
so common World Bank / provider forms like "Korea, Rep." resolve correctly.
"""

import re

# Form as it may appear in data -> (iso2, display name)
_RAW = {
    # Americas
    "united states": ("US", "USA"),
    "usa": ("US", "USA"),
    "us": ("US", "USA"),
    "united states of america": ("US", "USA"),
    "u.s.": ("US", "USA"),
    "u.s.a.": ("US", "USA"),
    "canada": ("CA", "Canada"),
    "mexico": ("MX", "Mexico"),
    "brazil": ("BR", "Brazil"),
    "argentina": ("AR", "Argentina"),
    "chile": ("CL", "Chile"),
    "colombia": ("CO", "Colombia"),
    "peru": ("PE", "Peru"),
    "venezuela": ("VE", "Venezuela"),
    "ecuador": ("EC", "Ecuador"),
    "costa rica": ("CR", "Costa Rica"),
    "panama": ("PA", "Panama"),
    "dominican republic": ("DO", "Dominican Republic"),
    "cuba": ("CU", "Cuba"),
    # Europe
    "united kingdom": ("GB", "UK"),
    "uk": ("GB", "UK"),
    "great britain": ("GB", "UK"),
    "britain": ("GB", "UK"),
    "england": ("GB", "UK"),
    "germany": ("DE", "Germany"),
    "france": ("FR", "France"),
    "italy": ("IT", "Italy"),
    "spain": ("ES", "Spain"),
    "portugal": ("PT", "Portugal"),
    "netherlands": ("NL", "Netherlands"),
    "switzerland": ("CH", "Switzerland"),
    "sweden": ("SE", "Sweden"),
    "norway": ("NO", "Norway"),
    "denmark": ("DK", "Denmark"),
    "finland": ("FI", "Finland"),
    "austria": ("AT", "Austria"),
    "belgium": ("BE", "Belgium"),
    "ireland": ("IE", "Ireland"),
    "greece": ("GR", "Greece"),
    "iceland": ("IS", "Iceland"),
    "luxembourg": ("LU", "Luxembourg"),
    "poland": ("PL", "Poland"),
    "czech republic": ("CZ", "Czech Republic"),
    "czechia": ("CZ", "Czech Republic"),
    "hungary": ("HU", "Hungary"),
    "romania": ("RO", "Romania"),
    "ukraine": ("UA", "Ukraine"),
    # Russia / Caucasus
    "russia": ("RU", "Russia"),
    "russian federation": ("RU", "Russia"),
    "azerbaijan": ("AZ", "Azerbaijan"),
    "georgia": ("GE", "Georgia"),
    "armenia": ("AM", "Armenia"),
    # Asia & Pacific
    "china": ("CN", "China"),
    "india": ("IN", "India"),
    "japan": ("JP", "Japan"),
    "south korea": ("KR", "South Korea"),
    "korea": ("KR", "South Korea"),
    "korea, rep.": ("KR", "South Korea"),
    "republic of korea": ("KR", "South Korea"),
    "north korea": ("KP", "North Korea"),
    "korea, dem. people's rep.": ("KP", "North Korea"),
    "democratic people's republic of korea": ("KP", "North Korea"),
    "dprk": ("KP", "North Korea"),
    "indonesia": ("ID", "Indonesia"),
    "taiwan": ("TW", "Taiwan"),
    "hong kong": ("HK", "Hong Kong"),
    "singapore": ("SG", "Singapore"),
    "thailand": ("TH", "Thailand"),
    "malaysia": ("MY", "Malaysia"),
    "vietnam": ("VN", "Vietnam"),
    "philippines": ("PH", "Philippines"),
    "pakistan": ("PK", "Pakistan"),
    "bangladesh": ("BD", "Bangladesh"),
    "australia": ("AU", "Australia"),
    "new zealand": ("NZ", "New Zealand"),
    "kazakhstan": ("KZ", "Kazakhstan"),
    # Middle East
    "turkey": ("TR", "Turkey"),
    "israel": ("IL", "Israel"),
    "saudi arabia": ("SA", "Saudi Arabia"),
    "united arab emirates": ("AE", "United Arab Emirates"),
    "uae": ("AE", "United Arab Emirates"),
    "qatar": ("QA", "Qatar"),
    "kuwait": ("KW", "Kuwait"),
    "iran": ("IR", "Iran"),
    "iran, islamic rep.": ("IR", "Iran"),
    "iraq": ("IQ", "Iraq"),
    "jordan": ("JO", "Jordan"),
    # Africa
    "egypt": ("EG", "Egypt"),
    "nigeria": ("NG", "Nigeria"),
    "south africa": ("ZA", "South Africa"),
    "kenya": ("KE", "Kenya"),
    "ethiopia": ("ET", "Ethiopia"),
    "ghana": ("GH", "Ghana"),
    "cameroon": ("CM", "Cameroon"),
    "morocco": ("MA", "Morocco"),
    "algeria": ("DZ", "Algeria"),
    "tunisia": ("TN", "Tunisia"),
    # Demonym/adjectival forms so user phrasing like
    # "American military spending vs Chinese" resolves the same
    # as "USA vs China".  Map to the SAME iso2/display as the
    # country name, so flags/titles stay canonical.
    "papua new guinea": ("PG", "Papua New Guinea"),
    "fiji": ("FJ", "Fiji"),
    "solomon islands": ("SB", "Solomon Islands"),
    "vanuatu": ("VU", "Vanuatu"),
    "tonga": ("TO", "Tonga"),
    "samoa": ("WS", "Samoa"),
    "timor-leste": ("TL", "Timor-Leste"),
    "east timor": ("TL", "Timor-Leste"),
    "myanmar": ("MM", "Myanmar"),
    "burma": ("MM", "Myanmar"),
    "nepal": ("NP", "Nepal"),
    "bhutan": ("BT", "Bhutan"),
    "tajikistan": ("TJ", "Tajikistan"),
    "kyrgyzstan": ("KG", "Kyrgyzstan"),
    "uzbekistan": ("UZ", "Uzbekistan"),
    "afghanistan": ("AF", "Afghanistan"),
    "mongolia": ("MN", "Mongolia"),
    "bolivia": ("BO", "Bolivia"),
    "nicaragua": ("NI", "Nicaragua"),
    "guatemala": ("GT", "Guatemala"),
    "el salvador": ("SV", "El Salvador"),
    "haiti": ("HT", "Haiti"),
    "puerto rico": ("PR", "Puerto Rico"),
    "guyana": ("GY", "Guyana"),
    "suriname": ("SR", "Suriname"),
    "albania": ("AL", "Albania"),
    "croatia": ("HR", "Croatia"),
    "bulgaria": ("BG", "Bulgaria"),
    "slovenia": ("SI", "Slovenia"),
    "serbia": ("RS", "Serbia"),
    "bosnia and herzegovina": ("BA", "Bosnia and Herzegovina"),
    "bosnia": ("BA", "Bosnia and Herzegovina"),
    "north macedonia": ("MK", "North Macedonia"),
    "macedonia": ("MK", "North Macedonia"),
    "moldova": ("MD", "Moldova"),
    "cyprus": ("CY", "Cyprus"),
    "new caledonia": ("NC", "New Caledonia"),
    "american": ("US", "USA"),
    "chinese": ("CN", "China"),
    "indian": ("IN", "India"),
    "british": ("GB", "UK"),
    "canadian": ("CA", "Canada"),
    "german": ("DE", "Germany"),
    "french": ("FR", "France"),
    "japanese": ("JP", "Japan"),
    "russian": ("RU", "Russia"),
    "ukrainian": ("UA", "Ukraine"),
    "israeli": ("IL", "Israel"),
    "australian": ("AU", "Australia"),
    "italian": ("IT", "Italy"),
    "spanish": ("ES", "Spain"),
    "mexican": ("MX", "Mexico"),
    "brazilian": ("BR", "Brazil"),
    "dutch": ("NL", "Netherlands"),
    "swedish": ("SE", "Sweden"),
    "norwegian": ("NO", "Norway"),
    "swiss": ("CH", "Switzerland"),
    "polish": ("PL", "Poland"),
    "turkish": ("TR", "Turkey"),
    "iranian": ("IR", "Iran"),
    "pakistani": ("PK", "Pakistan"),
    "bangladeshi": ("BD", "Bangladesh"),
    "egyptian": ("EG", "Egypt"),
    "nigerian": ("NG", "Nigeria"),
    "south african": ("ZA", "South Africa"),
    "south korean": ("KR", "South Korea"),
    "north korean": ("KP", "North Korea"),
    "saudi": ("SA", "Saudi Arabia"),
    "argentine": ("AR", "Argentina"),
    "chilean": ("CL", "Chile"),
    "colombian": ("CO", "Colombia"),
    "peruvian": ("PE", "Peru"),
    "venezuelan": ("VE", "Venezuela"),
    "ecuadorian": ("EC", "Ecuador"),
    "vietnamese": ("VN", "Vietnam"),
    "thai": ("TH", "Thailand"),
    "indonesian": ("ID", "Indonesia"),
    "malaysian": ("MY", "Malaysia"),
    "singaporean": ("SG", "Singapore"),
    "filipino": ("PH", "Philippines"),
    "greek": ("GR", "Greece"),
    "portuguese": ("PT", "Portugal"),
    "irish": ("IE", "Ireland"),
    # Pacific Ring of Fire / seismic-region additions (earthquake
    # country attribution + OWID disaster CSV coverage).
    "papua new guinea": ("PG", "Papua New Guinea"),
    "fiji": ("FJ", "Fiji"),
    "solomon islands": ("SB", "Solomon Islands"),
    "vanuatu": ("VU", "Vanuatu"),
    "tonga": ("TO", "Tonga"),
    "timor-leste": ("TL", "Timor-Leste"),
    "east timor": ("TL", "Timor-Leste"),
    "myanmar": ("MM", "Myanmar"),
    "burma": ("MM", "Myanmar"),
    "nepal": ("NP", "Nepal"),
    "bhutan": ("BT", "Bhutan"),
    "tajikistan": ("TJ", "Tajikistan"),
    "kyrgyzstan": ("KG", "Kyrgyzstan"),
    "afghanistan": ("AF", "Afghanistan"),
    "bolivia": ("BO", "Bolivia"),
    "nicaragua": ("NI", "Nicaragua"),
    "guatemala": ("GT", "Guatemala"),
    "el salvador": ("SV", "El Salvador"),
    "haiti": ("HT", "Haiti"),
    "puerto rico": ("PR", "Puerto Rico"),
    "new caledonia": ("NC", "New Caledonia"),
    "albania": ("AL", "Albania"),
    "croatia": ("HR", "Croatia"),
    "bulgaria": ("BG", "Bulgaria"),
    "slovenia": ("SI", "Slovenia"),
    "serbia": ("RS", "Serbia"),
    "bosnia and herzegovina": ("BA", "Bosnia and Herzegovina"),
    "bosnia": ("BA", "Bosnia and Herzegovina"),
    "cyprus": ("CY", "Cyprus"),
    "samoa": ("WS", "Samoa"),
    "mongolia": ("MN", "Mongolia"),
    "uzbekistan": ("UZ", "Uzbekistan"),
    "north macedonia": ("MK", "North Macedonia"),
    "macedonia": ("MK", "North Macedonia"),
    "moldova": ("MD", "Moldova"),
    "guyana": ("GY", "Guyana"),
    "suriname": ("SR", "Suriname"),
    # ---------------------------------------------------------
         # Aggregate / supranational entities seen in provider rows
    # (Stanford AI Index regions, World Bank aggregates).  Not
    # countries, but they render on charts too -- give them the
    # same consistent flag treatment (flagcdn has eu.png / un.png)
    # instead of silently dropping their icons.
    # ---------------------------------------------------------
    "europe": ("EU", "Europe"),
    "european union": ("EU", "European Union"),
    "world": ("UN", "World"),
    # ---------------------------------------------------------
    # Additional countries (name -> (iso2, display)) that appear
    # in World Bank / provider rows but were missing from the
    # original hand-curated _RAW set.  Without these, the
    # entity-in-data validation gate false-positives: a topic
    # naming "BFA" (ISO3) would be compared against the frame
    # label "Burkina Faso" (full name), and lookup("Burkina
    # Faso") returned None because the name was absent from
    # _RAW -- so the iso2 cross-check in _match_label was
    # skipped and the entity was falsely flagged as missing.
    # ---------------------------------------------------------
    "angola": ("AO", "Angola"),
    "aruba": ("AW", "Aruba"),
    "barbados": ("BB", "Barbados"),
    "burkina faso": ("BF", "Burkina Faso"),
    "bahrain": ("BH", "Bahrain"),
    "benin": ("BJ", "Benin"),
    "brunei": ("BN", "Brunei"),
    "bahamas": ("BS", "Bahamas"),
    "botswana": ("BW", "Botswana"),
    "belarus": ("BY", "Belarus"),
    "belize": ("BZ", "Belize"),
    "congo, dem. rep.": ("CD", "Congo, Dem. Rep."),
    "democratic republic of the congo": ("CD", "Congo, Dem. Rep."),
    "congo, rep.": ("CG", "Congo, Rep."),
    "republic of the congo": ("CG", "Congo, Rep."),
    "cote d'ivoire": ("CI", "Cote d'Ivoire"),
    "caboverde": ("CV", "Cabo Verde"),
    "cabo verde": ("CV", "Cabo Verde"),
    "curacao": ("CW", "Curacao"),
    "djibouti": ("DJ", "Djibouti"),
    "central african republic": ("CF", "Central African Republic"),
    "estonia": ("EE", "Estonia"),
    "eritrea": ("ER", "Eritrea"),
    "falkland islands": ("FK", "Falkland Islands"),
    "micronesia, fed. st.": ("FM", "Micronesia, Fed. St."),
    "micronesia": ("FM", "Micronesia, Fed. St."),
    "gabon": ("GA", "Gabon"),
    "french guiana": ("GF", "French Guiana"),
    "guinea": ("GN", "Guinea"),
    "guinea-bissau": ("GW", "Guinea-Bissau"),
    "guinea bissau": ("GW", "Guinea-Bissau"),
    "guadeloupe": ("GP", "Guadeloupe"),
    "equatorial guinea": ("GQ", "Equatorial Guinea"),
    "honduras": ("HN", "Honduras"),
    "jamaica": ("JM", "Jamaica"),
    "cambodia": ("KH", "Cambodia"),
    "korea, dem. people's rep.": ("KP", "North Korea"),
    "democratic people's republic of korea": ("KP", "North Korea"),
    "lao pdr": ("LA", "Lao PDR"),
    "lao people's democratic republic": ("LA", "Lao PDR"),
    "lebanon": ("LB", "Lebanon"),
    "sri lanka": ("LK", "Sri Lanka"),
    "liberia": ("LR", "Liberia"),
    "lesotho": ("LS", "Lesotho"),
    "lithuania": ("LT", "Lithuania"),
    "latvia": ("LV", "Latvia"),
    "libya": ("LY", "Libya"),
    "montenegro": ("ME", "Montenegro"),
    "madagascar": ("MG", "Madagascar"),
    "mali": ("ML", "Mali"),
    "macao": ("MO", "Macao"),
    "martinique": ("MQ", "Martinique"),
    "malta": ("MT", "Malta"),
    "mauritius": ("MU", "Mauritius"),
    "malawi": ("MW", "Malawi"),
    "mozambique": ("MZ", "Mozambique"),
    "namibia": ("NA", "Namibia"),
    "niger": ("NE", "Niger"),
    "oman": ("OM", "Oman"),  # also in Middle East section below, deduped by _NORM
    "west bank": ("PS", "West Bank"),
    "state of palestine": ("PS", "West Bank"),
    "palestine": ("PS", "West Bank"),
    "paraguay": ("PY", "Paraguay"),
    "reunion": ("RE", "Reunion"),
    "rwanda": ("RW", "Rwanda"),
    "sudan": ("SD", "Sudan"),
    "slovak republic": ("SK", "Slovak Republic"),
    "slovakia": ("SK", "Slovak Republic"),
    "sierra leone": ("SL", "Sierra Leone"),
    "senegal": ("SN", "Senegal"),
    "somalia": ("SO", "Somalia"),
    "somalia, fed. rep.": ("SO", "Somalia"),
    "south sudan": ("SS", "South Sudan"),
    "syrian arab republic": ("SY", "Syrian Arab Republic"),
    "syria": ("SY", "Syrian Arab Republic"),
    "eswatini": ("SZ", "Eswatini"),
    "swaziland": ("SZ", "Eswatini"),
    "chad": ("TD", "Chad"),
    "togo": ("TG", "Togo"),
    "turkmenistan": ("TM", "Turkmenistan"),
    "trinidad and tobago": ("TT", "Trinidad and Tobago"),
    "tanzania": ("TZ", "Tanzania"),
    "uganda": ("UG", "Uganda"),
    "uruguay": ("UY", "Uruguay"),
    "british virgin islands": ("VG", "British Virgin Islands"),
    "yemen": ("YE", "Yemen"),
    "mayotte": ("YT", "Mayotte"),
    "zambia": ("ZM", "Zambia"),
    "zimbabwe": ("ZW", "Zimbabwe"),
}

# Display names widely recognized enough to include directly in a title.
WIDELY_RECOGNIZED = {
    "USA", "China", "India", "Japan", "Germany", "UK", "Russia", "France",
    "Brazil", "Canada", "Italy", "Spain", "Australia", "Mexico", "South Korea",
    "Netherlands", "Switzerland", "Sweden", "Poland", "Indonesia", "Turkey",
    "Saudi Arabia", "Argentina",
}

def _normalize_key(name: str) -> str:
    """Collapse to lowercase alphanumeric tokens for fuzzy matching."""
    return re.sub(r"[^a-zA-Z0-9]+", " ", str(name)).strip().lower()



# Auto-generated gazetteer gap fill (World Bank country
# list audit -- see _audit_gaps.py).  MUST stay above the
# _NORM / _BY_ISO2 derivations below.
_RAW.update({
    'american samoa': ('AS', 'American Samoa'),
    'andorra': ('AD', 'Andorra'),
    'antigua and barbuda': ('AG', 'Antigua and Barbuda'),
    'bahamas the': ('BS', 'Bahamas, The'),
    'bermuda': ('BM', 'Bermuda'),
    'brunei darussalam': ('BN', 'Brunei Darussalam'),
    'burundi': ('BI', 'Burundi'),
    'cayman islands': ('KY', 'Cayman Islands'),
    'channel islands': ('JG', 'Channel Islands'),
    'comoros': ('KM', 'Comoros'),
    'cote divoire': ('CI', "Cote d'Ivoire"),
    'dominica': ('DM', 'Dominica'),
    'egypt arab rep': ('EG', 'Egypt, Arab Rep.'),
    'faroe islands': ('FO', 'Faroe Islands'),
    'french polynesia': ('PF', 'French Polynesia'),
    'gambia': ('GM', 'Gambia, The'),
    'gambia the': ('GM', 'Gambia, The'),
    'gibraltar': ('GI', 'Gibraltar'),
    'greenland': ('GL', 'Greenland'),
    'grenada': ('GD', 'Grenada'),
    'guam': ('GU', 'Guam'),
    'hong kong sar china': ('HK', 'Hong Kong SAR, China'),
    'isle of man': ('IM', 'Isle of Man'),
    'ivory coast': ('CI', "Cote d'Ivoire"),
    'kiribati': ('KI', 'Kiribati'),
    'kosovo': ('XK', 'Kosovo'),
    'kyrgyz republic': ('KG', 'Kyrgyz Republic'),
    'lao': ('LA', 'Lao PDR'),
    'laos': ('LA', 'Lao PDR'),
    'liechtenstein': ('LI', 'Liechtenstein'),
    'macao sar china': ('MO', 'Macao SAR, China'),
    'maldives': ('MV', 'Maldives'),
    'marshall islands': ('MH', 'Marshall Islands'),
    'mauritania': ('MR', 'Mauritania'),
    'micronesia fed sts': ('FM', 'Micronesia, Fed. Sts.'),
    'monaco': ('MC', 'Monaco'),
    'naoero': ('NR', 'Naoero'),
    'nauru': ('NR', 'Naoero'),
    'northern mariana islands': ('MP', 'Northern Mariana Islands'),
    'palau': ('PW', 'Palau'),
    'puerto rico us': ('PR', 'Puerto Rico (US)'),
    'saint kitts and nevis': ('KN', 'St. Kitts and Nevis'),
    'saint lucia': ('LC', 'St. Lucia'),
    'saint vincent and the grenadines': ('VC', 'St. Vincent and the Grenadines'),
    'san marino': ('SM', 'San Marino'),
    'sao tome and principe': ('ST', 'Sao Tome and Principe'),
    'seychelles': ('SC', 'Seychelles'),
    'sint maarten': ('SX', 'Sint Maarten (Dutch part)'),
    'sint maarten dutch part': ('SX', 'Sint Maarten (Dutch part)'),
    'st kitts and nevis': ('KN', 'St. Kitts and Nevis'),
    'st lucia': ('LC', 'St. Lucia'),
    'st martin french part': ('MF', 'St. Martin (French part)'),
    'st vincent and the grenadines': ('VC', 'St. Vincent and the Grenadines'),
    'the gambia': ('GM', 'Gambia, The'),
    'turkiye': ('TR', 'Turkiye'),
    'turks and caicos islands': ('TC', 'Turks and Caicos Islands'),
    'tuvalu': ('TV', 'Tuvalu'),
    'u s virgin islands': ('VI', 'Virgin Islands (U.S.)'),
    'us virgin islands': ('VI', 'Virgin Islands (U.S.)'),
    'venezuela rb': ('VE', 'Venezuela, RB'),
    'viet nam': ('VN', 'Viet Nam'),
    'virgin islands u s': ('VI', 'Virgin Islands (U.S.)'),
    'west bank and gaza': ('PS', 'West Bank and Gaza'),
    'yemen rep': ('YE', 'Yemen, Rep.'),
})

# ---------------------------------------------------------
# Gazetteer gap fill #2 -- OWID entity sweep.
#
# The World Bank audit above (see _audit_gazetteer.py) reports
# ZERO gaps, but OWID emits ~20 further territories that the
# World Bank does not carry at all.  A live random-mode run
# selected `owid/population` whose top rows were Tokelau and
# Bonaire, and the entity-in-data gate blocked it with
# "[BES, TKL] NOT present ... (labels: ... Tokelau)" -- the two
# names were visibly IN the frame but unresolvable, so the
# canonical-ISO2 comparison in _match_label was skipped.
#
# This is the same Bug-1 class as Burkina Faso / Malawi / Latvia,
# one data source over.  Every entry below is a real ISO 3166-1
# territory/dependency that OWID actually publishes, with its
# true alpha-2 and alpha-3.
# ---------------------------------------------------------
_RAW.update({
    'akrotiri and dhekelia': ('AX', 'Akrotiri and Dhekelia'),
    'anguilla': ('AI', 'Anguilla'),
    'bonaire sint eustatius and saba': ('BQ', 'Bonaire, Sint Eustatius and Saba'),
    'caribbean netherlands': ('BQ', 'Bonaire, Sint Eustatius and Saba'),
    'bonaire': ('BQ', 'Bonaire, Sint Eustatius and Saba'),
    'cook islands': ('CK', 'Cook Islands'),
    'cabo verde': ('CV', 'Cabo Verde'),
    'cape verde': ('CV', 'Cabo Verde'),
    'guernsey': ('GG', 'Guernsey'),
    'jersey': ('JE', 'Jersey'),
    'micronesia country': ('FM', 'Micronesia, Fed. Sts.'),
    'montserrat': ('MS', 'Montserrat'),
    'niue': ('NU', 'Niue'),
    'saint barthelemy': ('BL', 'Saint Barthelemy'),
    'st barthelemy': ('BL', 'Saint Barthelemy'),
    'saint helena': ('SH', 'Saint Helena'),
    'st helena': ('SH', 'Saint Helena'),
    'saint pierre and miquelon': ('PM', 'Saint Pierre and Miquelon'),
    'st pierre and miquelon': ('PM', 'Saint Pierre and Miquelon'),
    'svalbard and jan mayen': ('SJ', 'Svalbard and Jan Mayen'),
    'tokelau': ('TK', 'Tokelau'),
    'us virgin islands': ('VI', 'Virgin Islands (U.S.)'),
    'united states virgin islands': ('VI', 'Virgin Islands (U.S.)'),
    'vatican': ('VA', 'Vatican City'),
    'vatican city': ('VA', 'Vatican City'),
    'holy see': ('VA', 'Vatican City'),
    'wallis and futuna': ('WF', 'Wallis and Futuna'),
    'western sahara': ('EH', 'Western Sahara'),
    'saint martin french part': ('MF', 'St. Martin (French part)'),
    'st martin french part': ('MF', 'St. Martin (French part)'),
})

_NORM = {_normalize_key(form): meta for form, meta in _RAW.items()}

# ---------------------------------------------------------
# ISO 3166-1 alpha-3 -> alpha-2.
#
# Providers index chart rows by CODE, not name (World Bank's
# `countryiso3code` yields "USA"/"CHN"/"DEU"...), so flag and
# icon lookups must accept alpha-3 directly -- previously only
# "usa" worked because it doubled as a name alias, which is
# why charts showed a flag on the US bar alone.
# ---------------------------------------------------------

_ALPHA3_TO_ALPHA2 = {
    # Comprehensive ISO 3166-1 alpha-3 -> alpha-2 covering the
    # full UN-member + widely-used territory set, so ANY World
    # Bank / provider row resolves (production hit gaps like
    # MDA / ALB / GUY with the original hand-curated subset).
    # Americas
    "USA": "US", "CAN": "CA", "MEX": "MX", "BRA": "BR", "ARG": "AR",
    "CHL": "CL", "COL": "CO", "PER": "PE", "VEN": "VE", "ECU": "EC",
    "CRI": "CR", "PAN": "PA", "DOM": "DO", "CUB": "CU", "BOL": "BO",
    "PRY": "PY", "URY": "UY", "GTM": "GT", "HND": "HN", "SLV": "SV",
    "NIC": "NI", "JAM": "JM", "HTI": "HT", "TTO": "TT", "BLZ": "BZ",
    "BHS": "BS", "BRB": "BB", "GUY": "GY", "SUR": "SR",
    # Europe
    "GBR": "GB", "DEU": "DE", "FRA": "FR", "ITA": "IT", "ESP": "ES",
    "PRT": "PT", "NLD": "NL", "CHE": "CH", "SWE": "SE", "NOR": "NO",
    "DNK": "DK", "FIN": "FI", "AUT": "AT", "BEL": "BE", "IRL": "IE",
    "GRC": "GR", "ISL": "IS", "LUX": "LU", "POL": "PL", "CZE": "CZ",
    "HUN": "HU", "ROU": "RO", "UKR": "UA", "MLT": "MT", "CYP": "CY",
    "SVK": "SK", "SVN": "SI", "HRV": "HR", "BIH": "BA", "SRB": "RS",
    "MNE": "ME", "MKD": "MK", "ALB": "AL", "MDA": "MD", "BGR": "BG",
    "LTU": "LT", "LVA": "LV", "EST": "EE", "BLR": "BY",
    # Russia / Caucasus / Central Asia
    "RUS": "RU", "AZE": "AZ", "GEO": "GE", "ARM": "AM",
    "KAZ": "KZ", "UZB": "UZ", "TKM": "TM", "KGZ": "KG", "TJK": "TJ",
    # Asia & Pacific
    "CHN": "CN", "IND": "IN", "JPN": "JP", "KOR": "KR", "PRK": "KP",
    "IDN": "ID", "TWN": "TW", "HKG": "HK", "SGP": "SG", "THA": "TH",
    "MYS": "MY", "VNM": "VN", "PHL": "PH", "PAK": "PK", "BGD": "BD",
    "AUS": "AU", "NZL": "NZ", "LKA": "LK", "NPL": "NP", "BTN": "BT",
    "MMR": "MM", "KHM": "KH", "LAO": "LA", "MNG": "MN", "AFG": "AF",
    "BRN": "BN", "FJI": "FJ", "PNG": "PG",
    # Middle East
    "TUR": "TR", "ISR": "IL", "SAU": "SA", "ARE": "AE", "QAT": "QA",
    "KWT": "KW", "IRN": "IR", "IRQ": "IQ", "JOR": "JO", "LBN": "LB",
    "SYR": "SY", "YEM": "YE", "OMN": "OM", "BHR": "BH", "PSE": "PS",
    # Africa
    "EGY": "EG", "NGA": "NG", "ZAF": "ZA", "KEN": "KE", "ETH": "ET",
    "GHA": "GH", "CMR": "CM", "MAR": "MA", "DZA": "DZ", "TUN": "TN",
    "LBY": "LY", "SDN": "SD", "TZA": "TZ", "UGA": "UG", "RWA": "RW",
    "SEN": "SN", "CIV": "CI", "MLI": "ML", "NER": "NE", "TCD": "TD",
    "BFA": "BF", "GIN": "GN", "SLE": "SL", "LBR": "LR", "BEN": "BJ",
    "TGO": "TG", "GAB": "GA", "COG": "CG", "COD": "CD", "CAF": "CF",
    "AGO": "AO", "ZMB": "ZM", "ZWE": "ZW", "MWI": "MW", "MOZ": "MZ",
    "BWA": "BW", "NAM": "NA", "MDG": "MG", "MUS": "MU", "SOM": "SO",
    "ERI": "ER", "DJI": "DJ", "GNQ": "GQ", "SSD": "SS", "LSO": "LS",
    "SWZ": "SZ", "CPV": "CV",
    # Territories / special cases seen in provider rows
    "MYT": "YT", "GUF": "GF", "GLP": "GP", "MTQ": "MQ",
    "REU": "RE", "MAC": "MO", "PRI": "PR", "CUW": "CW",
    "ABW": "AW", "VGB": "VG", "FLK": "FK", "NCL": "NC",
}


# Auto-generated alpha-3 gap fill (World Bank country list
# audit -- see _audit_gaps.py).  Includes COM, MRT, STP, TLS,
# GMB and 40 others provider rows actually use.
_ALPHA3_TO_ALPHA2.update({
    'AND': 'AD',
    'ASM': 'AS',
    'ATG': 'AG',
    'BDI': 'BI',
    'BMU': 'BM',
    'CHI': 'JG',
    'COM': 'KM',
    'CYM': 'KY',
    'DMA': 'DM',
    'FRO': 'FO',
    'FSM': 'FM',
    'GIB': 'GI',
    'GMB': 'GM',
    'GNB': 'GW',
    'GRD': 'GD',
    'GRL': 'GL',
    'GUM': 'GU',
    'IMN': 'IM',
    'KIR': 'KI',
    'KNA': 'KN',
    'LCA': 'LC',
    'LIE': 'LI',
    'MAF': 'MF',
    'MCO': 'MC',
    'MDV': 'MV',
    'MHL': 'MH',
    'MNP': 'MP',
    'MRT': 'MR',
    'NRU': 'NR',
    'PLW': 'PW',
    'PYF': 'PF',
    'SLB': 'SB',
    'SMR': 'SM',
    'STP': 'ST',
    'SXM': 'SX',
    'SYC': 'SC',
    'TCA': 'TC',
    'TLS': 'TL',
    'TON': 'TO',
    'TUV': 'TV',
    'VCT': 'VC',
    'VIR': 'VI',
    'VUT': 'VU',
    'WSM': 'WS',
    'XKX': 'XK',
})

# Alpha-3 gap fill #2 -- the OWID territories above.  The World
# Bank audit returns zero gaps, but OWID's own entity list is a
# separate universe and these codes appear in provider frames.
# Without them lookup('TKL') is None, which silently disables the
# canonical-ISO2 cross-check in VisualEngine._match_label and
# makes the entity-in-data gate report a false mismatch.
_ALPHA3_TO_ALPHA2.update({
    'AIA': 'AI',
    'AXC': 'AX',
    'BLM': 'BL',
    # Bonaire: ISO 3166-1 alpha-3 is BES.  BQ1 is the
    # "old code" variant seen in some statistical releases; both
    # are accepted so either provider spelling resolves.
    'BES': 'BQ',
    'BQ1': 'BQ',
    'CXR': 'CX',
    'COK': 'CK',
    'ESH': 'EH',
    'FLK': 'FK',
    'GGY': 'GG',
    'IMN': 'IM',
    'JEY': 'JE',
    'MSR': 'MS',
    'NIU': 'NU',
    'PCN': 'PM',
    'PRK': 'KP',
    'SHN': 'SH',
    'SJM': 'SJ',
    'TKL': 'TK',
    'VAT': 'VA',
    'WLF': 'WF',
})

# iso2 (upper) -> canonical (iso2, display). Built from _RAW so a
# code-form lookup returns the SAME display name as a name-form
# lookup ("DEU" -> Germany, "GB" -> UK, ...).
_BY_ISO2 = {}
for _raw_form, (_raw_iso2, _raw_display) in _RAW.items():
    _BY_ISO2.setdefault(_raw_iso2.upper(), (_raw_iso2, _raw_display))
del _raw_form, _raw_iso2, _raw_display


def lookup(name) -> dict:
    """Return dict(iso2, display) for a name OR an ISO code, else None.

    Accepts, in priority order:
      1. Any known name form        ("Germany", "korea, rep.")
      2. ISO 3166-1 alpha-2 code    ("DE", "kr")
      3. ISO 3166-1 alpha-3 code    ("DEU", "chn")
    """
    entry = _NORM.get(_normalize_key(name))

    if entry:
        return {"iso2": entry[0], "display": entry[1]}

    raw = str(name or "").strip()

    if re.fullmatch(r"[A-Za-z]{2}", raw):

        hit = _BY_ISO2.get(raw.upper())

        if hit:
            return {"iso2": hit[0], "display": hit[1]}

    elif re.fullmatch(r"[A-Za-z]{3}", raw):

        iso2 = _ALPHA3_TO_ALPHA2.get(raw.upper())

        if iso2:

            hit = _BY_ISO2.get(iso2)

            # Even an unmapped iso2 still yields a usable
            # flag code -- production rows like MDA/ALB/GUY
            # previously fell through here and lost their
            # flags just because no display name existed.
            return {
                "iso2": (
                    hit[0] if hit else iso2
                ),
                "display": (
                    hit[1] if hit else None
                ),
            }

    return None


def iso2_code(name) -> str | None:
    """Lowercase ISO 3166-1 alpha-2 code (as used by flag CDNs), else None."""
    entry = lookup(name)
    return entry["iso2"].lower() if entry else None


def display_name(name) -> str | None:
    entry = lookup(name)
    return entry["display"] if entry else None


def name_forms() -> frozenset:
    """
    Normalized NAME-form keys known to lookup() -- aliases like
    "usa", "uk", "korea, rep." INCLUDED; the bare ISO2/ISO3
    code fallback EXCLUDED.  Used by offline country-token
    detection so common English words that collide with ISO
    codes ("are" -> ARE/UAE, "and" -> AND/Andorra, "can" ->
    CAN/Canada) can never produce a false country hit.
    """
    return frozenset(_NORM.keys())


def is_widely_recognized(name) -> bool:
    display = display_name(name)
    return bool(display) and display in WIDELY_RECOGNIZED


def country_hashtag(name) -> str | None:
    """A #Tag derived from the country's display name, or None."""
    display = display_name(name)
    if not display:
        return None
    tokens = re.findall(r"[A-Za-z0-9]+", display)
    tag = "".join(tok[:1].upper() + tok[1:] for tok in tokens)
    return "#" + tag