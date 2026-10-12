"""
Tests for procedure-label standardization.

Run from the standardization directory with:
    python -m pytest tests/test_procedures.py
"""

import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.procedure_standardization import standardize_procedure_label  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("test_procedure_standardizer.log", mode="w"),
    ],
)
logger = logging.getLogger("test_procedures")


def std(label, label_type="prior"):
    result = standardize_procedure_label(label, label_type)
    logger.info("input=%r type=%s -> %r", label, label_type, result["standardized_procedure_list"])
    return result["standardized_procedure_list"]


# ------------------------------------------------------------
# R5 - normalization (expand shorthand, keep acronyms)
# ------------------------------------------------------------

@pytest.mark.parametrize(
    "label,expected",
    [
        ("trab", "trabeculectomy"),
        ("Trab MMC 3/2018", "trabeculectomy MMC 3/2018"),
        ("Trabeculectomy + MMC 2/23/2018", "trabeculectomy MMC 2/23/2018"),
        ("trabeculectomy with mmc 2019", "trabeculectomy MMC 2019"),
        ("Trab+5FU", "trabeculectomy 5FU injection"),
        ("Trabeculectomy 5FU", "trabeculectomy 5FU injection"),
        ("Needling 5FU 8/9/2024", "needling 5FU injection 8/9/2024"),
        ("5FU", "5FU injection"),
        ("5FU 8/9/2024", "5FU injection 8/9/2024"),
        # A dose on 5FU/MMC is adjunct detail, not a second procedure.
        ("Bleb needling w/ 10 mg 5FU", "bleb needling 5FU injection"),
        ("Bleb needling with 10 mg 5FU", "bleb needling 5FU injection"),
        ("Bleb needling 10 mg 5FU", "bleb needling 5FU injection"),
        ("Bleb needling w/ 5FU", "bleb needling 5FU injection"),
        ("needling 5FU 10 mg", "needling 5FU injection"),
        ("Trabeculectomy + 0.4 mg MMC", "trabeculectomy MMC"),
        ("Trab 360", "Trab 360"),
        ("trabeculectomy 360", "Trab 360"),
        ("trab360", "Trab 360"),
        ("trabeculectomy360", "Trab 360"),
        ("Trab 360 5/2021", "Trab 360 5/2021"),
        # A trabeculectomy revision is named for the bleb it revises.
        ("bleb revision 3/2022", "bleb revision 3/2022"),
        ("trabeculectomy revision 2017", "bleb revision 2017"),
        ("Revision Trabeculectomy 2017", "bleb revision 2017"),
        ("trab revision", "bleb revision"),
        ("revision of trab 2017", "bleb revision 2017"),
        ("trabeculectomy bleb revision", "bleb revision"),
        ("trab flap revision 5/2020", "bleb revision 5/2020"),
        ("bleb revision MMC 3/2022", "bleb revision MMC 3/2022"),
        ("cataract surgery", "CEIOL"),
        # An unspecified laser is its own generic procedure.
        ("laser", "laser"),
        ("Laser surgery 2019", "laser 2019"),
        ("laser procedure", "laser"),
        ("laser OU 6/2015", "laser 6/2015"),
        ("possible laser", "possible laser"),
        ("laser x2", "laser (x2)"),
        # A named laser is never reduced to the generic one.
        ("laser peripheral iridotomy", "LPI"),
        ("YAG laser 2021", "YAG capsulotomy 2021"),
        ("LTP 2018", "SLT 2018"),
        ("laser trabeculoplasty", "SLT"),
        ("selective laser trabeculoplasty 180", "SLT (180)"),
        ("argon laser 2001", "ALT 2001"),
        ("argon laser trabeculoplasty", "ALT"),
        ("laser iridoplasty", "iridoplasty"),
        ("iridoplasty", "iridoplasty"),
        ("ALPI", "iridoplasty"),
        ("argon laser iridoplasty", "iridoplasty"),
        ("adhesion lysis", "adhesion lysis"),
        ("lysis synechiae to IOL", "adhesion lysis"),
        ("lysis iris adhesions", "adhesion lysis"),
        ("lysis", "adhesion lysis"),
        ("SLT temp", "SLT (temporal)"),
        ("SLT nasal 1/9/2019", "SLT (nasal) 1/9/2019"),
    ],
)
def test_normalization(label, expected):
    assert std(label) == expected


def test_status_prefix_stripped():
    assert std("s/p SLT 6/2015") == "SLT 6/2015"


def test_fuzzy_typo_correction():
    assert std("trabeculctomy 2019") == "trabeculectomy 2019"


# ------------------------------------------------------------
# R4 - date normalization
# ------------------------------------------------------------

@pytest.mark.parametrize(
    "label,expected",
    [
        ("SLT 1/16/19", "SLT 1/16/2019"),
        ("SLT 5/5/15", "SLT 5/5/2015"),
        ("SLT 6/2015", "SLT 6/2015"),
        ("SLT 2015", "SLT 2015"),
        # Year/Year is a mis-printed single date -> keep the first year.
        ("CEIOL 2018/2019", "CEIOL 2018"),
    ],
)
def test_date_normalization(label, expected):
    assert std(label) == expected


# ------------------------------------------------------------
# R6 - detail preservation (parentheses) + device model kept in name
# ------------------------------------------------------------

@pytest.mark.parametrize(
    "label,expected",
    [
        ("Omni 360/180 2/10/23", "Omni (360/180) 2/10/2023"),
        ("Ahmed sulcus 2/2024", "AGI (sulcus) 2/2024"),
        ("AGI in anterior chamber OS 10/3/18", "AGI (anterior chamber) 10/3/2018"),
        ("Ahmed FP7 sulcus STQ 5/5/15", "AGI FP7 (STQ, sulcus) 5/5/2015"),
        ("BGI 350 pars plana STQ 2/2020", "BGI 350 (pars plana, STQ) 2/2020"),
        # "with" splits off a non-procedure/excluded fragment; keep its location detail.
        ("BGI with patch graft in the sulcus", "BGI (sulcus)"),
        ("BGI with sulcus", "BGI (sulcus)"),
        ("Ahmed with patch graft in anterior chamber", "AGI (anterior chamber)"),
    ],
)
def test_detail_preservation(label, expected):
    assert std(label) == expected


def test_outcome_comment_dropped():
    # R6: treatment outcome/efficacy comments are not preserved.
    assert std("SLT (did not work)") == "SLT"


@pytest.mark.parametrize(
    "label,expected",
    [
        # A slash inside a parenthetical is commentary, not a second procedure.
        ("CPC (mod/heavy treatment needed) 12-14 spots", "CPC"),
        ("CPC (mod/heavy treatment needed)", "CPC"),
        ("CPC 12-14 spots", "CPC"),
        ("CPC (did not work)", "CPC"),
    ],
)
def test_cpc_treatment_notes_discarded(label, expected):
    assert std(label) == expected


# ------------------------------------------------------------
# R7 - uncertainty (possible / ~)
# ------------------------------------------------------------

@pytest.mark.parametrize(
    "label,expected",
    [
        ("? trab", "possible trabeculectomy"),
        ("likely prior SLT", "possible SLT"),
        ("cataract surgery ~1990s", "CEIOL ~1990s"),
        ("trab 2000?", "trabeculectomy ~2000"),
        ("tube shunt 2010s", "tube shunt ~2010s"),
    ],
)
def test_uncertainty(label, expected):
    assert std(label) == expected


def test_laterality_unknown_placeholder_preserved():
    assert std("possible ALT (laterality unknown)") == "possible ALT (laterality unknown)"


def test_laterality_unknown_shares_parenthetical_with_details():
    # The marker is split out from a shared parenthetical, keeping the real details.
    assert std("SLT (x3, laterality unknown)") == "SLT (x3) (laterality unknown)"
    assert std("SLT (laterality unknown, x3)") == "SLT (x3) (laterality unknown)"


# ------------------------------------------------------------
# R9 - combined same-day procedures joined with "/"
# ------------------------------------------------------------

@pytest.mark.parametrize(
    "label,expected",
    [
        ("phaco + goniotomy 6/12/2024", "CEIOL/goniotomy 6/12/2024"),
        ("CEIOL with KDB", "CEIOL/KDB"),
        ("phaco + Omni 360/180 2/10/23", "CEIOL/Omni (360/180) 2/10/2023"),
        ("phaco/IOL+AGI in anterior chamber (10/3/18)", "AGI (anterior chamber)/CEIOL 10/3/2018"),
        # Unspecified MIGS is its own procedure; CE beside it implies an IOL.
        ("CE/MIGS", "CEIOL/MIGS"),
        ("CE/MIGS 2020", "CEIOL/MIGS 2020"),
        ("phaco/MIGS", "CEIOL/MIGS"),
        ("CEIOL/MIGS", "CEIOL/MIGS"),
        ("CE + MIGS", "CEIOL/MIGS"),
        ("MIGS", "MIGS"),
        # GSL beside CE implies an IOL, same as MIGS.
        ("CE/GSL", "CEIOL/goniosynechialysis"),
        ("CEIOL/GSL", "CEIOL/goniosynechialysis"),
        ("CE with GSL", "CEIOL/goniosynechialysis"),
        ("GSL", "goniosynechialysis"),
        # "cataract extraction" is CE and "phaco" is CEIOL; together they are one CEIOL.
        ("cataract extraction with Phaco", "CEIOL"),
        ("CE with phaco", "CEIOL"),
        ("CE/CEIOL/GATT", "CEIOL/GATT"),
        ("phaco with cataract extraction", "CEIOL"),
        # Without an IOL/phaco signal, cataract extraction stays CE.
        ("GATT 360 with cataract extraction", "CE/GATT (360)"),
    ],
)
def test_combined_procedures(label, expected):
    assert std(label) == expected


@pytest.mark.parametrize(
    "label,expected",
    [
        # AC paracentesis is an R1-excluded non-surgical event: drop it, keep the rest.
        ("AC paracentesis", "None"),
        ("paracentesis", "None"),
        ("anterior chamber paracentesis", "None"),
        ("SLT, AC paracentesis", "SLT"),
        ("CEIOL, AC paracentesis 2020", "CEIOL"),
        ("AC paracentesis OD 5/5/15, trabeculectomy", "trabeculectomy"),
        ("trabeculectomy + AC paracentesis 2019", "trabeculectomy 2019"),
        ("possible AC paracentesis", "None"),
        ("patch graft", "None"),
        ("BGI with patch graft", "BGI"),
    ],
)
def test_excluded_ac_paracentesis(label, expected):
    assert std(label) == expected


def test_excluded_ac_paracentesis_is_not_a_failed_match():
    # Dropping an excluded procedure is intentional, not an unmapped failure.
    result = standardize_procedure_label("SLT, AC paracentesis", "prior")
    assert result["standardized_procedure_list"] == "SLT"
    assert result["failed_match"] is False


@pytest.mark.parametrize(
    "label,expected",
    [
        # A dash between two procedure names is a combined-procedure separator.
        ("phaco-hydrus", "CEIOL/Hydrus"),
        ("phaco-Hydrus 6/2020", "CEIOL/Hydrus 6/2020"),
        ("phaco - goniotomy 2024", "CEIOL/goniotomy 2024"),
        ("SLT-LPI", "LPI/SLT"),
        ("trab-CEIOL 2020", "CEIOL/trabeculectomy 2020"),
        # Every dash in a chain separates.
        ("phaco-KDB-goniotomy", "CEIOL/KDB"),
        # En dashes are pasted in from notes too.
        ("phaco\u2013hydrus", "CEIOL/Hydrus"),
    ],
)
def test_dash_separated_combined_procedures(label, expected):
    assert std(label) == expected


@pytest.mark.parametrize(
    "label,expected",
    [
        # A dash inside a single name is punctuation, not a separator: only a dash with a
        # procedure name on BOTH sides separates.
        ("i-stent", "iStent"),
        ("I-Stent 2019", "iStent 2019"),
        ("tube-shunt", "tube shunt"),
        ("Ex-PRESS trab 7/2011", "trabeculectomy (express) 7/2011"),
        ("YAG-capsulotomy", "YAG capsulotomy"),
        ("trab-MMC 3/2018", "trabeculectomy MMC 3/2018"),
        ("trab-5FU", "trabeculectomy 5FU injection"),
        ("mitomycin-c trab", "trabeculectomy MMC"),
        # The lens implant suffix is part of the cataract procedure, dash or slash.
        ("phaco-IOL", "CEIOL"),
        ("CE-PCIOL 3/25/21", "CEIOL 3/25/2021"),
        # A dash may also just introduce the details, or sit inside a year range.
        ("Ahmed FP7 - sulcus 5/5/15", "AGI FP7 (sulcus) 5/5/2015"),
        ("SLT - temporal 6/2015", "SLT (temporal) 6/2015"),
        ("trab 2018-2019", "trabeculectomy 2018"),
        # Device model / plate size, however it is joined to the device name.
        ("BGI-350", "BGI 350"),
        ("BVT-350", "BGI 350"),
        ("350-BGI", "BGI 350"),
        ("Ahmed-FP7", "AGI FP7"),
        ("BGI-350 pars plana 2/2020", "BGI 350 (pars plana) 2/2020"),
    ],
)
def test_dash_within_one_procedure_is_not_a_separator(label, expected):
    assert std(label) == expected


def test_combined_components_alphabetical():
    # Components of a combined procedure are always ordered alphabetically.
    assert std("goniotomy + phaco 6/12/2024") == "CEIOL/goniotomy 6/12/2024"
    assert std("Xen + CEIOL") == "CEIOL/Xen"


@pytest.mark.parametrize(
    "label,expected",
    [
        # A space alone can join two procedures -- both must survive.
        ("Phaco iStent 6/2020", "CEIOL/iStent 6/2020"),
        ("phaco goniotomy 2020", "CEIOL/goniotomy 2020"),
        ("CEIOL YAG 2021", "CEIOL/YAG capsulotomy 2021"),
        ("Phaco iStent Hydrus 2019", "CEIOL/Hydrus/iStent 2019"),
        ("phaco/IOL iStent 6/2020", "CEIOL/iStent 6/2020"),
        ("trab 360 SLT 2020", "SLT/Trab 360 2020"),
        # Details stay attached to the procedure they follow.
        ("phaco Omni 360/180 2/10/23", "CEIOL/Omni (360/180) 2/10/2023"),
        ("phaco AGI sulcus 5/5/15", "AGI (sulcus)/CEIOL 5/5/2015"),
    ],
)
def test_space_separated_combined_procedures(label, expected):
    assert std(label) == expected


@pytest.mark.parametrize(
    "label,expected",
    [
        # Multi-word names, device models, the lens-implant half of cataract surgery,
        # and modifiers are all part of a SINGLE procedure despite the space.
        ("KDB goniotomy", "KDB"),
        ("Sion blade goniotomy", "Sion"),
        ("Omni canaloplasty", "Omni"),
        ("CE PCIOL", "CEIOL"),
        ("Ahmed FP7 sulcus 5/5/15", "AGI FP7 (sulcus) 5/5/2015"),
        ("BGI tube 350", "BGI 350"),
        ("trab needling 2020", "trabeculectomy 2020"),
        ("trab revision needling 2020", "bleb revision 2020"),
        ("micropulse CPC 360", "MP CPC (360)"),
        ("laser peripheral iridotomy", "LPI"),
        ("tube shunt 2010s", "tube shunt ~2010s"),
        # A generic name beside a specific one describes a single procedure.
        ("Ahmed glaucoma drainage implant", "AGI"),
        ("CE for congenital cataract 1997", "CE 1997"),
        ("tube revision for tube exposure 6/6/2023", "tube revision 6/6/2023"),
        # A generic "laser" beside a named one describes that one procedure.
        ("SLT laser 2020", "SLT 2020"),
        ("CPC laser", "CPC"),
        ("micropulse laser 2022", "MP 2022"),
        # The Ex-PRESS shunt is a trabeculectomy with express kept as a detail.
        ("Express Trab 7/2011", "trabeculectomy (express) 7/2011"),
    ],
)
def test_space_not_split_within_one_procedure(label, expected):
    assert std(label) == expected


@pytest.mark.parametrize(
    "label,expected",
    [
        ("express", "trabeculectomy (express)"),
        ("express shunt", "trabeculectomy (express)"),
        ("Express shunt MMC 3/2018", "trabeculectomy MMC (express) 3/2018"),
        ("trab Express", "trabeculectomy (express)"),
        ("trab-express", "trabeculectomy (express)"),
        ("trab/express", "trabeculectomy (express)"),
        ("trabeculectomy/express", "trabeculectomy (express)"),
        ("express/trab", "trabeculectomy (express)"),
        ("Ex-PRESS/trab 7/2011", "trabeculectomy (express) 7/2011"),
        ("Express removal", "Express removal"),
    ],
)
def test_express_becomes_trabeculectomy_with_detail(label, expected):
    assert std(label) == expected


@pytest.mark.parametrize(
    "label,expected",
    [
        ("tube revision", "tube revision"),
        ("tube repositioning", "tube revision (repositioning)"),
        ("tube reposition", "tube revision (repositioning)"),
        ("tube repos", "tube revision (repositioning)"),
        ("tube trim", "tube revision (trimming)"),
        ("tube trimming", "tube revision (trimming)"),
        ("tube revision repositioning", "tube revision (repositioning)"),
        ("tube repositioning sulcus 5/5/15", "tube revision (repositioning, sulcus) 5/5/2015"),
    ],
)
def test_tube_revision_subtypes_become_details(label, expected):
    assert std(label) == expected


def test_parenthetical_details_are_not_split_into_procedures():
    # A procedure name inside a detail parenthetical does not start a new component.
    assert std("GATT (iTrack, 360) 10/12/22") == "GATT (360) 10/12/2022"


def test_specific_device_preferred_over_generic_tube():
    assert std("IOL repositioning ST CP250 AC tube 4/4/24") == "CP250/iol repositioning (ST) 4/4/2024"


def test_slash_after_plate_size_is_combined_separator():
    # A '/' after a numeric plate size joins two procedures; only digit/digit '/'
    # (a degree range) is protected.
    assert std("BGI 350/trabeculectomy 11/8/2018") == "BGI 350/trabeculectomy 11/8/2018"
    assert std("CP250/SLT 2020") == "CP250/SLT 2020"


def test_staged_procedures_use_commas():
    assert std("SLT 2021, trabeculectomy 2023") == "SLT 2021, trabeculectomy 2023"


def test_revision_is_separate_from_the_original_trabeculectomy():
    assert (
        std("Trabeculectomy 2004, Revision Trabeculectomy 2017")
        == "trabeculectomy 2004, bleb revision 2017"
    )


# ------------------------------------------------------------
# Ordering - chronological, then alphabetical (no de-duplication)
# ------------------------------------------------------------

@pytest.mark.parametrize(
    "label,expected",
    [
        # Dated procedures first (chronological), undated last (alphabetical).
        ("BGI350 in sulcus 2/17/2020, CEIOL", "BGI 350 (sulcus) 2/17/2020, CEIOL"),
        ("CEIOL, BGI, Xen", "BGI, CEIOL, Xen"),
        ("LI 2010, CEIOL, YAG 3/24/2022", "LPI 2010, YAG capsulotomy 3/24/2022, CEIOL"),
        ("trabeculectomy 2023, SLT 2021", "SLT 2021, trabeculectomy 2023"),
    ],
)
def test_ordering(label, expected):
    assert std(label) == expected


def test_no_deduplication():
    # Duplicates are intentionally preserved (de-dup rule removed).
    assert std("SLT, SLT 5/2021") == "SLT 5/2021, SLT"


# ------------------------------------------------------------
# Synonym / abbreviation consolidation (comparison robustness)
# ------------------------------------------------------------

@pytest.mark.parametrize(
    "label,expected",
    [
        ("May have had ALT", "possible ALT"),
        ("PCIOL 2020", "CEIOL 2020"),
        ("LI", "LPI"),
        ("YAG 3/24/2022", "YAG capsulotomy 3/24/2022"),
        ("KDB goniotomy", "KDB"),
        ("laser peripheral iridotomy", "LPI"),
        # The "/IOL" / "/PCIOL" lens suffix is part of the cataract procedure, not a
        # separate one -> all collapse to CEIOL.
        ("CE/IOL", "CEIOL"),
        ("CE/PCIOL", "CEIOL"),
        ("phaco/IOL", "CEIOL"),
        ("phaco/PCIOL", "CEIOL"),
        ("choroidal drainage", "choroidal drainage"),
        ("choroidal drainage 5/2021", "choroidal drainage 5/2021"),
        ("drainage of choroidals", "choroidal drainage"),
        ("choroidal effusion drainage", "choroidal drainage"),
    ],
)
def test_synonym_consolidation(label, expected):
    assert std(label) == expected


def test_detail_order_canonicalized():
    # Details render alphabetically regardless of source order.
    assert std("Ahmed FP7 STQ sulcus 5/5/15") == "AGI FP7 (STQ, sulcus) 5/5/2015"


def test_commas_inside_parentheses_not_split():
    # Multiple details separated by commas inside parentheses must stay together.
    assert (
        std("AGI (anterior chamber, ST) 11/29/2017, CEIOL 2019")
        == "AGI (anterior chamber, ST) 11/29/2017, CEIOL 2019"
    )


@pytest.mark.parametrize(
    "label,expected",
    [
        ("BGI 350", "BGI 350"),
        ("BGI350", "BGI 350"),
        ("350 BGI", "BGI 350"),
        ("BGI 250", "BGI 250"),
        ("BGI250", "BGI 250"),
        ("250 BGI", "BGI 250"),
    ],
)
def test_bgi_plate_size_normalization(label, expected):
    assert std(label) == expected


# ------------------------------------------------------------
# R11 - None fallback
# ------------------------------------------------------------

@pytest.mark.parametrize("label", ["None", "", "n/a", "  "])
def test_none_fallback(label):
    assert std(label) == "None"


# ------------------------------------------------------------
# Future procedures use the same formatting, minus the date
# ------------------------------------------------------------

def test_future_label_type():
    # Undated procedures are ordered alphabetically.
    assert std("Xen, Durysta", label_type="future") == "Durysta, Xen"


@pytest.mark.parametrize(
    "label,expected",
    [
        # A proposed procedure is labelled without a date; the one in the text says when
        # it is planned for, not that it happened.
        ("TRABECULECTOMY 1/2018", "trabeculectomy"),
        ("trab MMC 3/25/21", "trabeculectomy MMC"),
        ("SLT temp 6/2015", "SLT (temporal)"),
        ("phaco + goniotomy 6/12/2024", "CEIOL/goniotomy"),
        ("possible Xen 2025", "possible Xen"),
        ("CEIOL ~1990s", "CEIOL"),
        ("Xen (laterality unknown) 2/2026", "Xen (laterality unknown)"),
        # Ordering falls back to alphabetical once the dates are gone.
        ("Xen 6/2025, Durysta 1/2025", "Durysta, Xen"),
    ],
)
def test_future_labels_drop_dates(label, expected):
    assert std(label, label_type="future") == expected


def test_prior_labels_keep_dates():
    # The same label keeps its date when the procedure has already happened.
    assert std("TRABECULECTOMY 1/2018", label_type="prior") == "trabeculectomy 1/2018"


def test_future_date_is_not_mistaken_for_a_detail():
    # The date is still parsed out of the text, so no part of it lands in parentheses
    # or in the procedure name.
    assert std("Omni 360 2/10/23", label_type="future") == "Omni (360)"
    assert std("BGI 350 pars plana 2/2020", label_type="future") == "BGI 350 (pars plana)"


def test_manual_review_flag_on_unmapped():
    result = standardize_procedure_label("zzq unknown thing", "prior")
    assert result["failed_match"] is True


@pytest.mark.parametrize(
    "label",
    [
        "laser suture lysis",
        "laser retinopexy",
        "trabeculoplasty",
    ],
)
def test_generic_laser_does_not_absorb_a_longer_unknown_name(label):
    # "laser" / "argon laser" name a procedure only on their own. A longer phrase
    # starting with one of them is something else -- R1 excludes laser suture lysis --
    # so it is flagged, not relabeled. A bare "trabeculoplasty" is likewise ambiguous
    # between SLT and ALT.
    result = standardize_procedure_label(label, "prior")
    assert result["standardized_procedure_list"] == label
    assert result["failed_match"] is True


def test_return_shape():
    result = standardize_procedure_label("s/p SLT 6/2015", "prior")
    assert set(result.keys()) == {
        "input_type",
        "raw_input",
        "standardized_procedure_list",
        "parsed_items",
        "failed_match",
    }
    assert result["input_type"] == "prior"
    assert isinstance(result["parsed_items"], list)
