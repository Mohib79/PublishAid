"""
Generates schema-validated system guideline rule JSON files in backend/seed/guideline_rules/
for all 50 catalog journals in backend/seed/journals.csv.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.guidelines.schema import GuidelineRuleSchema

CSV_PATH = BACKEND_DIR / "seed" / "journals.csv"
OUT_DIR = BACKEND_DIR / "seed" / "guideline_rules"

# Preserve existing filenames for the 3 already-seeded catalog journals
EXISTING_SLUG_MAP = {
    "0162-8828": "ieee_tpami",
    "0925-2312": "elsevier_neurocomputing",
    "0730-0301": "acm_tog",
}


def slugify_journal(title: str, publisher: str, issn: str) -> str:
    if issn in EXISTING_SLUG_MAP:
        return EXISTING_SLUG_MAP[issn]

    pub_low = publisher.lower()
    if "ieee" in pub_low:
        prefix = "ieee"
    elif "elsevier" in pub_low:
        prefix = "elsevier"
    elif "springer" in pub_low:
        prefix = "springer"
    elif "acm" in pub_low:
        prefix = "acm"
    elif "oxford" in pub_low:
        prefix = "oup"
    else:
        prefix = "wiley"

    # Check if title has parenthetical abbreviation like (TPAMI)
    m = re.search(r"\(([A-Za-z0-9]+)\)", title)
    if m:
        abbr = m.group(1).lower()
        return f"{prefix}_{abbr}"

    clean = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    # Remove leading publisher prefix if duplicated
    if clean.startswith(f"{prefix}_"):
        clean = clean[len(prefix) + 1 :]
    if clean.startswith("transactions_on_"):
        clean = "trans_" + clean[len("transactions_on_") :]
    words = clean.split("_")
    short = "_".join(words[:4])
    return f"{prefix}_{short}"


# Journal-specific overrides keyed by ISSN
JOURNAL_OVERRIDES: dict[str, dict[str, Any]] = {
    # IEEE (10)
    "0162-8828": {  # TPAMI
        "sourceUrl": "https://www.computer.org/csdl/journal/tp/write-for-us/15066",
        "maxWords": 9500,
        "maxAbstractWords": 250,
        "maxPages": 14,
        "reviewType": "double_blind",
        "maxReferences": 65,
    },
    "2162-237X": {  # TNNLS
        "sourceUrl": "https://cis.ieee.org/publications/t-neural-networks-and-learning-systems/tnnls-information-for-authors",
        "maxWords": 9000,
        "maxAbstractWords": 250,
        "maxPages": 12,
        "reviewType": "single_blind",
        "maxReferences": 55,
    },
    "1057-7149": {  # TIP
        "sourceUrl": "https://signalprocessingsociety.org/publications-resources/ieee-transactions-image-processing/information-authors-tip",
        "maxWords": 9000,
        "maxAbstractWords": 250,
        "maxPages": 13,
        "reviewType": "single_blind",
        "maxReferences": 55,
    },
    "0018-9340": {  # TC
        "sourceUrl": "https://www.computer.org/csdl/journal/tc/write-for-us/13946",
        "maxWords": 8500,
        "maxAbstractWords": 200,
        "maxPages": 12,
        "reviewType": "single_blind",
        "maxReferences": 50,
    },
    "0098-5589": {  # TSE
        "sourceUrl": "https://www.computer.org/csdl/journal/ts/write-for-us/15080",
        "maxWords": 10000,
        "maxAbstractWords": 200,
        "maxPages": 14,
        "reviewType": "double_blind",
        "maxReferences": 65,
    },
    "1041-4347": {  # TKDE
        "sourceUrl": "https://www.computer.org/csdl/journal/tk/write-for-us/15055",
        "maxWords": 9500,
        "maxAbstractWords": 200,
        "maxPages": 14,
        "reviewType": "single_blind",
        "maxReferences": 60,
    },
    "1077-2626": {  # TVCG
        "sourceUrl": "https://www.computer.org/csdl/journal/tg/write-for-us/15085",
        "maxWords": 9000,
        "maxAbstractWords": 200,
        "maxPages": 12,
        "reviewType": "single_blind",
        "maxReferences": 55,
    },
    "1536-1233": {  # TMC
        "sourceUrl": "https://www.computer.org/csdl/journal/tm/write-for-us/15061",
        "maxWords": 9500,
        "maxAbstractWords": 200,
        "maxPages": 14,
        "reviewType": "single_blind",
        "maxReferences": 55,
    },
    "1545-5971": {  # TDSC
        "sourceUrl": "https://www.computer.org/csdl/journal/tq/write-for-us/15048",
        "maxWords": 9500,
        "maxAbstractWords": 200,
        "maxPages": 14,
        "reviewType": "single_blind",
        "maxReferences": 55,
    },
    "1556-6013": {  # TIFS
        "sourceUrl": "https://signalprocessingsociety.org/publications-resources/ieee-transactions-information-forensics-and-security/information-authors-tifs",
        "maxWords": 9000,
        "maxAbstractWords": 250,
        "maxPages": 13,
        "reviewType": "single_blind",
        "maxReferences": 55,
    },
    # Elsevier (10)
    "0004-3702": {  # Artificial Intelligence
        "sourceUrl": "https://www.sciencedirect.com/journal/artificial-intelligence/publish/guide-for-authors",
        "maxWords": 12000,
        "maxPages": 30,
        "reviewType": "single_blind",
    },
    "0020-0255": {  # Information Sciences
        "sourceUrl": "https://www.sciencedirect.com/journal/information-sciences/publish/guide-for-authors",
        "maxWords": 10000,
        "maxPages": 25,
        "reviewType": "single_blind",
    },
    "0031-3203": {  # Pattern Recognition
        "sourceUrl": "https://www.sciencedirect.com/journal/pattern-recognition/publish/guide-for-authors",
        "maxWords": 9500,
        "maxPages": 24,
        "reviewType": "single_blind",
    },
    "0950-7051": {  # Knowledge-Based Systems
        "sourceUrl": "https://www.sciencedirect.com/journal/knowledge-based-systems/publish/guide-for-authors",
        "maxWords": 9000,
        "maxPages": 22,
        "reviewType": "single_blind",
    },
    "0925-2312": {  # Neurocomputing
        "sourceUrl": "https://www.sciencedirect.com/journal/neurocomputing/publish/guide-for-authors",
        "maxWords": 9000,
        "maxPages": 22,
        "reviewType": "single_blind",
    },
    "0164-1212": {  # Journal of Systems and Software
        "sourceUrl": "https://www.sciencedirect.com/journal/journal-of-systems-and-software/publish/guide-for-authors",
        "maxWords": 10000,
        "maxPages": 25,
        "reviewType": "single_blind",
    },
    "1389-1286": {  # Computer Networks
        "sourceUrl": "https://www.sciencedirect.com/journal/computer-networks/publish/guide-for-authors",
        "maxWords": 9500,
        "maxPages": 22,
        "reviewType": "single_blind",
    },
    "0167-739X": {  # Future Generation Computer Systems
        "sourceUrl": "https://www.sciencedirect.com/journal/future-generation-computer-systems/publish/guide-for-authors",
        "maxWords": 9500,
        "maxPages": 22,
        "reviewType": "single_blind",
    },
    "1077-3142": {  # Computer Vision and Image Understanding
        "sourceUrl": "https://www.sciencedirect.com/journal/computer-vision-and-image-understanding/publish/guide-for-authors",
        "maxWords": 10000,
        "maxPages": 24,
        "reviewType": "double_blind",
    },
    "1566-2535": {  # Information Fusion
        "sourceUrl": "https://www.sciencedirect.com/journal/information-fusion/publish/guide-for-authors",
        "maxWords": 10000,
        "maxPages": 25,
        "reviewType": "single_blind",
    },
    # Springer (10)
    "0920-5691": {  # IJCV
        "sourceUrl": "https://link.springer.com/journal/11263/submission-guidelines",
        "maxWords": 11000,
        "maxPages": 25,
        "columns": "double",
        "citationStyle": "APA",
        "numbered": False,
        "reviewType": "single_blind",
    },
    "0885-6125": {  # Machine Learning
        "sourceUrl": "https://link.springer.com/journal/10994/submission-guidelines",
        "maxWords": 10000,
        "maxPages": 25,
        "columns": "single",
        "citationStyle": "APA",
        "numbered": False,
        "reviewType": "single_blind",
    },
    "0269-2821": {  # Artificial Intelligence Review
        "sourceUrl": "https://link.springer.com/journal/10462/submission-guidelines",
        "maxWords": 14000,
        "maxPages": 30,
        "columns": "single",
        "citationStyle": "APA",
        "numbered": False,
        "maxReferences": 140,
        "reviewType": "single_blind",
    },
    "1387-2532": {  # AAMAS
        "sourceUrl": "https://link.springer.com/journal/10458/submission-guidelines",
        "maxWords": 10000,
        "maxPages": 25,
        "columns": "single",
        "citationStyle": "Springer",
        "numbered": True,
        "reviewType": "single_blind",
    },
    "1386-145X": {  # World Wide Web
        "sourceUrl": "https://link.springer.com/journal/11280/submission-guidelines",
        "maxWords": 9500,
        "maxPages": 22,
        "columns": "single",
        "citationStyle": "Springer",
        "numbered": True,
        "reviewType": "single_blind",
    },
    "1386-7857": {  # Cluster Computing
        "sourceUrl": "https://link.springer.com/journal/10586/submission-guidelines",
        "maxWords": 9000,
        "maxPages": 20,
        "columns": "double",
        "citationStyle": "Springer",
        "numbered": True,
        "reviewType": "single_blind",
    },
    "1382-3256": {  # Empirical Software Engineering
        "sourceUrl": "https://link.springer.com/journal/10664/submission-guidelines",
        "maxWords": 12000,
        "maxPages": 28,
        "columns": "single",
        "citationStyle": "APA",
        "numbered": False,
        "reviewType": "single_blind",
    },
    "0941-0643": {  # Neural Computing and Applications
        "sourceUrl": "https://link.springer.com/journal/521/submission-guidelines",
        "maxWords": 9500,
        "maxPages": 22,
        "columns": "double",
        "citationStyle": "Springer",
        "numbered": True,
        "reviewType": "single_blind",
    },
    "1380-7501": {  # Multimedia Tools and Applications
        "sourceUrl": "https://link.springer.com/journal/11042/submission-guidelines",
        "maxWords": 9000,
        "maxPages": 20,
        "columns": "single",
        "citationStyle": "Springer",
        "numbered": True,
        "reviewType": "single_blind",
    },
    "0010-485X": {  # Computing
        "sourceUrl": "https://link.springer.com/journal/607/submission-guidelines",
        "maxWords": 9000,
        "maxPages": 20,
        "columns": "single",
        "citationStyle": "Springer",
        "numbered": True,
        "reviewType": "single_blind",
    },
    # ACM (10)
    "0004-5411": {  # JACM
        "sourceUrl": "https://dl.acm.org/journal/jacm/author-guidelines",
        "maxWords": 14000,
        "maxPages": 30,
        "columns": "single",
        "fontSizePt": 10.0,
        "reviewType": "single_blind",
    },
    "0001-0782": {  # CACM
        "sourceUrl": "https://cacm.acm.org/author-guidelines/",
        "maxWords": 4500,
        "maxAbstractWords": 150,
        "maxPages": 8,
        "columns": "double",
        "fontSizePt": 10.0,
        "maxReferences": 25,
        "reviewType": "single_blind",
    },
    "0360-0300": {  # CSUR
        "sourceUrl": "https://dl.acm.org/journal/csur/author-guidelines",
        "maxWords": 18000,
        "maxPages": 35,
        "columns": "single",
        "fontSizePt": 10.0,
        "maxReferences": 160,
        "reviewType": "single_blind",
    },
    "0730-0301": {  # TOG
        "sourceUrl": "https://dl.acm.org/journal/tog/author-guidelines",
        "maxWords": 12000,
        "maxPages": 16,
        "columns": "double",
        "fontSizePt": 9.0,
        "reviewType": "double_blind",
    },
    "0362-5915": {  # TODS
        "sourceUrl": "https://dl.acm.org/journal/tods/author-guidelines",
        "maxWords": 13000,
        "maxPages": 28,
        "columns": "single",
        "fontSizePt": 10.0,
        "reviewType": "single_blind",
    },
    "0734-2071": {  # TOCS
        "sourceUrl": "https://dl.acm.org/journal/tocs/author-guidelines",
        "maxWords": 12000,
        "maxPages": 25,
        "columns": "single",
        "fontSizePt": 10.0,
        "reviewType": "single_blind",
    },
    "1049-331X": {  # TOSEM
        "sourceUrl": "https://dl.acm.org/journal/tosem/author-guidelines",
        "maxWords": 13000,
        "maxPages": 28,
        "columns": "single",
        "fontSizePt": 10.0,
        "reviewType": "double_blind",
    },
    "1046-8188": {  # TOIS
        "sourceUrl": "https://dl.acm.org/journal/tois/author-guidelines",
        "maxWords": 12000,
        "maxPages": 25,
        "columns": "single",
        "fontSizePt": 10.0,
        "reviewType": "double_blind",
    },
    "1549-6325": {  # TALG
        "sourceUrl": "https://dl.acm.org/journal/talg/author-guidelines",
        "maxWords": 12000,
        "maxPages": 25,
        "columns": "single",
        "fontSizePt": 10.0,
        "reviewType": "single_blind",
    },
    "2157-6904": {  # TIST
        "sourceUrl": "https://dl.acm.org/journal/tist/author-guidelines",
        "maxWords": 11000,
        "maxPages": 24,
        "columns": "single",
        "fontSizePt": 10.0,
        "reviewType": "single_blind",
    },
    # Wiley (9) + OUP (1)
    "0167-7055": {  # Computer Graphics Forum
        "sourceUrl": "https://onlinelibrary.wiley.com/page/journal/14678659/homepage/forauthors.html",
        "maxWords": 9000,
        "maxPages": 12,
        "columns": "double",
        "reviewType": "double_blind",
    },
    "0038-0644": {  # Software: Practice and Experience
        "sourceUrl": "https://onlinelibrary.wiley.com/page/journal/1097024x/homepage/forauthors.html",
        "maxWords": 9500,
        "maxPages": 22,
        "columns": "single",
        "reviewType": "single_blind",
    },
    "0824-7935": {  # Computational Intelligence
        "sourceUrl": "https://onlinelibrary.wiley.com/page/journal/14678640/homepage/forauthors.html",
        "maxWords": 9000,
        "maxPages": 20,
        "columns": "single",
        "citationStyle": "APA",
        "numbered": False,
        "reviewType": "single_blind",
    },
    "0266-4720": {  # Expert Systems
        "sourceUrl": "https://onlinelibrary.wiley.com/page/journal/14680394/homepage/forauthors.html",
        "maxWords": 9000,
        "maxPages": 20,
        "columns": "single",
        "citationStyle": "APA",
        "numbered": False,
        "reviewType": "single_blind",
    },
    "1532-0626": {  # Concurrency and Computation: Practice and Experience
        "sourceUrl": "https://onlinelibrary.wiley.com/page/journal/15320634/homepage/forauthors.html",
        "maxWords": 9500,
        "maxPages": 20,
        "columns": "single",
        "reviewType": "single_blind",
    },
    "2047-7481": {  # Journal of Software: Evolution and Process
        "sourceUrl": "https://onlinelibrary.wiley.com/page/journal/20477481/homepage/forauthors.html",
        "maxWords": 9500,
        "maxPages": 22,
        "columns": "single",
        "reviewType": "single_blind",
    },
    "2475-6725": {  # Security and Privacy
        "sourceUrl": "https://onlinelibrary.wiley.com/page/journal/24756725/homepage/forauthors.html",
        "maxWords": 8500,
        "maxPages": 18,
        "columns": "single",
        "reviewType": "single_blind",
    },
    "1942-4787": {  # WIREs Data Mining and Knowledge Discovery
        "sourceUrl": "https://wires.onlinelibrary.wiley.com/hub/journal/19424795/forauthors.html",
        "maxWords": 11000,
        "maxPages": 24,
        "columns": "single",
        "citationStyle": "APA",
        "numbered": False,
        "maxReferences": 120,
        "reviewType": "single_blind",
    },
    "1055-7148": {  # International Journal of Network Management
        "sourceUrl": "https://onlinelibrary.wiley.com/page/journal/10991190/homepage/forauthors.html",
        "maxWords": 8500,
        "maxPages": 18,
        "columns": "single",
        "reviewType": "single_blind",
    },
    "1083-6101": {  # Journal of Computer-Mediated Communication (OUP)
        "sourceUrl": "https://academic.oup.com/jcmc/pages/General_Instructions",
        "maxWords": 8000,
        "maxAbstractWords": 200,
        "maxPages": 25,
        "columns": "single",
        "citationStyle": "APA",
        "numbered": False,
        "reviewType": "double_blind",
        "documentClass": "article.cls",
    },
}


def build_rules_for_row(row: dict[str, str]) -> dict[str, Any]:
    title = row["journal_title"].strip()
    publisher = row["publisher"].strip()
    issn = row["issn"].strip()
    ov = JOURNAL_OVERRIDES.get(issn, {})
    pub_low = publisher.lower()

    is_survey = any(k in title.lower() for k in ("survey", "review", "wires"))

    if "ieee" in pub_low:
        rules = {
            "schemaVersion": 1,
            "general": {
                "maxWords": ov.get("maxWords", 9000),
                "minWords": 3000,
                "wordLimitExcludes": ["references", "figureCaptions", "appendices"],
                "maxAbstractWords": ov.get("maxAbstractWords", 250),
                "abstractStructure": "unstructured",
                "keywords": {"min": 3, "max": 5},
                "keywordSeparator": "comma",
                "maxTitleChars": 150,
                "requiredSections": [
                    "Abstract",
                    "Keywords",
                    "Introduction",
                    "Methods",
                    "Results",
                    "Discussion",
                    "Conclusion",
                    "Acknowledgements",
                    "References",
                ],
                "requiredStatements": [
                    "conflictOfInterest",
                    "dataAvailability",
                    "funding",
                    "authorContributions",
                    "generativeAI",
                    "acknowledgements",
                ],
            },
            "citation": {
                "style": "IEEE",
                "numbered": True,
                "maxReferences": ov.get("maxReferences", 55),
                "notes": "IEEE numbered citations in square brackets [1] ordered by appearance.",
            },
            "layout": {
                "columns": "double",
                "pageSize": "Letter",
                "fontFamily": "Times New Roman",
                "fontSizePt": 10.0,
                "fontSizeTitlePt": 24.0,
                "fontSizeFigureCaptionPt": 8.0,
                "fontSizeTableCaptionPt": 8.0,
                "documentClass": "IEEEtran.cls",
                "lineSpacing": 1.0,
                "marginsCm": {"top": 1.9, "bottom": 2.54, "left": 1.6, "right": 1.6},
                "maxPages": ov.get("maxPages", 12),
            },
            "figures": {
                "maxFigures": 12,
                "maxTables": 6,
                "minDpi": 300,
                "formats": ["pdf", "eps", "tiff", "png"],
            },
            "submission": {
                "fileFormats": ["pdf", "tex", "docx"],
                "reviewType": ov.get("reviewType", "single_blind"),
                "templateUrl": "https://template-selector.ieee.org/",
                "coverLetterRequired": True,
                "orcidRequired": True,
                "highlightsRequired": False,
            },
            "articleTypes": [
                {
                    "name": "Regular Paper",
                    "maxWords": ov.get("maxWords", 9000),
                    "maxAbstractWords": ov.get("maxAbstractWords", 250),
                    "requiredSections": ["Introduction", "Methods", "Results", "Discussion", "Conclusion", "References"],
                    "maxFigures": 12,
                    "maxTables": 6,
                    "maxReferences": ov.get("maxReferences", 55),
                },
                {
                    "name": "Short Paper",
                    "maxWords": 4500,
                    "maxAbstractWords": 150,
                    "requiredSections": ["Introduction", "Methods", "Results", "Conclusion", "References"],
                    "maxFigures": 6,
                    "maxTables": 3,
                    "maxReferences": 30,
                },
                {
                    "name": "Survey Paper",
                    "maxWords": 12000,
                    "maxAbstractWords": 250,
                    "requiredSections": ["Introduction", "Background", "Discussion", "Conclusion", "References"],
                    "maxFigures": 14,
                    "maxTables": 8,
                    "maxReferences": 100,
                },
            ],
            "defaultArticleType": "Regular Paper",
        }
    elif "elsevier" in pub_low:
        rules = {
            "schemaVersion": 1,
            "general": {
                "maxWords": ov.get("maxWords", 9500),
                "minWords": 3500,
                "wordLimitExcludes": ["references", "abstract", "appendices"],
                "maxAbstractWords": 250,
                "abstractStructure": "unstructured",
                "keywords": {"min": 4, "max": 6},
                "keywordSeparator": "semicolon",
                "maxTitleChars": 150,
                "requiredSections": [
                    "Abstract",
                    "Keywords",
                    "Introduction",
                    "Methods",
                    "Results",
                    "Discussion",
                    "Conclusion",
                    "Data Availability",
                    "Conflict of Interest",
                    "References",
                ],
                "requiredStatements": [
                    "conflictOfInterest",
                    "dataAvailability",
                    "funding",
                    "creditStatement",
                    "generativeAI",
                    "acknowledgements",
                ],
            },
            "citation": {
                "style": "Elsevier",
                "numbered": True,
                "maxReferences": 75,
                "notes": "Elsevier numbered reference style in square brackets [1] or elsarticle-num.",
            },
            "layout": {
                "columns": "single",
                "pageSize": "A4",
                "fontFamily": "Times New Roman",
                "fontSizePt": 12.0,
                "fontSizeTitlePt": 16.0,
                "fontSizeFigureCaptionPt": 10.0,
                "fontSizeTableCaptionPt": 10.0,
                "documentClass": "elsarticle.cls",
                "lineSpacing": 1.5,
                "marginsCm": {"top": 2.54, "bottom": 2.54, "left": 2.54, "right": 2.54},
                "maxPages": ov.get("maxPages", 24),
            },
            "figures": {
                "maxFigures": 12,
                "maxTables": 8,
                "minDpi": 300,
                "formats": ["tiff", "eps", "pdf", "jpg", "png"],
            },
            "submission": {
                "fileFormats": ["docx", "tex", "pdf"],
                "reviewType": ov.get("reviewType", "single_blind"),
                "templateUrl": "https://www.elsevier.com/researcher/author/policies-and-guidelines/latex-instructions",
                "coverLetterRequired": True,
                "orcidRequired": True,
                "highlightsRequired": True,
                "highlightCount": 5,
                "highlightLengthChars": 85,
            },
            "articleTypes": [
                {
                    "name": "Original Research Article",
                    "maxWords": ov.get("maxWords", 9500),
                    "maxAbstractWords": 250,
                    "requiredSections": ["Introduction", "Methods", "Results", "Discussion", "Conclusion", "References"],
                    "maxFigures": 12,
                    "maxTables": 8,
                    "maxReferences": 75,
                },
                {
                    "name": "Review Article",
                    "maxWords": 14000,
                    "maxAbstractWords": 250,
                    "requiredSections": ["Introduction", "Background", "Discussion", "Conclusion", "References"],
                    "maxFigures": 15,
                    "maxTables": 10,
                    "maxReferences": 140,
                },
                {
                    "name": "Short Communication",
                    "maxWords": 4500,
                    "maxAbstractWords": 150,
                    "requiredSections": ["Introduction", "Methods", "Results", "Conclusion", "References"],
                    "maxFigures": 5,
                    "maxTables": 3,
                    "maxReferences": 35,
                },
            ],
            "defaultArticleType": "Original Research Article",
        }
    elif "springer" in pub_low:
        cite_style = ov.get("citationStyle", "Springer")
        numbered = ov.get("numbered", True)
        req_sections = (
            ["Abstract", "Keywords", "Introduction", "Background", "Discussion", "Conclusion", "References"]
            if is_survey
            else ["Abstract", "Keywords", "Introduction", "Methods", "Results", "Discussion", "Conclusion", "References"]
        )
        rules = {
            "schemaVersion": 1,
            "general": {
                "maxWords": ov.get("maxWords", 10000),
                "minWords": 3500,
                "wordLimitExcludes": ["references", "appendices"],
                "maxAbstractWords": 250,
                "abstractStructure": "unstructured",
                "keywords": {"min": 4, "max": 6},
                "keywordSeparator": "comma",
                "maxTitleChars": 160,
                "requiredSections": req_sections,
                "requiredStatements": [
                    "conflictOfInterest",
                    "dataAvailability",
                    "funding",
                    "ethics",
                    "authorContributions",
                    "consentForPublication",
                    "generativeAI",
                ],
            },
            "citation": {
                "style": cite_style,
                "numbered": numbered,
                "maxReferences": ov.get("maxReferences", 80),
                "notes": "Springer Nature sn-jnl reference style.",
            },
            "layout": {
                "columns": ov.get("columns", "single"),
                "pageSize": "A4",
                "fontFamily": "Times New Roman",
                "fontSizePt": 10.0,
                "fontSizeTitlePt": 16.0,
                "fontSizeFigureCaptionPt": 9.0,
                "fontSizeTableCaptionPt": 9.0,
                "documentClass": "sn-jnl.cls",
                "lineSpacing": 1.5,
                "marginsCm": {"top": 2.5, "bottom": 2.5, "left": 2.5, "right": 2.5},
                "maxPages": ov.get("maxPages", 25),
            },
            "figures": {
                "maxFigures": 12,
                "maxTables": 8,
                "minDpi": 300,
                "formats": ["eps", "pdf", "png", "tiff", "jpg"],
            },
            "submission": {
                "fileFormats": ["tex", "docx", "pdf"],
                "reviewType": ov.get("reviewType", "single_blind"),
                "templateUrl": "https://www.springernature.com/gp/authors/campaigns/latex-author-support",
                "coverLetterRequired": False,
                "orcidRequired": True,
                "highlightsRequired": False,
            },
            "articleTypes": [
                {
                    "name": "Regular Article",
                    "maxWords": ov.get("maxWords", 10000),
                    "maxAbstractWords": 250,
                    "requiredSections": ["Introduction", "Methods", "Results", "Discussion", "Conclusion", "References"],
                    "maxFigures": 12,
                    "maxTables": 8,
                    "maxReferences": ov.get("maxReferences", 80),
                },
                {
                    "name": "Short Article",
                    "maxWords": 4500,
                    "maxAbstractWords": 150,
                    "requiredSections": ["Introduction", "Methods", "Results", "Conclusion", "References"],
                    "maxFigures": 6,
                    "maxTables": 4,
                    "maxReferences": 35,
                },
                {
                    "name": "Survey Article",
                    "maxWords": 14000,
                    "maxAbstractWords": 250,
                    "requiredSections": ["Introduction", "Background", "Discussion", "Conclusion", "References"],
                    "maxFigures": 15,
                    "maxTables": 10,
                    "maxReferences": 140,
                },
            ],
            "defaultArticleType": "Survey Article" if is_survey else "Regular Article",
        }
    elif "acm" in pub_low:
        req_sections = (
            ["Abstract", "Keywords", "Introduction", "Background", "Discussion", "Conclusion", "References"]
            if is_survey
            else ["Abstract", "Keywords", "Introduction", "Methods", "Results", "Discussion", "Conclusion", "References"]
        )
        rules = {
            "schemaVersion": 1,
            "general": {
                "maxWords": ov.get("maxWords", 12000),
                "minWords": 3000,
                "wordLimitExcludes": ["references", "appendices"],
                "maxAbstractWords": ov.get("maxAbstractWords", 250),
                "abstractStructure": "unstructured",
                "keywords": {"min": 3, "max": 8},
                "keywordSeparator": "comma",
                "maxTitleChars": 160,
                "requiredSections": req_sections,
                "requiredStatements": [
                    "conflictOfInterest",
                    "dataAvailability",
                    "funding",
                    "authorContributions",
                    "generativeAI",
                    "acknowledgements",
                ],
            },
            "citation": {
                "style": "ACM",
                "numbered": True,
                "maxReferences": ov.get("maxReferences", 70),
                "notes": "ACM-Reference-Format numbered citations in square brackets.",
            },
            "layout": {
                "columns": ov.get("columns", "single"),
                "pageSize": "Letter",
                "fontFamily": "Linux Libertine",
                "fontSizePt": ov.get("fontSizePt", 10.0),
                "fontSizeTitlePt": 14.0,
                "fontSizeFigureCaptionPt": 9.0,
                "fontSizeTableCaptionPt": 9.0,
                "documentClass": "acmart.cls",
                "lineSpacing": 1.0,
                "marginsCm": {"top": 2.54, "bottom": 2.54, "left": 2.2, "right": 2.2},
                "maxPages": ov.get("maxPages", 25),
            },
            "figures": {
                "maxFigures": 12,
                "maxTables": 8,
                "minDpi": 300,
                "formats": ["pdf", "png", "eps", "svg"],
            },
            "submission": {
                "fileFormats": ["tex", "pdf", "docx"],
                "reviewType": ov.get("reviewType", "single_blind"),
                "templateUrl": "https://www.acm.org/publications/proceedings-template",
                "coverLetterRequired": True,
                "orcidRequired": True,
                "highlightsRequired": False,
            },
            "articleTypes": [
                {
                    "name": "Research Article",
                    "maxWords": ov.get("maxWords", 12000),
                    "maxAbstractWords": ov.get("maxAbstractWords", 250),
                    "requiredSections": ["Introduction", "Methods", "Results", "Discussion", "Conclusion", "References"],
                    "maxFigures": 12,
                    "maxTables": 8,
                    "maxReferences": ov.get("maxReferences", 70),
                },
                {
                    "name": "Short Paper",
                    "maxWords": 5000,
                    "maxAbstractWords": 150,
                    "requiredSections": ["Introduction", "Methods", "Results", "Conclusion", "References"],
                    "maxFigures": 6,
                    "maxTables": 4,
                    "maxReferences": 35,
                },
                {
                    "name": "Tutorial and Survey",
                    "maxWords": 18000,
                    "maxAbstractWords": 250,
                    "requiredSections": ["Introduction", "Background", "Discussion", "Conclusion", "References"],
                    "maxFigures": 15,
                    "maxTables": 10,
                    "maxReferences": 160,
                },
            ],
            "defaultArticleType": "Tutorial and Survey" if is_survey else "Research Article",
        }
    else:  # Wiley + OUP
        is_oup = "oxford" in pub_low
        cite_style = ov.get("citationStyle", "APA" if is_oup else "Vancouver")
        numbered = ov.get("numbered", False if cite_style == "APA" else True)
        req_sections = (
            ["Abstract", "Keywords", "Introduction", "Background", "Discussion", "Conclusion", "References"]
            if is_survey
            else ["Abstract", "Keywords", "Introduction", "Methods", "Results", "Discussion", "Conclusion", "References"]
        )
        rules = {
            "schemaVersion": 1,
            "general": {
                "maxWords": ov.get("maxWords", 9000),
                "minWords": 3000,
                "wordLimitExcludes": ["references", "tables", "figureCaptions"],
                "maxAbstractWords": ov.get("maxAbstractWords", 250),
                "abstractStructure": "unstructured",
                "keywords": {"min": 3, "max": 6},
                "keywordSeparator": "comma",
                "maxTitleChars": 150,
                "requiredSections": req_sections,
                "requiredStatements": [
                    "conflictOfInterest",
                    "dataAvailability",
                    "funding",
                    "ethics",
                    "authorContributions",
                    "acknowledgements",
                ],
            },
            "citation": {
                "style": cite_style,
                "numbered": numbered,
                "maxReferences": ov.get("maxReferences", 75),
                "notes": "Oxford University Press APA style." if is_oup else "Wiley New Journal Design reference style.",
            },
            "layout": {
                "columns": ov.get("columns", "single"),
                "pageSize": "Letter" if is_oup else "A4",
                "fontFamily": "Times New Roman",
                "fontSizePt": 12.0 if is_oup else 11.0,
                "fontSizeTitlePt": 16.0,
                "fontSizeFigureCaptionPt": 9.5,
                "fontSizeTableCaptionPt": 9.5,
                "documentClass": ov.get("documentClass", "WileyNJDv5.cls"),
                "lineSpacing": 2.0 if is_oup else 1.5,
                "marginsCm": {"top": 2.54, "bottom": 2.54, "left": 2.54, "right": 2.54},
                "maxPages": ov.get("maxPages", 20),
            },
            "figures": {
                "maxFigures": 10,
                "maxTables": 6,
                "minDpi": 300,
                "formats": ["tiff", "eps", "pdf", "png"],
            },
            "submission": {
                "fileFormats": ["docx", "tex", "pdf"],
                "reviewType": ov.get("reviewType", "single_blind"),
                "templateUrl": (
                    "https://academic.oup.com/jcmc/pages/General_Instructions"
                    if is_oup
                    else "https://authorservices.wiley.com/author-resources/Journal-Authors/Prepare/new-journal-design.html"
                ),
                "coverLetterRequired": True,
                "orcidRequired": True,
                "highlightsRequired": False,
            },
            "articleTypes": [
                {
                    "name": "Original Research Article",
                    "maxWords": ov.get("maxWords", 9000),
                    "maxAbstractWords": ov.get("maxAbstractWords", 250),
                    "requiredSections": ["Introduction", "Methods", "Results", "Discussion", "Conclusion", "References"],
                    "maxFigures": 10,
                    "maxTables": 6,
                    "maxReferences": ov.get("maxReferences", 75),
                },
                {
                    "name": "Review Article",
                    "maxWords": 12000,
                    "maxAbstractWords": 250,
                    "requiredSections": ["Introduction", "Background", "Discussion", "Conclusion", "References"],
                    "maxFigures": 12,
                    "maxTables": 8,
                    "maxReferences": 120,
                },
            ],
            "defaultArticleType": "Review Article" if is_survey else "Original Research Article",
        }

    # Validate against GuidelineRuleSchema
    validated = GuidelineRuleSchema.model_validate(rules)
    return {
        "name": f"{title} Guidelines"[:200],
        "journalTitle": title,
        "journalIssn": issn,
        "sourceUrl": ov.get("sourceUrl", "https://www.doi.org/"),
        "schemaVersion": 1,
        "rules": validated.model_dump(exclude_none=True),
    }


def generate_all() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(CSV_PATH, mode="r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    used_slugs: set[str] = set()
    generated = 0
    for row in rows:
        title = row["journal_title"].strip()
        publisher = row["publisher"].strip()
        issn = row["issn"].strip()
        slug = slugify_journal(title, publisher, issn)
        if slug in used_slugs:
            slug = f"{slug}_{issn.replace('-', '')}"
        used_slugs.add(slug)

        payload = build_rules_for_row(row)
        out_path = OUT_DIR / f"{slug}.json"
        with open(out_path, mode="w", encoding="utf-8") as out_f:
            json.dump(payload, out_f, indent=2)
        generated += 1

    print(f"Generated and schema-validated {generated} catalog journal rule files in {OUT_DIR}")
    return generated


if __name__ == "__main__":
    generate_all()

