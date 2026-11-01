"""Author-defined synthetic seed. No record is a sourced incident or human-reviewed observation."""
import json
from pathlib import Path

# Two related examples per family. These are text data, never executable demo behavior.
FAMILIES = [
    ("clickfix", "verification", [
        "Human verification required. Open Windows Run, paste the check and press Enter.",
        "To finish human verification, open the Run dialog, paste the token and hit Enter."]),
    ("clickfix", "verification", [
        "Prove you are human. Press Win+R followed by Ctrl+V and Enter.",
        "Prove you are human to continue: Win + R, Ctrl + V, Enter."]),
    ("clickfix", "verification", [
        "Verify you are human. Open PowerShell, paste the verification code, then run it.",
        "Verify you are human by opening PowerShell. Paste the code and press Enter."]),
    ("clickfix", "verification", [
        "Confirm you are not a robot. Open command prompt, paste the code and execute.",
        "Confirm you are not a robot: launch CMD, paste this check, press Enter."]),
    ("clickfix", "verification", [
        "Security check before your download. Open Windows Run, paste the access code and Enter.",
        "For the security check, open the Run box. Paste the copied code and hit Enter."]),
    ("clickfix", "verification", [
        "Complete CAPTCHA in Terminal. Paste the copied challenge and press Enter.",
        "CAPTCHA step: open Terminal, paste the challenge, then execute it."]),
    ("clickfix", "verification", [
        "Anti-bot check. Open Windows Run and paste the token. Press Enter to unlock the page.",
        "The anti-bot service requires Windows Run. Paste the validation and hit Enter."]),
    ("clickfix", "verification", [
        "Verify you are human. Press W i n + R, then Ctrl + V, then Enter.",
        "Verify you are human. Press Win\u200b+R and paste the code. Hit Enter."]),
    ("clickfix", "repair", [
        "Repair your browser. Open PowerShell, paste the repair text and press Enter.",
        "Repair the browser by opening PowerShell. Paste the copied fix and run it."]),
    ("clickfix", "repair", [
        "Fix Chrome to view this document. Press Win+R, Ctrl+V and Enter.",
        "To fix your Chrome, open the Run dialog, paste the code and hit Enter."]),
    ("clickfix", "repair", [
        "Update your browser immediately. Open CMD, paste the update code and execute.",
        "Update the browser using command prompt: paste the update and press Enter."]),
    ("clickfix", "repair", [
        "Browser error prevents playback. Open Windows Run, paste the fix, press Enter.",
        "Browser error recovery: Win+R, paste the recovered text, then hit Enter."]),
    ("clickfix", "repair", [
        "Connection error. Open PowerShell and paste the recovery text. Run it to restore access.",
        "Connection repair needed: open Terminal, paste the recovery and press Enter."]),
    ("clickfix", "repair", [
        "Restore your browser. Open Windows Run, paste the code and execute it.",
        "Restore the browser by using Win+R. Paste the copied repair and Enter."]),
    ("clickfix", "repair", [
        "Fix Edge to continue. Open command prompt. Paste the code and press Enter.",
        "Fix your Edge browser: launch CMD, paste the check and run it."]),
    ("clickfix", "repair", [
        "Video error repair. Open Terminal, paste the diagnostic fix and hit Enter.",
        "A video error requires a fix. In PowerShell paste the code and execute it."]),
    ("legitimate", "captcha", [
        "Please select every picture containing a bicycle to complete this CAPTCHA.",
        "CAPTCHA challenge: choose the bicycle images and submit your answer."]),
    ("legitimate", "captcha", [
        "Verify you are human by checking the box on this page.",
        "To verify you are human, tick the checkbox and wait for confirmation."]),
    ("legitimate", "captcha", [
        "Human verification: type the six letters shown in the picture.",
        "For human verification enter the displayed letters into the webpage field."]),
    ("legitimate", "captcha", [
        "Security check complete. You can continue browsing the library.",
        "The security check succeeded. Continue to the requested course material."]),
    ("legitimate", "installation", [
        "Python installation guide. Open PowerShell and paste python --version, then press Enter.",
        "In this Python setup tutorial, copy python --version into Terminal and press Enter."]),
    ("legitimate", "installation", [
        "Node installation documentation: in command prompt run node --version to inspect your installation.",
        "Open CMD after installing Node. Type node --version to check the installed release."]),
    ("legitimate", "powershell_tutorial", [
        "PowerShell lesson: paste Get-Date into the terminal and press Enter. It displays the current date.",
        "Copy button: Get-Date. Paste this PowerShell tutorial example and hit Enter to print the date."]),
    ("legitimate", "powershell_tutorial", [
        "PowerShell arrays tutorial. Copy the example into your terminal to learn list indexing.",
        "This documentation explains arrays in PowerShell with examples and a copy button."]),
    ("legitimate", "windows_troubleshooting", [
        "Windows network troubleshooting guide. Open Settings and select the built-in troubleshooter.",
        "For network troubleshooting on Windows, use Settings and review the connection details."]),
    ("legitimate", "windows_troubleshooting", [
        "Fix the browser by clearing cached files in its settings. Restart Chrome normally.",
        "Browser error help: clear cached images through Settings, then reopen your browser."]),
    ("legitimate", "security_reporting", [
        "Security article: attackers say verify you are human, open Windows Run, paste code and press Enter.",
        "Security report: attackers instruct victims to complete human verification in PowerShell, paste and execute."]),
    ("legitimate", "security_reporting", [
        "Never paste unknown commands into Windows Run to verify you are human.",
        "Do not paste a website command into PowerShell to complete human verification."]),
    ("legitimate", "ordinary", [
        "The campus library opens at nine. Borrow books using your student identity card.",
        "Library timetable: opening at 9 AM with book returns accepted at the front desk."]),
    ("legitimate", "ordinary", [
        "Our student photography club meets every Friday for a workshop.",
        "Join the photography workshop on Friday and bring your camera."]),
    ("legitimate", "technical_reference", [
        "The Windows key opens Start. Ctrl+V pastes text in ordinary applications.",
        "Keyboard reference: use the Windows key for Start, or paste text with Ctrl+V."]),
    ("legitimate", "technical_reference", [
        "Copy button accessibility guide. Use a descriptive label and announce when text is copied.",
        "Web accessibility tutorial: a copy button should report its status without moving keyboard focus."]),
]


def main():
    rows = []
    for family, (label, scenario, texts) in enumerate(FAMILIES):
        for variant, text in enumerate(texts):
            rows.append({"id": f"seed_{family:02}_{variant}", "text": text, "label": label,
                         "scenario": scenario, "template_group": f"authored_family_{family:02}",
                         "source": "BLANK authored synthetic seed; not an observed incident",
                         "source_type": "synthetic", "synthetic": True, "review_status": "unreviewed",
                         "review_notes": "Author-assigned demonstration label; human review pending.",
                         "context": {"inside_dialog": label == "clickfix", "has_code": "tutorial" in scenario,
                                     "has_copy_button": label == "clickfix" or "copy" in text.lower()}})
    path = Path(__file__).with_name("seed.jsonl")
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {len(rows)} synthetic examples in {len(FAMILIES)} families")


if __name__ == "__main__":
    main()
