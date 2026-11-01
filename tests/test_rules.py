import pytest

from backend.detector import Detector
from backend.schemas import AnalyzeRequest


def analyze(text, **context):
    request = AnalyzeRequest(scan_id="test", blocks=[{
        "block_id": "block_1", "text": text, "context": context,
    }])
    return Detector().analyze(request)


@pytest.mark.parametrize("text,code", [
    ("Verify you are human. Press Win+R, then Ctrl+V and press Enter.",
     "VERIFICATION_WITH_SYSTEM_EXECUTION"),
    ("Repair your browser. Open PowerShell, paste the fix and run it.", "REPAIR_WITH_PASTE_AND_RUN"),
    ("Confirm you are not a robot. Open Windows Run. Paste the code and hit Enter.",
     "VERIFICATION_WITH_SYSTEM_EXECUTION"),
    ("Verify you are human. Press W i n + R then Ctrl + V and Enter.",
     "VERIFICATION_WITH_SYSTEM_EXECUTION"),
    ("Verify you are human. Press Win\u200b+R then Ctrl+V and Enter.",
     "VERIFICATION_WITH_SYSTEM_EXECUTION"),
    ("What to do? (Windows)\n• Press Windows + R\n• Press Ctrl + V\n• Press Enter",
     "SUSPICIOUS_SYSTEM_EXECUTION_SEQUENCE"),
    ("• Press Windows + R\n• Press Ctrl + V\n• Press Enter",
     "SUSPICIOUS_SYSTEM_EXECUTION_SEQUENCE"),
    ("I'm not a robot\nVerification failed. Additional verification required.\nPress Windows + R, then Ctrl + V and Enter.",
     "VERIFICATION_WITH_SYSTEM_EXECUTION"),
])
def test_deceptive_instructions(text, code):
    result = analyze(text)
    assert result.verdict == "suspicious"
    assert code in [finding.code for finding in result.findings]
    assert all(finding.evidence in text for finding in result.findings)
    assert result.detector_mode == "rules_only"
    assert result.model_version is None
    assert result.processing_ms >= 0


@pytest.mark.parametrize("text", [
    "PowerShell tutorial: copy Get-Date into PowerShell and press Enter to print the date.",
    "Complete this CAPTCHA by selecting the bicycles.",
    "Press the Windows key to open the Start menu.",
    "University library opening hours and examination schedule.",
    "Installation guide: open a terminal, paste python --version and press Enter.",
    "PowerShell tutorial: paste Get-Date and press Enter. There is no verification or browser repair claim.",
    "Never paste commands into Windows Run to verify you are human.",
])
def test_legitimate_text_is_not_suspicious(text):
    assert analyze(text).verdict == "no_suspicious_signals"


def test_reporting_conflict_and_overlay():
    text = 'Security article: attackers say "Verify you are human. Press Win+R, Ctrl+V and Enter."'
    assert analyze(text).verdict == "uncertain"
    assert analyze(text, inside_dialog=True).verdict == "suspicious"


def test_partial_and_truncated():
    assert analyze("Verify you are human. Open PowerShell.").verdict == "uncertain"
    result = Detector().analyze(AnalyzeRequest(scan_id="test", blocks=[], extraction={"truncated": True}))
    assert result.verdict == "uncertain"
