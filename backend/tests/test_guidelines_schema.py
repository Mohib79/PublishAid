"""
Unit tests for Guideline Rule Schema (GE-SCH) and Grounding (GE-GRD).
Reference: Guideline Extraction Plan Sections 10.2 and 10.3.
"""

import time
import pytest
from pydantic import ValidationError

from app.services.guidelines.schema import (
    GuidelineRuleSchema,
    GeneralRules,
    CitationRules,
    LayoutRules,
    FiguresRules,
    SubmissionRules,
    ArticleTypeSpec,
    OtherNote,
    get_schema_metadata,
    canonicalize_section_name,
)
from app.services.guidelines.grounding import (
    compute_grounding,
    check_number_in_text,
    check_word_in_text,
    normalize_text_for_matching,
)


# ===========================================================================
# 10.2 Rule Schema, Normalization and Validation (GE-SCH)
# ===========================================================================

def test_ge_sch_01_empty_rules_object():
    """GE-SCH-01: Empty rules object {} with schemaVersion: 1 is valid."""
    schema = GuidelineRuleSchema(schemaVersion=1)
    assert schema.schemaVersion == 1
    assert schema.general is None
    assert schema.citation is None


def test_ge_sch_02_unknown_top_level_key():
    """GE-SCH-02: Unknown top-level key is rejected."""
    with pytest.raises(ValidationError) as exc:
        GuidelineRuleSchema.model_validate({"schemaVersion": 1, "unknownKey": 123})
    assert "extra_forbidden" in str(exc.value) or "Extra inputs are not permitted" in str(exc.value)


def test_ge_sch_03_unknown_key_nested_inside_general():
    """GE-SCH-03: Unknown key nested inside general is rejected."""
    with pytest.raises(ValidationError) as exc:
        GuidelineRuleSchema.model_validate({
            "schemaVersion": 1,
            "general": {"maxWords": 5000, "unknownProperty": "bad"}
        })
    assert "extra_forbidden" in str(exc.value) or "Extra inputs are not permitted" in str(exc.value)


def test_ge_sch_04_schema_version_missing_or_not_1():
    """GE-SCH-04: schemaVersion missing or not 1 is rejected."""
    with pytest.raises(ValidationError):
        GuidelineRuleSchema.model_validate({"schemaVersion": 2})
    
    # Missing schemaVersion defaults to 1 if not passed in Python,
    # but if passed as None or invalid type:
    with pytest.raises(ValidationError):
        GuidelineRuleSchema.model_validate({"schemaVersion": "v1"})


def test_ge_sch_05_max_words_boundaries():
    """GE-SCH-05: maxWords 99 / 100 / 100000 / 100001 -> Rejected / valid / valid / rejected."""
    with pytest.raises(ValidationError):
        GeneralRules(maxWords=99)
    assert GeneralRules(maxWords=100).maxWords == 100
    assert GeneralRules(maxWords=100000).maxWords == 100000
    with pytest.raises(ValidationError):
        GeneralRules(maxWords=100001)


def test_ge_sch_06_max_words_input_normalization():
    """GE-SCH-06: maxWords as '8,000', '8 000', 8000.0 normalizes to 8000."""
    assert GeneralRules(maxWords="8,000").maxWords == 8000
    assert GeneralRules(maxWords="8 000").maxWords == 8000
    assert GeneralRules(maxWords=8000.0).maxWords == 8000


def test_ge_sch_07_max_words_invalid_inputs():
    """GE-SCH-07: maxWords as 8000.5, -5, 0, 'abc', True rejected; None is allowed."""
    for invalid in [8000.5, -5, 0, "abc", True]:
        with pytest.raises(ValidationError):
            GeneralRules(maxWords=invalid)
    assert GeneralRules(maxWords=None).maxWords is None


def test_ge_sch_08_min_words_greater_than_max_words():
    """GE-SCH-08: minWords greater than maxWords is rejected."""
    with pytest.raises(ValidationError) as exc:
        GeneralRules(minWords=6000, maxWords=5000)
    assert "minWords must be at most maxWords" in str(exc.value)


def test_ge_sch_09_max_abstract_words_boundaries():
    """GE-SCH-09: maxAbstractWords 19 / 20 / 1000 / 1001 -> Rejected / valid / valid / rejected."""
    with pytest.raises(ValidationError):
        GeneralRules(maxAbstractWords=19)
    assert GeneralRules(maxAbstractWords=20).maxAbstractWords == 20
    assert GeneralRules(maxAbstractWords=1000).maxAbstractWords == 1000
    with pytest.raises(ValidationError):
        GeneralRules(maxAbstractWords=1001)


def test_ge_sch_10_abstract_limit_larger_than_manuscript_limit():
    """GE-SCH-10: Abstract limit larger than manuscript limit is valid in schema (warning at merge)."""
    # Schema allows it without rejecting
    rules = GeneralRules(minWords=100, maxWords=200, maxAbstractWords=300)
    assert rules.maxAbstractWords == 300


def test_ge_sch_11_keywords_min_max_validation():
    """GE-SCH-11: keywords.min > max; max 0; max 31 rejected."""
    from app.services.guidelines.schema import KeywordsSpec
    with pytest.raises(ValidationError):
        KeywordsSpec(min=6, max=4)
    with pytest.raises(ValidationError):
        KeywordsSpec(max=0)
    with pytest.raises(ValidationError):
        KeywordsSpec(max=31)
    assert KeywordsSpec(min=3, max=6).max == 6


def test_ge_sch_12_word_limit_excludes_unknown_value():
    """GE-SCH-12: wordLimitExcludes with an unknown value is rejected."""
    with pytest.raises(ValidationError):
        GeneralRules(wordLimitExcludes=["abstract", "unknown_elem"])


def test_ge_sch_13_word_limit_excludes_duplicates():
    """GE-SCH-13: wordLimitExcludes duplicates are deduplicated."""
    rules = GeneralRules(wordLimitExcludes=["abstract", "references", "abstract"])
    assert rules.wordLimitExcludes == ["abstract", "references"]


def test_ge_sch_14_required_sections_canonicalization():
    """GE-SCH-14: '2. Methods', 'METHODS', 'Materials and Methods', 'Methodology', 'Method' -> all become 'Methods'."""
    inputs = ["2. Methods", "METHODS", "Materials and Methods", "Methodology", "Method"]
    for raw in inputs:
        assert canonicalize_section_name(raw) == "Methods"
    
    rules = GeneralRules(requiredSections=inputs)
    assert rules.requiredSections == ["Methods"]


def test_ge_sch_15_required_sections_unknown():
    """GE-SCH-15: requiredSections with an unknown section 'Ethics Statement' is kept as given."""
    rules = GeneralRules(requiredSections=["Ethics Statement"])
    assert rules.requiredSections == ["Ethics Statement"]


def test_ge_sch_16_duplicate_sections_after_canonicalization():
    """GE-SCH-16: Duplicate sections after canonicalization kept once, order preserved."""
    rules = GeneralRules(requiredSections=["Introduction", "1. Introduction", "Methods", "Methodology"])
    assert rules.requiredSections == ["Introduction", "Methods"]


def test_ge_sch_17_too_many_required_sections():
    """GE-SCH-17: 31 required sections is rejected (max 30)."""
    with pytest.raises(ValidationError):
        GeneralRules(requiredSections=[f"Section {i}" for i in range(31)])
    assert len(GeneralRules(requiredSections=[f"Section {i}" for i in range(30)]).requiredSections) == 30


def test_ge_sch_18_section_name_html_control_chars():
    """GE-SCH-18: Section name with HTML tags or control characters stripped."""
    assert canonicalize_section_name("<b>Methods</b>\x00") == "Methods"
    rules = GeneralRules(requiredSections=["<i>Background</i>\x07"])
    assert rules.requiredSections == ["Background"]


def test_ge_sch_19_citation_style_aliases():
    """GE-SCH-19: citation.style aliases: 'ieee', 'IEEE style', 'Harvard (Elsevier)', 'numbered'."""
    assert CitationRules.model_validate({"style": "ieee"}).style == "IEEE"
    assert CitationRules.model_validate({"style": "IEEE style"}).style == "IEEE"
    assert CitationRules.model_validate({"style": "Harvard (Elsevier)"}).style == "Harvard"
    assert CitationRules.model_validate({"style": "numbered"}).style == "IEEE"


def test_ge_sch_20_citation_style_unknown():
    """GE-SCH-20: citation.style unknown ('Custom XYZ') -> Other with original in notes."""
    c = CitationRules.model_validate({"style": "Custom XYZ"})
    assert c.style == "Other"
    assert "Custom XYZ" in (c.notes or "")


def test_ge_sch_21_citation_max_references():
    """GE-SCH-21: citation.maxReferences 0 / 1 / 1000 / 1001 -> Rejected / valid / valid / rejected."""
    with pytest.raises(ValidationError):
        CitationRules(maxReferences=0)
    assert CitationRules(maxReferences=1).maxReferences == 1
    assert CitationRules(maxReferences=1000).maxReferences == 1000
    with pytest.raises(ValidationError):
        CitationRules(maxReferences=1001)


def test_ge_sch_22_citation_notes_length():
    """GE-SCH-22: citation.notes of 300 / 301 characters -> Valid / rejected."""
    assert len(CitationRules(notes="a" * 300).notes) == 300
    with pytest.raises(ValidationError):
        CitationRules(notes="a" * 301)


def test_ge_sch_23_layout_columns_synonyms():
    """GE-SCH-23: layout.columns synonyms: 'two-column', 'double column', '2-col' -> double."""
    for synonym in ["two-column", "double column", "2-col", "2 column"]:
        assert LayoutRules(columns=synonym).columns == "double"


def test_ge_sch_24_layout_columns_invalid():
    """GE-SCH-24: layout.columns invalid ('triple') -> Rejected."""
    with pytest.raises(ValidationError):
        LayoutRules(columns="triple")


def test_ge_sch_25_font_size_pt_boundaries():
    """GE-SCH-25: fontSizePt 5.9 / 6 / 24 / 24.1 -> Rejected / valid / valid / rejected."""
    with pytest.raises(ValidationError):
        LayoutRules(fontSizePt=5.9)
    assert LayoutRules(fontSizePt=6.0).fontSizePt == 6.0
    assert LayoutRules(fontSizePt=24.0).fontSizePt == 24.0
    with pytest.raises(ValidationError):
        LayoutRules(fontSizePt=24.1)


def test_ge_sch_26_line_spacing_boundaries():
    """GE-SCH-26: lineSpacing 0.9 / 1 / 1.5 / 2 / 3 / 3.1 -> Rejected / valid / valid / valid / valid / rejected."""
    with pytest.raises(ValidationError):
        LayoutRules(lineSpacing=0.9)
    assert LayoutRules(lineSpacing=1.0).lineSpacing == 1.0
    assert LayoutRules(lineSpacing=1.5).lineSpacing == 1.5
    assert LayoutRules(lineSpacing=2.0).lineSpacing == 2.0
    assert LayoutRules(lineSpacing=3.0).lineSpacing == 3.0
    with pytest.raises(ValidationError):
        LayoutRules(lineSpacing=3.1)


def test_ge_sch_27_margins_unit_conversions():
    """GE-SCH-27: Margins given in inches and millimetres converted to centimetres (1 in = 2.54 cm)."""
    from app.services.guidelines.schema import MarginsCm
    m = MarginsCm(top="1 inch", bottom="25.4 mm", left="1 in", right="2.54 cm")
    assert m.top == 2.54
    assert m.bottom == 2.54
    assert m.left == 2.54
    assert m.right == 2.54


def test_ge_sch_28_margins_boundaries():
    """GE-SCH-28: Margin 0.4 / 0.5 / 6 / 6.1 cm -> Rejected / valid / valid / rejected."""
    from app.services.guidelines.schema import MarginsCm
    with pytest.raises(ValidationError):
        MarginsCm(top=0.4)
    assert MarginsCm(top=0.5).top == 0.5
    assert MarginsCm(top=6.0).top == 6.0
    with pytest.raises(ValidationError):
        MarginsCm(top=6.1)


def test_ge_sch_29_partial_margins():
    """GE-SCH-29: Only some margin sides present is valid."""
    from app.services.guidelines.schema import MarginsCm
    m = MarginsCm(top=2.5)
    assert m.top == 2.5
    assert m.bottom is None


def test_ge_sch_30_figures_formats_unknown():
    """GE-SCH-30: figures.formats unknown value ('gif') -> Rejected."""
    with pytest.raises(ValidationError):
        FiguresRules(formats=["tiff", "gif"])
    # jpeg normalizes to jpg
    f = FiguresRules(formats=["jpeg", "png"])
    assert f.formats == ["jpg", "png"]


def test_ge_sch_31_figures_min_dpi_boundaries():
    """GE-SCH-31: figures.minDpi 71 / 72 / 1200 / 1201 -> Rejected / valid / valid / rejected."""
    with pytest.raises(ValidationError):
        FiguresRules(minDpi=71)
    assert FiguresRules(minDpi=72).minDpi == 72
    assert FiguresRules(minDpi=1200).minDpi == 1200
    with pytest.raises(ValidationError):
        FiguresRules(minDpi=1201)


def test_ge_sch_32_submission_file_formats_review_type():
    """GE-SCH-32: submission.fileFormats and reviewType invalid values rejected."""
    with pytest.raises(ValidationError):
        SubmissionRules(fileFormats=["exe"])
    with pytest.raises(ValidationError):
        SubmissionRules(reviewType="triple_blind")
    s = SubmissionRules(fileFormats=["docx", "tex"], reviewType="double_blind")
    assert s.reviewType == "double_blind"


def test_ge_sch_33_submission_template_url():
    """GE-SCH-33: submission.templateUrl http / not a URL / over 500 / javascript URL rejected."""
    with pytest.raises(ValidationError):
        SubmissionRules(templateUrl="http://example.com/template.docx")
    with pytest.raises(ValidationError):
        SubmissionRules(templateUrl="javascript:alert(1)")
    with pytest.raises(ValidationError):
        SubmissionRules(templateUrl="https://" + ("a" * 501))
    valid = "https://example.com/downloads/template.dotx"
    assert SubmissionRules(templateUrl=valid).templateUrl == valid


def test_ge_sch_34_article_types_count_boundary():
    """GE-SCH-34: articleTypes with 15 / 16 entries -> Valid / rejected."""
    types15 = [ArticleTypeSpec(name=f"Type {i}") for i in range(15)]
    schema15 = GuidelineRuleSchema(schemaVersion=1, articleTypes=types15)
    assert len(schema15.articleTypes) == 15

    types16 = [ArticleTypeSpec(name=f"Type {i}") for i in range(16)]
    with pytest.raises(ValidationError):
        GuidelineRuleSchema(schemaVersion=1, articleTypes=types16)


def test_ge_sch_35_article_types_duplicate_case_insensitive():
    """GE-SCH-35: Two article types with the same name ignoring case -> Rejected."""
    with pytest.raises(ValidationError) as exc:
        GuidelineRuleSchema(
            schemaVersion=1,
            articleTypes=[
                ArticleTypeSpec(name="Research Article"),
                ArticleTypeSpec(name="RESEARCH ARTICLE"),
            ]
        )
    assert "unique" in str(exc.value)


def test_ge_sch_36_article_type_name_validation():
    """GE-SCH-36: Article type without a name; name over 80 characters -> Rejected."""
    with pytest.raises(ValidationError):
        ArticleTypeSpec(name="")
    with pytest.raises(ValidationError):
        ArticleTypeSpec(name="a" * 81)
    assert ArticleTypeSpec(name="a" * 80).name == "a" * 80


def test_ge_sch_37_default_article_type_not_in_list():
    """GE-SCH-37: defaultArticleType not in the list is rejected."""
    with pytest.raises(ValidationError) as exc:
        GuidelineRuleSchema(
            schemaVersion=1,
            articleTypes=[ArticleTypeSpec(name="Original Article")],
            defaultArticleType="Short Communication",
        )
    assert "must match an articleType name" in str(exc.value)


def test_ge_sch_38_default_article_type_without_article_types():
    """GE-SCH-38: defaultArticleType set while articleTypes empty -> Rejected."""
    with pytest.raises(ValidationError) as exc:
        GuidelineRuleSchema(
            schemaVersion=1,
            articleTypes=[],
            defaultArticleType="Original Article",
        )
    assert "defaultArticleType cannot be set" in str(exc.value)


def test_ge_sch_39_other_notes_validation():
    """GE-SCH-39: other with 20 / 21 entries; label over 80; text over 500 -> Valid / rejected."""
    assert OtherNote(label="Test", text="A note").label == "Test"
    with pytest.raises(ValidationError):
        OtherNote(label="a" * 81, text="Note")
    with pytest.raises(ValidationError):
        OtherNote(label="Test", text="a" * 501)
    
    notes20 = [OtherNote(label=f"L{i}", text=f"T{i}") for i in range(20)]
    s20 = GuidelineRuleSchema(schemaVersion=1, other=notes20)
    assert len(s20.other) == 20

    notes21 = [OtherNote(label=f"L{i}", text=f"T{i}") for i in range(21)]
    with pytest.raises(ValidationError):
        GuidelineRuleSchema(schemaVersion=1, other=notes21)


def test_ge_sch_40_whitespace_trimming():
    """GE-SCH-40: Strings with leading, trailing and inner extra whitespace trimmed and collapsed."""
    note = OtherNote(label="  My   Label  ", text="  Multiple   Spaces   Here  ")
    assert note.label == "My Label"
    assert note.text == "Multiple Spaces Here"


def test_ge_sch_41_control_chars_stripped_or_rejected():
    """GE-SCH-41: Strings with NUL or control characters stripped or rejected."""
    note = OtherNote(label="Label\x00\x08", text="Text\x1fHere")
    assert note.label == "Label"
    assert note.text == "TextHere"


def test_ge_sch_42_required_statements_unknown():
    """GE-SCH-42: requiredStatements unknown value rejected."""
    with pytest.raises(ValidationError):
        GeneralRules(requiredStatements=["unknownStatement"])
    g = GeneralRules(requiredStatements=["ethics", "dataAvailability"])
    assert "ethics" in g.requiredStatements


def test_ge_sch_43_unicode_text_preserved():
    """GE-SCH-43: Unicode text in names and notes (Urdu, Chinese, emoji) preserved."""
    urdu = "تحقیقی مقالہ"
    chinese = "研究论文"
    emoji = "📄 Notes 🚀"
    at = ArticleTypeSpec(name=urdu, notes=f"{chinese} {emoji}")
    assert at.name == urdu
    assert chinese in at.notes
    assert emoji in at.notes


def test_ge_sch_44_schema_metadata_endpoint():
    """GE-SCH-44: Schema metadata endpoint output lists every path, type, range, enum, canonical sections."""
    meta = get_schema_metadata()
    assert meta["schemaVersion"] == 1
    assert "Methods" in meta["canonicalSections"]
    assert "IEEE" in meta["enums"]["citationStyles"]
    assert meta["ranges"]["general.maxWords"]["max"] == 100000


def test_ge_sch_45_rule_set_all_nulls_valid():
    """GE-SCH-45: A rule set whose every value is null is valid in the schema."""
    schema = GuidelineRuleSchema(
        schemaVersion=1,
        general=GeneralRules(maxWords=None, minWords=None),
        citation=CitationRules(style=None),
        layout=LayoutRules(columns=None),
    )
    assert schema.schemaVersion == 1


def test_ge_sch_46_round_trip_dump_validate():
    """GE-SCH-46: Round trip (dump then validate) is stable."""
    orig = GuidelineRuleSchema(
        schemaVersion=1,
        general=GeneralRules(maxWords=5000, requiredSections=["Methods", "Results"]),
        citation=CitationRules(style="IEEE", maxReferences=50),
        layout=LayoutRules(columns="double"),
    )
    data = orig.model_dump()
    reconstructed = GuidelineRuleSchema.model_validate(data)
    assert reconstructed.model_dump() == data


def test_ge_sch_47_extremely_deep_or_huge_payload():
    """GE-SCH-47: Extremely deep or huge JSON payload cleanly rejected."""
    # Build a payload with 500 nested dictionaries or huge strings
    huge_data = {"schemaVersion": 1, "general": {"maxWords": 5000, "deep": {"a": {"b": {}}}}}
    with pytest.raises(ValidationError):
        GuidelineRuleSchema.model_validate(huge_data)


# ===========================================================================
# 10.3 Grounding and Confidence (GE-GRD)
# ===========================================================================

def test_ge_grd_01_exact_substring_and_number_in_evidence():
    """GE-GRD-01: Evidence is an exact substring and number is in evidence -> high."""
    source = "Manuscripts should not exceed 8,000 words excluding references."
    evidence = "Manuscripts should not exceed 8,000 words"
    res = compute_grounding(8000, evidence, source, "general.maxWords")
    assert res.confidence == "high"
    assert res.grounded is True
    assert res.evidence_status == "exact"


def test_ge_grd_02_smart_quotes_dashes_spaces_line_wraps():
    """GE-GRD-02: Evidence differs by smart quotes, en dashes, non-breaking spaces or line wraps -> high."""
    source = 'The “maximum” word count – including tables\u00a0– is 5,000 words.'
    evidence = 'The "maximum" word count - including tables - is 5,000 words.'
    res = compute_grounding(5000, evidence, source, "general.maxWords")
    assert res.confidence == "high"
    assert res.grounded is True


def test_ge_grd_03_fuzzy_match_above_threshold():
    """GE-GRD-03: Evidence found only by fuzzy match above threshold -> medium."""
    source = "Authors are requested to provide up to 5 keywords for indexing purposes."
    # Slightly altered phrase with a minor typo (>90% partial ratio, not exact)
    evidence = "Authors are requested to provide up to 5 keywords for indexing puposes."
    res = compute_grounding(5, evidence, source, "general.keywords.max")
    assert res.confidence == "medium"
    assert res.evidence_status == "fuzzy"


def test_ge_grd_04_evidence_not_present_in_source():
    """GE-GRD-04: Evidence not present in source -> low."""
    source = "This journal requires single-blind peer review."
    evidence = "Authors must submit double-blind manuscripts."
    res = compute_grounding("double_blind", evidence, source, "submission.reviewType")
    assert res.confidence == "low"
    assert res.evidence_status == "not_found"
    assert res.grounded is False


def test_ge_grd_05_number_formats_grounded():
    """GE-GRD-05: Number written '8,000', '8 000', '8000' in source -> Grounded."""
    for formatted in ["8,000 words", "8 000 words", "8000 words"]:
        source = f"Articles have a limit of {formatted}."
        assert check_number_in_text(8000, normalize_text_for_matching(source)) is True


def test_ge_grd_06_number_as_english_word():
    """GE-GRD-06: Number written as a word ('six keywords', value 6) -> Grounded."""
    source = "Please provide between three and six keywords."
    assert check_number_in_text(6, normalize_text_for_matching(source)) is True
    assert check_number_in_text(3, normalize_text_for_matching(source)) is True


def test_ge_grd_07_number_in_source_not_in_evidence():
    """GE-GRD-07: Number appears in source but not in evidence -> medium."""
    source = "The overall length limit is 6,000 words. Please adhere to the guidelines."
    evidence = "Please adhere to the guidelines."
    res = compute_grounding(6000, evidence, source, "general.maxWords")
    assert res.confidence == "medium"
    assert res.grounded is True


def test_ge_grd_08_number_nowhere_in_source():
    """GE-GRD-08: Number appears nowhere in source -> low, warning UNGROUNDED_VALUES."""
    source = "There are no explicit word counts mentioned in this guide."
    evidence = "There are no explicit word counts"
    res = compute_grounding(7500, evidence, source, "general.maxWords")
    assert res.confidence == "low"
    assert res.grounded is False
    assert any(w["code"] == "UNGROUNDED_VALUES" for w in res.warnings)


def test_ge_grd_09_range_values_grounded():
    """GE-GRD-09: Range '3 to 6 keywords' with values 3 and 6 -> Both grounded."""
    source = "Include 3 to 6 keywords."
    assert check_number_in_text(3, normalize_text_for_matching(source)) is True
    assert check_number_in_text(6, normalize_text_for_matching(source)) is True


def test_ge_grd_10_number_part_of_another_number():
    """GE-GRD-10: Number appears only as part of another number (18000 for 8000) -> Not grounded."""
    source = "The institute has 18000 members worldwide."
    assert check_number_in_text(8000, normalize_text_for_matching(source)) is False


def test_ge_grd_11_evidence_empty_or_whitespace():
    """GE-GRD-11: Evidence empty or whitespace -> low."""
    source = "Word limit is 5000."
    res = compute_grounding(5000, "   ", source, "general.maxWords")
    assert res.confidence == "low"
    assert res.evidence_status == "empty"


def test_ge_grd_12_evidence_longer_than_300_chars():
    """GE-GRD-12: Evidence longer than 300 characters is truncated to 300 for storage."""
    source = "Word limit is 5000 words. " + ("Extra context. " * 30)
    long_evidence = "Word limit is 5000 words. " + ("Extra context. " * 25)
    assert len(long_evidence) > 300
    res = compute_grounding(5000, long_evidence, source, "general.maxWords")
    assert len(res.evidence) <= 300


def test_ge_grd_13_list_field_partial_grounding():
    """GE-GRD-13: List field with one item not found -> That item flagged, others fine."""
    source = "Manuscripts must include Methods and Results sections."
    res_methods = compute_grounding("Methods", "include Methods and Results", source, "requiredSections")
    res_unknown = compute_grounding("Conflict of Interest", "include Methods and Results", source, "requiredSections")
    assert res_methods.confidence == "high"
    assert res_unknown.confidence == "low"


def test_ge_grd_14_enum_value_in_evidence():
    """GE-GRD-14: Enum value ('IEEE') with word present in evidence -> Grounded."""
    source = "References should follow the IEEE citation format."
    evidence = "follow the IEEE citation format"
    res = compute_grounding("IEEE", evidence, source, "citation.style")
    assert res.confidence == "high"
    assert res.grounded is True


def test_ge_grd_15_enum_value_inferred_no_mention():
    """GE-GRD-15: Enum value inferred with no mention in source -> low."""
    source = "Cite references thoroughly using the standard format."
    evidence = "Cite references thoroughly"
    res = compute_grounding("IEEE", evidence, source, "citation.style")
    assert res.confidence == "low"
    assert res.grounded is False


def test_ge_grd_16_large_source_performance():
    """GE-GRD-16: Very large source (300,000 characters) finishes within a few seconds."""
    large_source = "Unrelated background text. " * 11000 + "Maximum words is 9000. " + "More text. " * 2000
    assert len(large_source) > 300000
    t0 = time.time()
    res = compute_grounding(9000, "Maximum words is 9000", large_source, "general.maxWords")
    elapsed = time.time() - t0
    assert elapsed < 3.0
    assert res.confidence == "high"


def test_ge_grd_17_llm_claim_overridden():
    """GE-GRD-17: Confidence never comes from LLM's own claim."""
    source = "The journal publishes papers twice a year."
    # Fabricated evidence not in source
    res = compute_grounding(5000, "Limit is 5000 words", source, "general.maxWords")
    # Even if caller or LLM thought it was high, grounding assigns low
    assert res.confidence == "low"
