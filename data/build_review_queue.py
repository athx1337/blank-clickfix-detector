"""Author inert review candidates with source references, never human-review claims."""
import json
from pathlib import Path

ATTACK_SOURCE = "https://www.microsoft.com/en-us/security/blog/2025/08/21/think-before-you-clickfix-analyzing-the-clickfix-social-engineering-technique/"
REPAIR_SOURCE = "https://www.microsoft.com/en-us/security/blog/2026/02/05/clickfix-variant-crashfix-deploying-python-rat-trojan/"
DOC_SOURCE = "https://learn.microsoft.com/en-us/powershell/scripting/learn/ps101/01-getting-started"
REPORT_SOURCE = "https://www.microsoft.com/en-us/security/blog/2026/08/05/macos-clickfix-campaign-learned-hide/"

LURES = ["Complete the human check", "Confirm you are not automated", "Unlock access to this document",
         "Finish the required security step", "Validate your browser session", "Restore the failed video player",
         "Recover from the browser crash", "Resolve the stalled meeting screen", "Repair the blocked connection",
         "Resume the interrupted download"]
ACTIONS = ["Open the Windows execution window, insert the supplied text, and confirm it.",
           "Press Win+R, paste the supplied material, and press Enter."]
LEGITIMATE = [
    "This PowerShell lesson explains how to open a terminal and run a command you wrote. No verification is required.",
    "The CAPTCHA asks you to select traffic lights and submit the result inside the webpage.",
    "A security report describes an attacker asking a victim to open Run and paste a command. Do not follow that request.",
    "The installation guide provides a package command, explains every argument, and asks you to review it before using a terminal.",
    "To fix the browser, open its settings, clear the documented cache, and restart it. No system command is requested.",
    "Never paste unknown commands into PowerShell for a human verification check.",
    "A quotation in this security article says: verify you are human, press Win+R, paste, and press Enter. This is an attack example.",
    "The developer console tutorial asks you to inspect a local variable in a page you are building.",
    "A classroom exercise compares a fake system-execution CAPTCHA with a real image-selection CAPTCHA.",
    "The troubleshooting documentation explains why an old terminal command fails and recommends the graphical repair tool.",
    "Copy the project directory name into your editor's search box. Confirm the match in the editor.",
    "Select the meeting link, open it in a new browser tab, and allow camera access if desired.",
    "The browser crashed. Reopen it from the Start menu and restore your tabs using its built-in recovery button.",
    "Use the Windows Run dialog to open a documented system settings panel. This article contains no verification or pasted command.",
    "The page has a copy button beside a short configuration example. It does not ask you to execute it.",
    "A help page explains what the Windows key does and how to use accessibility shortcuts.",
    "A local lab displays disabled attack instructions for classroom discussion. The example is not an access requirement.",
    "The download page asks you to save a source archive and read its installation documentation.",
    "An ordinary campus page lists examination dates, room changes, and club events.",
    "A security awareness reminder says that a real human verification check should not require system command execution.",
]


def build():
    rows = []
    for lure_index, lure in enumerate(LURES):
        for action_index, action in enumerate(ACTIONS):
            rows.append({"text": f"{lure}. {action} [INERT EDUCATIONAL RECREATION; NO COMMAND]",
                         "proposed_label": "clickfix", "source": ATTACK_SOURCE if lure_index < 5 else REPAIR_SOURCE})
    for text in LEGITIMATE:
        rows.append({"text": text, "proposed_label": "legitimate",
                     "source": REPORT_SOURCE if "security" in text.lower() else DOC_SOURCE})
    for i, row in enumerate(rows):
        row.update(id=f"blank-review-{i:03}", template_group=f"review-authored-{i:03}",
                   source_type="authored_candidate_with_background_reference", synthetic=True,
                   review_status="unreviewed", observed_at=None, research_eligible=False,
                   review_notes="Assistant-authored; reference is background, not a verbatim observation or verified label. Independently review intent, provenance, rights and family relationships. Educational marker may affect model behavior; do not train directly.")
    return rows


if __name__ == "__main__":
    destination = Path(__file__).with_name("review-queue.jsonl")
    destination.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in build()),
                           encoding="utf-8", newline="\n")
