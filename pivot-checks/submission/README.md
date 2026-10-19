# Submission package: AgentDyn audit paper (DRAFT, not submitted)

Source text: `../MANUSCRIPT_SUBMISSION.md`. Both PDFs are converted from it by `build.py`. No number is changed.

| version | files | notes |
|---|---|---|
| arXiv, named (DRAFT) | `arxiv/main.tex`, `arxiv/main.pdf` | Author line still holds the manuscript's [PLACEHOLDER]. Every page header says "DRAFT -- not submitted". |
| TMLR, anonymized | `tmlr/main.tex`, `tmlr/main.pdf`, `tmlr/tmlr.sty`, `tmlr/fancyhdr.sty`, `tmlr/tmlr.bst` | Built with the official TMLR style, anonymous mode ("Anonymous authors / Paper under double-blind review"). The style files come from github.com/JmlrOrg/tmlr-style-file at commit 7bf90efe3a0debbba703c05c43f3ff7e4d4a2992, Apache-2.0 (`tmlr/LICENSE_tmlr-style-file_Apache-2.0`). |

Build (offline): `cd pivot-checks/submission && python3 build.py`. Tools used: pandoc 3.1.11.1; pdfTeX 3.141592653-2.6-1.40.26 (TeX Live 2025/dev/Debian).

What `build.py` changes, apart from the conversion itself:
- **Front matter:** the title, status line and Authors line become LaTeX title/author fields. The TMLR version drops the status line and the Authors line.
- **TMLR text substitution (the only one):** "The owner (Shirazi Matin)" becomes "The owner (name withheld for double-blind review)".
- **Layout only:** line-break points after `/` and `_` in paths, and small type in tables.

Anonymization check on `tmlr/main.pdf` text (pdftotext, case-insensitive): matin 0, shirazi 0, "@" 0, Adapti-guard 0, cursor.com 0, claude.ai 0. "github.com" has 3 occurrences on 2 lines, all third-party code links in the reference list (SaFo-Lab/AgentDyn, the leolee99/AgentDyn redirect, and xhOwenMa/AutoDojo), not the authors' repository. The PDF metadata Author and Title fields are empty.

Open items (BLOCKING GAPs, left as the [PLACEHOLDER] text): author names and affiliations, competing interests, funding, the CRediT author name, the AgentDyn issue status and maintainers' response, and the release archive and DOI.
