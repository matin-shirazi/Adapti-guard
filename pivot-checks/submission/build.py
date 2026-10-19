#!/usr/bin/env python3
"""Build arXiv (named draft) and TMLR (anonymized) LaTeX + PDF from ../MANUSCRIPT_SUBMISSION.md.
Offline. Needs pandoc and pdflatex (TeX Live). Text is converted, not edited: the only text
substitutions are listed in ANON (TMLR only) and the front-matter handling below."""
import re, subprocess, pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE.parent / "MANUSCRIPT_SUBMISSION.md"
# TMLR double-blind: replace identifying strings (exact match, each must occur).
ANON = [("The owner (Shirazi Matin)", "The owner (name withheld for double-blind review)")]

UNICODE = r"""
\usepackage{newunicodechar}
\newunicodechar{κ}{\ensuremath{\kappa}}
\newunicodechar{τ}{\ensuremath{\tau}}
\newunicodechar{Δ}{\ensuremath{\Delta}}
\newunicodechar{−}{\ensuremath{-}}
\newunicodechar{≥}{\ensuremath{\geq}}
\newunicodechar{→}{\ensuremath{\rightarrow}}
\newunicodechar{×}{\ensuremath{\times}}
\newunicodechar{²}{\ensuremath{^{2}}}
\newunicodechar{…}{\ldots}
"""
COMMON = r"""
\usepackage[utf8]{inputenc}
\usepackage{amsmath,amssymb}
\usepackage{longtable,booktabs,array,calc}
\usepackage{xurl}
\usepackage[hidelinks]{hyperref}
\providecommand{\tightlist}{\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}
\setcounter{secnumdepth}{-\maxdimen}
\setlength{\emergencystretch}{3em}
\renewcommand{\arraystretch}{1.15}
\sloppy
\usepackage{etoolbox}
\AtBeginEnvironment{longtable}{\small}
""" + UNICODE

def split(md):
    lines = md.split("\n")
    assert lines[0].startswith("# "); title = lines[0][2:].strip()
    status = lines[2].strip().strip("*")
    authors = lines[4]; assert authors.startswith("**Authors:**")
    i_abs = lines.index("## Abstract"); i_intro = lines.index("## 1 Introduction")
    labels = "\n".join(lines[6:i_abs]).strip()
    abs_block = lines[i_abs + 1:i_intro]
    k = next(j for j, l in enumerate(abs_block) if l.startswith("**Keywords:**"))
    abstract = "\n".join(abs_block[:k]).strip(); after_abs = "\n".join(abs_block[k:]).strip()
    body = "\n".join(lines[i_intro:])
    return title, status, authors[len("**Authors:**"):].strip(), labels, abstract, after_abs, body

def tex(md):
    # "[LABEL]: text" at line start would be parsed as a link reference definition; escape the bracket.
    md = re.sub(r'(?m)^(\s*(?:[-*] |\d+\. )?)\[([^\]]*)\]:', lambda m: m.group(1) + '\\[' + m.group(2) + ']:', md)
    r = subprocess.run(["pandoc", "-f", "markdown+lists_without_preceding_blankline-smart-tex_math_dollars", "-t", "latex", "--shift-heading-level-by=-1", "--wrap=preserve"],
                       input=md, capture_output=True, text=True, check=True)
    return breakable_tt(r.stdout)

def breakable_tt(s):
    """Allow line breaks after / _ . inside \\texttt{} (long file paths in tables). Layout only."""
    def fix(m):
        c = m.group(1)
        c = c.replace("/", "/\\allowbreak{}").replace("\\_", "\\_\\allowbreak{}")
        return "\\texttt{" + c + "}"
    s = re.sub(r"\\texttt\{((?:[^{}]|\\\{|\\\})*)\}", fix, s)
    # Inside tables, also allow breaks after / and \_ in plain text (not in URLs). Layout only.
    out, intab = [], False
    for line in s.split("\n"):
        if line.startswith("\\begin{longtable}"): intab = True
        if intab and "\\url{" not in line and "\\href{" not in line:
            line = re.sub(r"/(?!\\allowbreak)", lambda m: "/\\allowbreak{}", line)
            line = re.sub(r"\\_(?!\\allowbreak)", lambda m: "\\_\\allowbreak{}", line)
        if line.startswith("\\end{longtable}"): intab = False
        out.append(line)
    return "\n".join(out)

def esc(s):
    return tex(s).strip()

def build(kind):
    md = SRC.read_text(encoding="utf-8")
    if kind == "tmlr":
        for a, b in ANON:
            assert md.count(a) == 1, a; md = md.replace(a, b)
    title, status, authors, labels, abstract, after_abs, body = split(md)
    front = esc(after_abs) + "\n\n" + esc(labels)
    if kind == "arxiv":
        pre = r"\documentclass[11pt]{article}" + "\n" + r"\usepackage[T1]{fontenc}\usepackage{lmodern}\usepackage[margin=1in]{geometry}" + COMMON + r"""
\usepackage{fancyhdr}\pagestyle{fancy}\fancyhf{}\lhead{\small DRAFT -- not submitted}\rhead{\small \thepage}
"""
        head = (r"\title{" + esc(title) + r"\thanks{DRAFT. " + esc(status) + r"}}" + "\n"
                r"\author{\parbox{0.9\textwidth}{\centering " + esc(authors) + "}}\n" r"\date{DRAFT, not submitted}" "\n")
        doc = pre + head + "\\begin{document}\n\\maketitle\n\\begin{abstract}\n" + esc(abstract) + "\n\\end{abstract}\n" + front + "\n\n" + tex(body) + "\n\\end{document}\n"
    else:
        pre = r"\documentclass[10pt]{article}" + "\n" + r"\usepackage{tmlr}" + COMMON
        head = r"\title{" + esc(title) + "}\n" + r"\author{Anonymous authors}" + "\n" + r"\def\month{MM}\def\year{YYYY}\def\openreview{\url{https://openreview.net/forum?id=XXXX}}" + "\n"
        doc = pre + head + "\\begin{document}\n\\maketitle\n\\begin{abstract}\n" + esc(abstract) + "\n\\end{abstract}\n" + front + "\n\n" + tex(body) + "\n\\end{document}\n"
    out = HERE / kind / "main.tex"; out.write_text(doc, encoding="utf-8")
    for _ in range(2):
        subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"], cwd=HERE / kind, check=True, stdout=subprocess.DEVNULL)
    print("built", out.with_suffix(".pdf"))

if __name__ == "__main__":
    for k in (sys.argv[1:] or ["arxiv", "tmlr"]):
        build(k)
