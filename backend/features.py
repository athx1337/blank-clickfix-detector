"""Small, bounded text features; never interprets or executes command strings."""
import re
import unicodedata
from dataclasses import dataclass

# English subset adapted from ClickFixMitigator, MIT, ae0e5144930f391f97dd8a7cbe0aa08548ee0d3d.
# Copyright (c) 2026 Jordi Serrano. Full notice: licenses/ClickFixMitigator-MIT.txt.
# Removed broad Windows-key-only and non-English matches; added raw span preservation.
PATTERNS = {
    "verification": r"verify\s+(?:that\s+)?you\s+are\s+(?:a\s+)?human|"
                    r"confirm\s+(?:that\s+)?you\s+are\s+(?:a\s+)?human|"
                    r"(?:confirm|prove)?\s*(?:i['’]?m|you\s+are)\s+not\s+a\s+robot|"
                    r"verification\s+(?:failed|required|needed|step|process|code|prompt)|"
                    r"(?:manual|additional|human|robot|security|bot)\s+verification|"
                    r"verify\s+(?:that\s+)?(?:you\s+are|to\s+continue|your\s+identity)|"
                    r"captcha|anti[- ]bot|prove\s+you\s+are\s+human|security\s+check",
    "repair": r"(?:repair|fix|update|restore)\s+(?:your\s+|the\s+)?(?:browser|chrome|edge)|"
              r"browser\s+(?:error|repair|problem)|connection\s+(?:error|repair)|video\s+(?:error|repair)",
    "system": r"(?:w\s*i\s*n(?:dows)?|⊞)\s*(?:key)?\s*\+\s*r\b|windows\s+run|run\s*(?:dialog|box)|open\s+run\b|"
              r"powershell|command\s+prompt|\bcmd(?:\.exe)?\b|\bterminal\b|"
              r"win\s*\+\s*x.{0,60}(?:terminal|press\s+i)",
    "run_dialog": r"(?:w\s*i\s*n(?:dows)?|⊞)\s*(?:key)?\s*\+\s*r\b|windows\s+run|run\s*(?:dialog|box)|open\s+run\b|"
                  r"win\s*\+\s*x.{0,60}(?:terminal|press\s+i)",
    "paste": r"\bpaste\b|(?:ctrl|control)\s*\+\s*v\b",
    "execute": r"\b(?:press|hit)\s+(?:the\s+)?enter\b|\benter\b|\bexecute\b|\brun\s+(?:it|the\s+(?:code|command|fix))",
    "command": r"-(?:enc(?:odedcommand)?|(?:executionpolicy|ep)\s+bypass|nop|w(?:indowstyle)?\s+hidden)\b|\bmshta(?:\.exe)?\b|"
               r"\binvoke-expression\b|\biex\b|\b(?:iwr|irm)\b|downloadstring\s*\(",
    "reporting": r"security\s+(?:article|report|research|bulletin|advisory)|"
                 r"attackers?\s+(?:say|ask|instruct|use)|"
                 r"scammers?\s+(?:say|ask|instruct)|quoted\s+(?:attack|example)|"
                 r"clickfix\s+(?:analysis|example|awareness|simulation|testing|research|app|hub|threat|campaign)|"
                 r"(?:safe|legitimate|educational)\s+(?:platforms?|sites?|tools?|resources?|environment)|"
                 r"simulate\s+(?:clickfix|attacks?)|test,\s*learn\s*about|"
                 r"without\s+exposing\s+your\s+system|"
                 r"educational\s+website|awareness\s+project|"
                 r"fake\s+(?:captcha|verification|recaptcha|cloudflare)|"
                 r"search\s+results?|threat\s+feeds?|security\s+researcher|lab\s+review",
    "negation": r"(?:never|do\s+not|don't|avoid)\s+(?:.{0,60}?)(?:paste|run|execute)",
}
COMPILED = {name: re.compile(pattern, re.I | re.S) for name, pattern in PATTERNS.items()}


@dataclass
class Features:
    normalized: str
    offsets: list[int]
    matches: dict[str, list[tuple[int, int]]]

    def has(self, name):
        return bool(self.matches[name])


def normalize_with_offsets(text: str) -> tuple[str, list[int]]:
    chars, offsets = [], []
    for index, char in enumerate(text):
        if char in "\u200b\u200c\u200d\ufeff\u2060":
            continue
        for normalized in unicodedata.normalize("NFKC", char).lower():
            chars.append(normalized)
            offsets.append(index)
    return "".join(chars), offsets


def extract_features(text: str) -> Features:
    normalized, offsets = normalize_with_offsets(text)
    matches = {key: [(m.start(), m.end()) for m in regex.finditer(normalized)]
               for key, regex in COMPILED.items()}
    # Scope negation and educational reporting to avoid treating reported scams as lures.
    reporting_prefix = re.compile(r"\b(?:no|without|fake|mock|simulate|simulated|about|test|understand|learn\s+about)\s+(?:(?:verification|browser|captcha|clickfix|or|a|any|the|fake)\s+){0,5}$")
    for key in ("verification", "repair"):
        matches[key] = [(start, end) for start, end in matches[key]
                        if not reporting_prefix.search(normalized[max(0, start - 80):start])]
    return Features(normalized, offsets, matches)


def excerpt(text: str, start: int, end: int, context: int = 50) -> str:
    # Adapted from ClickGrab extract_match_with_context, Apache-2.0, e5e78d67...
    # Changed API to raw offsets, added an explicit 600-character bound. See licenses/.
    left = max(0, start - context)
    right = min(len(text), end + context, left + 600)
    return text[left:right]


def evidence(text: str, features: Features, keys: list[str]) -> str:
    spans = [features.matches[key][0] for key in keys if features.has(key)]
    if not spans:
        return text[:600]
    start, end = min(s[0] for s in spans), max(s[1] for s in spans)
    return excerpt(text, features.offsets[start], features.offsets[end - 1] + 1)
