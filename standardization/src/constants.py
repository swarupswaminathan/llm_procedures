# constants.py
'''
Controlled vocabularies for glaucoma/cataract PROCEDURE label standardization.

These maps encode the rules described in configs/prompt_config.py:
- R5_PROCEDURE_NORMALIZATION  (expand shorthand, keep acronyms)
- R6_PROCEDURE_DETAIL_PRESERVATION (details in parentheses; device model/size kept in name)
- R7_UNCERTAINTY_RULE (possible / ~)
- R8_ALLOWED_PROCEDURE_INFERENCE (pseudophakia/PCO/IOL -> CEIOL, aphakia -> CE, tube -> tube shunt)

The canonical output form for each procedure is chosen here in ONE place 
so it can be tuned to your institution's conventions.
Edit the right-hand side of PROCEDURE_SYNONYMS to change canonical output.
'''

import re

# ============================================================
# Canonical procedure names (customize this list to your institution's conventions)
# ============================================================

CANONICAL_PROCEDURES = {
    "trabeculectomy",
    "bleb revision",
    "Trab 360",
    "Express removal",
    "BGI",
    "BGI revision",
    "AGI",
    "AGI revision",
    "tube shunt",
    "tube revision",
    "Tube removal",
    "CP250",
    "CP350",
    "Sion",
    "KDB",
    "GATT",
    "iTrack",
    "canaloplasty",
    "goniotomy",
    "MIGS",
    "Omni",
    "CPC",
    "MP",
    "ECP",
    "Durysta",
    "iDose",
    "SLT",
    "ALT",
    "LPI",
    "iridoplasty",
    "laser",
    "YAG capsulotomy",
    "iStent",
    "Hydrus",
    "Xen",
    "Xen revision",
    "Xen removal",
    "CEIOL",
    "CE",
    "bleb needling",
    "goniosynechialysis",
    "adhesion lysis",
    "choroidal drainage",
}

# ============================================================
# Synonym / abbreviation map (lowercased variant -> canonical output)
# Derived from PROCEDURE_ABBREVIATIONS and R5/R8 in configs/prompt_config.py
# Customize this list to your institution's conventions.
# ============================================================

PROCEDURE_SYNONYMS = {
    # --- Trabeculectomy family ---
    "trabeculectomy": "trabeculectomy",
    "trab": "trabeculectomy",
    "trabs": "trabeculectomy",
    "filter surgery": "trabeculectomy",
    "filtration surgery": "trabeculectomy",
    "filtering surgery": "trabeculectomy",
    "filtration": "trabeculectomy",
    "bleb revision": "bleb revision",
    "revision bleb": "bleb revision",
    "trabeculectomy revision": "bleb revision",
    "revision trabeculectomy": "bleb revision",
    "revision trab": "bleb revision",
    "trab revision": "bleb revision",
    "trabeculectomy bleb revision": "bleb revision",
    "trab bleb revision": "bleb revision",
    "trabeculectomy flap revision": "bleb revision",
    "trab flap revision": "bleb revision",

    # Trab 360 -- a distinct procedure. The "360" is part of the name, not a degree
    # detail, so variants are normalized to the single token "trab360" before detail
    # extraction (see TRAB360_PATTERN).
    "trab 360": "Trab 360",
    "trabeculectomy 360": "Trab 360",
    "trab360": "Trab 360",
    "trabeculectomy360": "Trab 360",

    # --- Express (a trabeculectomy with an Ex-PRESS shunt under the flap) ---
    # Resolves to trabeculectomy; "express" is preserved as a parenthetical detail
    # via PROCEDURE_IMPLIED_DETAILS.
    "express": "trabeculectomy",
    "express shunt": "trabeculectomy",
    "trab express": "trabeculectomy",
    "trabeculectomy express": "trabeculectomy",
    "express removal": "Express removal",
    "express explant": "Express removal",
    "express explantation": "Express removal",

    # --- Baerveldt glaucoma implant ---
    "bgi": "BGI",
    "bvt": "BGI",
    "baerveldt": "BGI",
    "baerveldt glaucoma implant": "BGI",
    "bgi revision": "BGI revision",
    "bvt revision": "BGI revision",
    "baerveldt glaucoma implant revision": "BGI revision",
    "baerveldt revision": "BGI revision",

    # --- Ahmed glaucoma implant ---
    "agi": "AGI",
    "ahmed": "AGI",
    "ahmed glaucoma implant": "AGI",
    "fp7": "AGI FP7",
    "ahmed fp7": "AGI FP7",
    "agv": "AGI",
    "agi revision": "AGI revision",
    "ahmed revision": "AGI revision",
    "ahmed glaucoma implant revision": "AGI revision",
    "agv revision": "AGI revision",
    "ahmed fp7 revision": "AGI FP7 revision",
    "agi fp7 revision": "AGI FP7 revision",

    # --- Generic glaucoma drainage implant / tube shunt (R8: tube -> tube shunt) ---
    "gdi": "tube shunt",
    "tube": "tube shunt",
    "tube shunt": "tube shunt",
    "glaucoma drainage implant": "tube shunt",
    "glaucoma drainage device": "tube shunt",
    "aqueous shunt": "tube shunt",
    "gdi": "tube shunt",
    "gdd": "tube shunt",
    "tube revision": "tube revision",
    "shunt revision": "tube revision",
    "tube shunt revision": "tube revision",
    # Reposition / trim variants resolve to tube revision; the subtype is preserved as
    # a parenthetical detail via PROCEDURE_IMPLIED_DETAILS (e.g. "tube trim" ->
    # "tube revision (trimming)").
    "tube repositioning": "tube revision",
    "tube reposition": "tube revision",
    "tube repos": "tube revision",
    "move tube": "tube revision",
    "move tubes": "tube revision",
    "move tubes to": "tube revision",
    "tube trimming": "tube revision",
    "tube trim": "tube revision",
    "tube removal": "Tube removal",
    "tube explant": "Tube removal",
    "tube explantation": "Tube removal",

    # --- Clearpath ---
    "cp250": "CP250",
    "cp 250": "CP250",
    "clearpath 250": "CP250",
    "ahmed cp250": "CP250",
    "cp350": "CP350",
    "cp 350": "CP350",
    "clearpath 350": "CP350",
    "ahmed cp350": "CP350",

    # --- MIGS / goniotomy / canaloplasty ---
    # "MIGS" is the umbrella term used when the specific device is not named.
    "migs": "MIGS",
    "minimally invasive glaucoma surgery": "MIGS",
    "sion": "Sion",
    "sion blade goniotomy": "Sion",
    "kdb": "KDB",
    "kahook dual blade": "KDB",
    "kahook": "KDB",
    "gatt": "GATT",
    "goniotomy": "goniotomy",
    "gonio": "goniotomy",
    "itrack": "iTrack",
    "canaloplasty": "canaloplasty",
    "omni": "Omni",
    "gsl": "goniosynechialysis",
    "goniosynechialysis": "goniosynechialysis",
    "adhesion lysis": "adhesion lysis",
    "lysis": "adhesion lysis",
    "lysis synechiae to iol": "adhesion lysis",
    "lysis iris adhesions": "adhesion lysis",
    "dissection pupillary membrane": "adhesion lysis",
    "istent": "iStent",
    "i-stent": "iStent",
    "hydrus": "Hydrus",
    "xen": "Xen",
    "xen gel stent": "Xen",
    "xen removal": "Xen removal",
    "xen explant": "Xen removal",
    "xen explantation": "Xen removal",


    # --- Laser procedures ---
    # A laser whose type is never specified. Every named laser below is matched first,
    # and these generic variants only match a COMPLETE procedure name (see
    # WHOLE_NAME_ONLY_VARIANTS), so a phrase that merely begins with "laser" -- such as
    # the R1-excluded "laser suture lysis" -- is left unmapped for review instead of
    # being turned into a laser procedure.
    "laser": "laser",
    "laser surgery": "laser",
    "laser surgeries": "laser",
    "laser procedure": "laser",
    "laser treatment": "laser",

    "cpc": "CPC",
    "cyclophotocoagulation": "CPC",
    "diode laser": "CPC",
    "mp": "MP",
    "mpcpc": "MP CPC",
    "mp cpc": "MP CPC",
    "micropulse": "MP",
    "micropulse cpc": "MP CPC",
    "transscleral cpc": "CPC",
    "ecp": "ECP",
    "endocyclophotocoagulation": "ECP",

    "slt": "SLT",
    "ltp": "SLT",
    "selective laser trabeculoplasty": "SLT",
    "laser trabeculoplasty": "SLT",
    "alt": "ALT",
    "argon laser trabeculoplasty": "ALT",
    # In a glaucoma label the argon laser means trabeculoplasty, but the phrase names an
    # instrument rather than a procedure, so it is accepted only as a complete name (see
    # WHOLE_NAME_ONLY_VARIANTS). "argon laser iridoplasty" has its own synonym below.
    "argon laser": "ALT",

    # Iridotomy family -- laser / peripheral iridotomy all map to LPI.
    "lpi": "LPI",
    "laser peripheral iridotomy": "LPI",
    "li": "LPI",
    "laser iridotomy": "LPI",
    "pi": "LPI",
    "peripheral iridotomy": "LPI",
    "iridotomy": "LPI",
    "iridectomy": "LPI",

    # Iridoplasty (ALPI) is a different laser than LPI / ALT.
    "iridoplasty": "iridoplasty",
    "laser iridoplasty": "iridoplasty",
    "argon laser iridoplasty": "iridoplasty",
    "argon iridoplasty": "iridoplasty",
    "alpi": "iridoplasty",
    "laser peripheral iridoplasty": "iridoplasty",
    "argon laser peripheral iridoplasty": "iridoplasty",

    # YAG laser capsulotomy family.
    "yag": "YAG capsulotomy",
    "yag capsulotomy": "YAG capsulotomy",
    "yag laser capsulotomy": "YAG capsulotomy",
    "yag laser": "YAG capsulotomy",
    "ylc": "YAG capsulotomy",
    "capsulotomy": "YAG capsulotomy",
    "posterior capsulotomy": "YAG capsulotomy",

    # --- Sustained drug release ---
    "durysta": "Durysta",
    "idose": "iDose",
    "idose tr": "iDose",

    # --- Cataract surgery (R8: pseudophakia/PCO/IOL -> CEIOL, aphakia -> CE) ---
    "ceiol": "CEIOL",
    "ce/iol": "CEIOL",
    "phaco/iol": "CEIOL",
    "phaco iol": "CEIOL",
    "phacoiol": "CEIOL",
    "cataract surgery": "CEIOL",
    "cataract removal": "CEIOL",
    "cataract": "CEIOL",
    "pseudophakia": "CEIOL",
    "pseudophakic": "CEIOL",
    "pco": "CEIOL",
    "posterior capsular opacification": "CEIOL",
    "iol": "CEIOL",
    "pciol": "CEIOL",
    "ce/pciol": "CEIOL",
    "pciol placement": "CEIOL",
    "mfiol": "CEIOL",
    "aciol": "CEIOL",
    "phaco": "CEIOL",
    "phacoemulsification": "CEIOL",
    "ce": "CE",
    "cataract extraction": "CE",
    "aphakia": "CE",
    "aphakic": "CE",

    # --- Revision / other ---
    "needling": "needling",
    "bleb needling": "bleb needling",
    "xen needling": "Xen needling",
    "xen revision": "Xen revision",


    # --- Choroidal drainage ---
    # NOTE: connector words like "of" are stripped by clean_name_text before lookup,
    # so "drainage of choroidals" arrives here as "drainage choroidals".
    "choroidal drainage": "choroidal drainage",
    "choroidal drain": "choroidal drainage",
    "choroidal effusion drainage": "choroidal drainage",
    "choroidal hemorrhage drainage": "choroidal drainage",
    "choroidal tap": "choroidal drainage",
    "drainage choroidal": "choroidal drainage",
    "drainage choroidals": "choroidal drainage",
    "drainage choroidal effusion": "choroidal drainage",
    "drainage choroidal effusions": "choroidal drainage",
    "drainage choroidal hemorrhage": "choroidal drainage",

    # --- Excluded (R1) ---
    # Recognized so they can be dropped from the output rather than left as flagged
    # unmapped text. See EXCLUDED_CANONICALS.
    "ac paracentesis": "AC paracentesis",
    "a.c. paracentesis": "AC paracentesis",
    "a.c paracentesis": "AC paracentesis",
    "ac tap": "AC paracentesis",
    "anterior chamber paracentesis": "AC paracentesis",
    "paracentesis": "AC paracentesis",
    "iol exchange": "iol exchange",
    "iol repositioning": "iol repositioning",
    "iol revision": "iol revision",
    "sceral patch graft": "sceral patch graft",
    "spg": "sceral patch graft",
    "patch graft": "sceral patch graft",
}

# When a synonym variant encodes a subtype of the canonical procedure, attach that
# subtype as a parenthetical detail rather than baking it into the procedure name.
# Example: "tube repositioning" -> name "tube revision", detail "repositioning".
PROCEDURE_IMPLIED_DETAILS = {
    "move tube": ["repositioning"],
    "move tubes": ["repositioning"],
    "move tubes to": ["repositioning"],
    "tube repositioning": ["repositioning"],
    "tube reposition": ["repositioning"],
    "tube repos": ["repositioning"],
    "tube trimming": ["trimming"],
    "tube trim": ["trimming"],
    "express": ["express"],
    "express shunt": ["express"],
    "trab express": ["express"],
    "trabeculectomy express": ["express"],
}

# Subtype tokens that may trail an already-resolved "tube revision" name
# ("tube revision repositioning" -> "tube revision (repositioning)").
TUBE_REVISION_SUBTYPE_SYNONYMS = {
    "repositioning": "repositioning",
    "reposition": "repositioning",
    "repos": "repositioning",
    "trimming": "trimming",
    "trim": "trimming",
}

# Device / technique details that may trail an already-resolved "trabeculectomy"
# ("trab express" -> "trabeculectomy (express)").
TRABECULECTOMY_DETAIL_SYNONYMS = {
    "express": "express",
}

# Procedures that appear in labels but must not appear in the standardized output
# (R1 non-surgical events). Synonyms above resolve to these canonicals; the parser
# then drops any component whose name is in this set.
EXCLUDED_CANONICALS = {
    "AC paracentesis",
    "iol exchange",
    "iol replacement",
    "iol revision",
    "sceral patch graft",
}

# Variants that name the instrument, or the procedure only vaguely, so they are accepted
# just as a COMPLETE procedure name and never as the leading part of a longer one.
# Procedure names normally resolve on their leading tokens ("KDB goniotomy" -> "KDB"),
# which for a word as broad as "laser" would quietly relabel anything starting with it --
# including "laser suture lysis", which R1 excludes. Such phrases stay unmapped and
# flagged for review. "lysis" on its own is adhesion lysis, but as a trailing word it
# is usually part of a different name (suture lysis).
WHOLE_NAME_ONLY_VARIANTS = {
    "laser",
    "laser surgery",
    "laser surgeries",
    "laser procedure",
    "laser treatment",
    "argon laser",
    "lysis",
}

# Dash characters that turn up in pasted note text: hyphen, non-breaking hyphen, en
# dash, em dash. A dash is usually punctuation inside a single name ("i-stent", "5-FU",
# "BGI-350"); the one case where it separates two procedures ("phaco-Hydrus") is handled
# by utils.split_combined_components. Escaped so it stays safe anywhere in a character
# class, including after another range such as [\s...].
HYPHEN_CHARS = r"\-\u2010\u2011\u2013\u2014"

# Model / plate-size identifiers that stay part of the NAME (R6), not parentheses.
MODEL_TOKENS = {"fp7", "250", "350"}

# ============================================================
# Space-separated combined procedures (R9)
# ============================================================

# A combination is sometimes written with nothing but a space between the procedures
# ("Phaco iStent" == "phaco + iStent"). utils.split_space_separated_components finds the
# boundaries by matching PROCEDURE_SYNONYMS, and the vocabularies below say when two
# neighboring matches are really ONE procedure -- named twice, or named and described.

# Canonical names that are interchangeable descriptions of one procedure, so two of
# them side by side are a single procedure named twice rather than a combination
# ("CE for congenital cataract", "AGI FP7").
EQUIVALENT_CANONICAL_GROUPS = [
    {"CE", "CEIOL"},
    {"AGI", "AGI FP7", "BGI", "CP250", "CP350"},
]

# Combined (same-day) procedures that imply an IOL was placed. A neighboring CE is
# then upgraded to CEIOL so "CE/MIGS" == "CEIOL/MIGS" and "CE/GSL" == "CEIOL/GSL".
CE_UPGRADES_TO_CEIOL_WITH = {
    "MIGS",
    "goniosynechialysis",
}

# Every procedure involving a drainage tube, used to recognize when a generic tube name
# is just re-describing a specific implant ("Ahmed glaucoma drainage implant").
TUBE_SHUNT_PROCEDURES = {
    "AGI",
    "AGI FP7",
    "BGI",
    "CP250",
    "CP350",
    "Express removal",
    "tube shunt",
    "tube revision",
    "Tube removal",
}

# Every procedure performed with a laser, used to recognize when a generic "laser" is
# just re-describing the specific one beside it ("SLT laser", "CPC laser").
LASER_PROCEDURES = {
    "SLT",
    "ALT",
    "LPI",
    "iridoplasty",
    "YAG capsulotomy",
    "CPC",
    "MP",
    "MP CPC",
    "ECP",
    "laser",
}

# The bare word "tube" describes an existing shunt far more often than it names a
# second procedure ("sulcus tube", "trimming of tube", "tube exposure"), so it never
# opens a new procedure; the explicit names ("tube shunt", "GDI") still can.
NEVER_STARTS_PROCEDURE = {"tube"}

# Tokens that merely describe the procedure they sit next to whenever that procedure
# already implies them: "KDB goniotomy" and "Express trab" are each one procedure,
# but "phaco goniotomy" is two. Keyed by vocabulary variant -> absorbing canonicals.
ABSORBED_BY_ADJACENT_CANONICAL = {
    "goniotomy": {"KDB", "Sion", "GATT", "Omni", "iTrack", "canaloplasty", "goniotomy"},
    "gonio": {"KDB", "Sion", "GATT", "Omni", "iTrack", "canaloplasty", "goniotomy"},
    "canaloplasty": {"GATT", "Omni", "iTrack", "canaloplasty"},
    "needling": {
        "trabeculectomy",
        "bleb revision",
        "Xen",
        "Xen revision",
        "bleb needling",
        "needling",
    },
    # Express and trabeculectomy are the same procedure once Express maps to
    # trabeculectomy; _same_procedure already collapses "Express trab" / "trab Express".
    # Generic laser / tube naming yields to the specific procedure beside it.
    "laser": LASER_PROCEDURES,
    "laser surgery": LASER_PROCEDURES,
    "laser surgeries": LASER_PROCEDURES,
    "laser procedure": LASER_PROCEDURES,
    "laser treatment": LASER_PROCEDURES,
    "gdi": TUBE_SHUNT_PROCEDURES,
    "tube shunt": TUBE_SHUNT_PROCEDURES,
    "glaucoma drainage implant": TUBE_SHUNT_PROCEDURES,
    "glaucoma drainage device": TUBE_SHUNT_PROCEDURES,
}

# ============================================================
# Procedure DETAIL vocabulary (R6) -- rendered inside parentheses
# ============================================================

# Location / surgical approach / implant position (lowercased variant -> canonical)
DETAIL_LOCATION_SYNONYMS = {
    "temp": "temporal",
    "temporal": "temporal",
    "nas": "nasal",
    "nasal": "nasal",
    "sup": "superior",
    "superior": "superior",
    "superiorly": "superior",
    "inf": "inferior",
    "inferior": "inferior",
    "inferiorly": "inferior",
    "sulcus": "sulcus",
    "pars plana": "pars plana",
    "anterior chamber": "anterior chamber",
}

# Quadrant abbreviations -- matched case-sensitively as upper-case tokens or full words.
DETAIL_QUADRANT_WORDS = {
    "superotemporal": "ST",
    "inferonasal": "IN",
    "superonasal": "SN",
    "inferotemporal": "IT",
}
DETAIL_QUADRANT_ABBREV = {
    "STQ": "STQ",
    "INQ": "INQ",
    "SNQ": "SNQ",
    "ITQ": "ITQ",
    "ST": "ST",
    "IN": "IN",
    "SN": "SN",
    "IT": "IT",
}

# Degrees of treatment considered valid detail values (avoids catching dates/doses).
DETAIL_DEGREE_VALUES = {"90", "180", "270", "360"}

# Antimetabolite modifiers stay attached to the preceding procedure NAME
# (e.g. "trabeculectomy MMC", "needling 5FU injection") rather than being separate
# procedures. 5FU always renders as "5FU injection". When one of these is the only
# token (e.g. a bare "5FU"), it becomes the procedure name on its own.
# A documented dose ("10 mg 5FU", "5FU 10mg") is consumed with the drug and dropped.
# Ordered so output is deterministic when more than one is present.
ANTIMETABOLITE_DOSE = r"(?:\d+(?:\.\d+)?\s*(?:mg|mcg|ug|µg|ml|cc)\b\s*)"
ANTIMETABOLITE_MODIFIERS = [
    (
        rf"(?:{ANTIMETABOLITE_DOSE})?\b(?:mmc|mitomycin[-\s]?c)\b(?:\s*{ANTIMETABOLITE_DOSE})?",
        "MMC",
    ),
    (
        rf"(?:{ANTIMETABOLITE_DOSE})?\b(?:5[-\s]?fu|5[-\s]?fluorouracil|fluorouracil)\b(?:\s*{ANTIMETABOLITE_DOSE})?",
        "5FU injection",
    ),
]

# Regex fragment matching any antimetabolite (used to detach it from a combined
# separator so "trabeculectomy + MMC" / "Trab+5FU" stay a single procedure).
ANTIMETABOLITE_ALT = r"(?:mmc|mitomycin[-\s]?c|5[-\s]?fu|5[-\s]?fluorouracil|fluorouracil)"

# "Trab 360" is a distinct procedure whose "360" would otherwise be stripped as a
# degree detail. Collapse all variants ("trab 360", "trab360", "trabeculectomy 360",
# "trabeculectomy360") to the single token "trab360" BEFORE detail extraction so the
# "360" stays part of the name and resolves via the synonym map.
TRAB360_PATTERN = re.compile(r"\b(?:trab|trabeculectomy)\s*360\b", re.I)

# ============================================================
# Uncertainty (R7)
# ============================================================

# Leading tokens / phrases that indicate uncertainty about whether the procedure
# occurred. Multi-word phrases are supported and matched as a leading unit.
POSSIBLE_TOKENS = {
    "possible",
    "possibly",
    "likely",
    "probable",
    "probably",
    "?",
    "questionable",
    "presumed",
    "reportedly",
    "may have had",
    "may have",
    "may had",
    "concern for",
    "history of possible",
    "h/o possible",
    "s/p possible",
    "suspected",
    "?possible",
}

POSSIBLE_PREFIX = "possible"

# ============================================================
# Status / history prefixes to strip (not part of the procedure name)
# ============================================================

STATUS_PREFIXES = [
    "s/p",
    "status post",
    "status-post",
    "sp",
    "h/o",
    "hx of",
    "history of",
    "prior",
    "s/",
    "recommended",
    "recommended for",
    "recommend",
    "recommend for",
    "plan",
    "plan for",
    "schedule",
    "schedule for",
    "repeat",
]

# ============================================================
# Laterality tokens (already resolved by column; stripped from label text)
# ============================================================

LATERALITY_TOKENS = {"od", "os", "ou"}
LATERALITY_UNKNOWN_PLACEHOLDER = "(laterality unknown)"

# ============================================================
# "None" / empty tokens (R11)
# ============================================================

NONE_TOKENS = {
    "none",
    "no",
    "n/a",
    "na",
    "not applicable",
    "no prior procedures",
    "no procedures",
    "no procedure",
    "no glaucoma procedures",
    "nothing",
    "-",
    "--",
}

# ============================================================
# Combined-procedure separators (R9) -- same-day procedures joined by "/"
# ============================================================

# "with", "w/", "plus", "&", "+", and "/" (only when not between digits) are treated
# as combined-procedure separators. Handled in utils.split_combined_components.
COMBINED_SEPARATOR_WORDS = ["combined with", "with", "w/", "plus"]
