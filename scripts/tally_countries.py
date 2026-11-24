# /// script
# requires-python = ">=3.10"
# dependencies = ["pycountry", "geonamescache"]
# ///
"""Tally which countries a set of GitHub users come from.

Reads a JSON file of GitHub user objects (as returned by the GitHub
``/users/<login>`` API), maps each user's free-text ``location`` field to a
country, and writes a JSON list of ``{"country": ..., "count": ...}`` rows
sorted by count (descending).

Resolution works entirely offline, in this order:

1. Hand-written overrides (``OVERRIDES`` below, plus ``--overrides FILE``)
2. The whole string is a country name / ISO code ("Germany", "UK", "DE")
3. Any comma/slash-separated part is a country name ("Berlin, Germany")
4. A trailing 2-letter code, disambiguated by the city before it
   ("Portland, OR" -> US, "Delft, NL" -> Netherlands)
5. A US/Canadian/Australian/... state or province ("Ontario")
6. A city from the GeoNames database (most populous match wins)
7. Country names or large cities (100k+) appearing anywhere in the text

Anything left over ("Earth", "127.0.0.1", "Europe") is reported as
unresolved and left out of the tally.

Usage:
    uv run scripts/tally_countries.py maintainer-info.json -o maintainer-countries.json
    uv run scripts/tally_countries.py maintainer-info.json --report   # audit matches

Check the --report output before using the numbers: free text is messy, and
new data will need new entries in OVERRIDES.
"""

import argparse
import collections
import json
import re
import sys
import unicodedata

import geonamescache
import pycountry

US, UK = "United States", "United Kingdom"


def norm(s):
    """Lowercase, strip accents and collapse whitespace."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.lower()).strip(" .")


# --- Country names -> canonical name ----------------------------------------

COUNTRY = {}
for c in pycountry.countries:
    name = getattr(c, "common_name", None) or c.name
    for alias in (c.name, getattr(c, "official_name", None), getattr(c, "common_name", None), c.alpha_3):
        if alias:
            COUNTRY[norm(alias)] = name

CODE2 = {c.alpha_2: getattr(c, "common_name", None) or c.name for c in pycountry.countries}

COUNTRY_ALIASES = {
    "usa": US, "us": US, "u.s.": US, "u.s.a.": US, "united states of america": US,
    "america": US, "the united states": US,
    "uk": UK, "u.k.": UK, "the uk": UK, "england": UK, "scotland": UK, "wales": UK,
    "northern ireland": UK, "great britain": UK, "britain": UK, "gb": UK,
    "deutschland": "Germany", "brasil": "Brazil", "espana": "Spain", "italia": "Italy",
    "schweiz": "Switzerland", "suisse": "Switzerland", "nederland": "Netherlands",
    "the netherlands": "Netherlands", "holland": "Netherlands", "osterreich": "Austria",
    "sverige": "Sweden", "norge": "Norway", "danmark": "Denmark", "suomi": "Finland",
    "polska": "Poland", "belgique": "Belgium", "belgie": "Belgium", "mexico": "Mexico",
    "russia": "Russian Federation", "south korea": "Korea, Republic of",
    "korea": "Korea, Republic of", "republic of korea": "Korea, Republic of",
    "czech republic": "Czechia", "czechia": "Czechia", "iran": "Iran", "vietnam": "Viet Nam",
    "turkey": "Türkiye", "turkiye": "Türkiye", "taiwan": "Taiwan",
    "prc": "China", "p.r. china": "China", "p.r.china": "China",
    "hong kong": "Hong Kong", "hk": "Hong Kong", "aotearoa": "New Zealand", "nz": "New Zealand",
    "uae": "United Arab Emirates", "ksa": "Saudi Arabia", "bolivia": "Bolivia",
    "venezuela": "Venezuela", "tanzania": "Tanzania", "moldova": "Moldova",
    "palestine": "Palestine", "syria": "Syria", "laos": "Laos",
}
COUNTRY.update({norm(k): v for k, v in COUNTRY_ALIASES.items()})

# Short or awkward pycountry names -> the names people expect to read.
PRETTY = {
    "Korea, Republic of": "South Korea", "Russian Federation": "Russia", "Viet Nam": "Vietnam",
    "Iran, Islamic Republic of": "Iran", "Taiwan, Province of China": "Taiwan",
    "Bolivia, Plurinational State of": "Bolivia", "Venezuela, Bolivarian Republic of": "Venezuela",
    "Tanzania, United Republic of": "Tanzania", "Moldova, Republic of": "Moldova",
    "Palestine, State of": "Palestine", "Syrian Arab Republic": "Syria",
    "Lao People's Democratic Republic": "Laos", "Czechia": "Czech Republic",
}


def pretty(name):
    return PRETTY.get(name, name)


# Country tokens of 3 characters or fewer that are safe to match inside longer text.
SHORT_COUNTRY_TOKENS = {"usa", "uk", "us", "uae", "prc", "gb", "nz", "hk"}

# --- States / provinces ------------------------------------------------------
# (country code, whether to also match 2-letter codes like "WA" / "ON")

REGION = {}
for cc, with_codes in (("US", True), ("CA", True), ("AU", True),
                       ("IN", False), ("DE", False), ("CN", False), ("BR", False)):
    country_name = US if cc == "US" else CODE2[cc]
    for s in pycountry.subdivisions.get(country_code=cc):
        REGION.setdefault(norm(s.name), country_name)
        if with_codes:
            REGION.setdefault(norm(s.code.split("-")[1]), country_name)

REGION.update({norm(k): v for k, v in {
    "bay area": US, "silicon valley": US, "socal": US, "norcal": US, "pnw": US,
    "washington dc": US, "dc": US, "d.c.": US, "nyc": US, "sf": US, "la": US, "texas": US,
    "ontario": "Canada", "quebec": "Canada", "bavaria": "Germany", "bayern": "Germany",
    "catalonia": "Spain", "catalunya": "Spain",
}.items()})

US_CODES = {s.code.split("-")[1] for s in pycountry.subdivisions.get(country_code="US")}

# --- Cities ------------------------------------------------------------------
# name -> (country, population); the most populous city with a name wins.

CITY = {}
for c in geonamescache.GeonamesCache(min_city_population=15000).get_cities().values():
    for name in [c["name"]] + [a for a in c.get("alternatenames", []) if a.isascii()]:
        key = norm(name)
        if len(key) < 3:
            continue
        if key not in CITY or c["population"] > CITY[key][1]:
            CITY[key] = (CODE2.get(c["countrycode"], c["countrycode"]), c["population"])

# Ambiguous names where the most populous match is not the one people mean.
CITY_PREFERENCES = {
    "cambridge": UK, "london": UK, "oxford": UK, "manchester": UK, "birmingham": UK,
    "paris": "France", "brest": "France", "berlin": "Germany",
    "barcelona": "Spain", "valencia": "Spain", "madeira": "Portugal",
    "delft": "Netherlands", "noordwijk": "Netherlands",
    "vancouver": "Canada", "melbourne": "Australia", "sydney": "Australia",
    "bangalore": "India", "bengaluru": "India", "cordoba": "Argentina",
    "boston": US, "portland": US, "richmond": US, "palo alto": US, "berkeley": US,
    "princeton": US, "pasadena": US, "los alamos": US, "ithaca": US, "urbana": US,
    "champaign": US, "stanford": US, "santa clara": US, "santa cruz": US, "san mateo": US,
}
for key, name in CITY_PREFERENCES.items():
    CITY[key] = (name, 10**9)

# --- Overrides ---------------------------------------------------------------
# Exact location strings (compared after norm()) that the rules above get
# wrong or miss. None means "deliberately unresolved". These were built from
# the conda-forge maintainer list; extend them for your own data.

OVERRIDES = {
    # Misspellings, abbreviations, small towns missing from GeoNames
    "Isreal": "Israel", "Gemany": "Germany", "Fairbanks Alaksa": US, "The U.S.": US,
    "NY": US, "TX": US, "SF": US, "SF Bay Area": US, "Greater NYC area": US, "MTV": US,
    "City of Angels": US, "Chicagoland": US, "Central Illinois": US, "Western Mass": US,
    "Ironton OH": US, "Lemont IL": US, "Ames Iowa": US, "Bend OR": US, "Flagstaff AZ": US,
    "Yorktown Heights": US, "CA94025": US, "Ames Research Center, Moffett Field, CA 94035": US,
    "40°47'11.2\"N 119°12'24.2\"W": US,
    "BC": "Canada", "Thetford Mines": "Canada", "DE": "Germany",
    "Holmfirth": UK, "Oxfordshire": UK, "Devon": UK, "West Sussex": UK, "West Yorkshire": UK,
    "Cymru": UK,
    "Villigen": "Switzerland", "CERN": "Switzerland",
    "Houten": "Netherlands", "Schoonhoven": "Netherlands", "Cuijk": "Netherlands",
    "Zeuthen": "Germany", "Ploen": "Germany", "Havixbeck": "Germany",
    "Garching Forschungszentrum": "Germany",
    "Saclay": "France", "Elsass": "France", "Ecole polytechnique": "France",
    "Sorbonne University Pierre and Marie Curie Campus": "France",
    "Københavns Universitet": "Denmark", "Kamchatka": "Russia",
    "Ribeira Grande, Azores": "Portugal", "Recife - PE": "Brazil", "Atlanta, Georgia": US,
    "Vienna ⋄ Helsinki ⋄ Quito": "Austria",
    # Institutions
    "Janelia": US, "GSFC": US, "Goddard Space Flight Center": US, "NOAA NCWCP": US,
    "Clark Center": US, "Duke University": US, "University of Alaska Fairbanks": US,
    "University of Central Florida": US, "Oak Ridge National Laboratory": US,
    "Memorial Sloan Kettering Cancer Center": US,
    # Jokes / ambiguous strings that would otherwise match a real place
    "Sturgeon Pond, SV": None, "Atlantis": None, "Data Center": None,
    "Planet Earth, most likely": None, "where time series is observed & valued": None,
    "Gaia, Sayshell Sector": None, "Angola/IN": None,
    "Kota Kahuana y La Cumbrecita: los pies en el suelo, y andar por las nubes": None,
}

# Checked before norm(), which drops non-Latin scripts entirely.
RAW_OVERRIDES = {"Байкаловск": "Russia"}


# --- Resolution --------------------------------------------------------------

def resolve(loc, overrides):
    """Return the country for a free-text location, or None."""
    if loc in RAW_OVERRIDES:
        return RAW_OVERRIDES[loc]
    n = norm(loc)
    if not n:
        return None
    if n in overrides:
        return overrides[n]

    # Whole string is a country, or a bare 2-letter code (US states win).
    if n in COUNTRY:
        return pretty(COUNTRY[n])
    if len(n) == 2 and n.upper() in US_CODES:
        return US
    if len(n) == 2 and n.upper() in CODE2:
        return pretty(CODE2[n.upper()])

    parts = [p.strip() for p in re.split(r"[,/|;·•\-–—()]+| and | & ", n) if p.strip()]

    # Any part is a country name (right-most first).
    for p in reversed(parts):
        if p in COUNTRY and (len(p) > 3 or p in SHORT_COUNTRY_TOKENS):
            return pretty(COUNTRY[p])

    # Trailing 2-letter code: state/province vs ISO country, decided by the city part.
    if len(parts) > 1 and len(parts[-1]) == 2:
        p = parts[-1]
        candidates = [x for x in (REGION.get(p), CODE2.get(p.upper())) if x]
        city_country = CITY.get(parts[0], (None,))[0]
        if city_country in candidates:
            return pretty(city_country)
        if p.upper() in US_CODES and REGION.get(p) == US:
            return US
        if candidates:
            return pretty(candidates[-1])

    # State / province name.
    for p in reversed(parts):
        if p in REGION and not (len(p) == 2 and len(parts) == 1):
            return pretty(REGION[p])

    # City.
    for p in parts:
        if p in CITY:
            return pretty(CITY[p][0])

    # Country names or large cities anywhere in the text.
    words = re.findall(r"[a-z][a-z.]+", n)
    for w in reversed(words):
        if w in COUNTRY and (len(w) > 3 or w in ("usa", "uk", "ksa")):
            return pretty(COUNTRY[w])
    for i in range(len(words)):
        for j in (3, 2, 1):
            key = " ".join(words[i:i + j])
            if len(key) >= 4 and key in CITY and CITY[key][1] >= 100_000:
                return pretty(CITY[key][0])

    if len(parts) == 1 and parts[0].upper() in CODE2:
        return pretty(CODE2[parts[0].upper()])
    return None


def load_locations(path, field):
    """Return {user: location} from a dict keyed by login or a list of user objects."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    records = data.items() if isinstance(data, dict) else (
        (r.get("login", i), r) for i, r in enumerate(data))
    return {user: (r.get(field) or "").strip()
            for user, r in records if isinstance(r, dict)}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("input", help="JSON file of GitHub user objects")
    parser.add_argument("-o", "--output", help="write the tally here (default: stdout)")
    parser.add_argument("--field", default="location", help="field holding the location text")
    parser.add_argument("--count-key", default="count",
                        help='name of the count field in output rows (default: "count")')
    parser.add_argument("--overrides", metavar="FILE",
                        help='extra JSON {"location string": "Country" or null} overrides')
    parser.add_argument("--report", action="store_true",
                        help="print which raw locations went into each country, plus the unresolved ones")
    args = parser.parse_args()

    overrides = {norm(k): v for k, v in OVERRIDES.items()}
    if args.overrides:
        with open(args.overrides, encoding="utf-8") as f:
            overrides.update({norm(k): v for k, v in json.load(f).items()})

    locations = load_locations(args.input, args.field)
    resolved, unresolved = {}, collections.Counter()
    for user, loc in locations.items():
        if not loc:
            continue
        country = resolve(loc, overrides)
        if country:
            resolved[user] = country
        else:
            unresolved[loc] += 1
    tally = collections.Counter(resolved.values())

    if args.report:
        by_country = collections.defaultdict(collections.Counter)
        for user, country in resolved.items():
            by_country[country][locations[user]] += 1
        for country, n in tally.most_common():
            examples = "; ".join(loc for loc, _ in by_country[country].most_common(25))
            print(f"== {country} ({n}): {examples}")
        print(f"\nUNRESOLVED ({sum(unresolved.values())}):")
        for loc, n in unresolved.most_common():
            print(f"  {n:3d}  {loc!r}")
        return

    rows = [{"country": c, args.count_key: n} for c, n in tally.most_common()]
    out = json.dumps(rows, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out)
    else:
        print(out)

    with_location = sum(1 for loc in locations.values() if loc)
    print(f"{len(locations)} users, {with_location} with a location, "
          f"{len(resolved)} resolved to {len(tally)} countries, "
          f"{sum(unresolved.values())} unresolved", file=sys.stderr)


if __name__ == "__main__":
    main()
