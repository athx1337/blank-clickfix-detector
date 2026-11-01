import re
from dataclasses import dataclass

from backend.features import evidence, extract_features
from backend.schemas import Block, Finding


@dataclass
class RuleResult:
    verdict: str
    findings: list[Finding]
    execution_lure: bool


def match_rules(block: Block, use_context: bool = True) -> RuleResult:
    f = extract_features(block.text)
    dialog = use_context and block.context.inside_dialog
    findings = []

    def add(code, message, keys):
        findings.append(Finding(code=code, message=message, block_id=block.block_id,
                                evidence=evidence(block.text, f, keys)))

    lure = f.has("verification") or f.has("repair")
    sequence = f.has("system") and f.has("paste") and f.has("execute")
    run_sequence = f.has("run_dialog") and f.has("paste") and f.has("execute")
    # Direct negated advice is not a request to execute. Dialog/reporting conflict remains visible.
    if f.has("negation") and not dialog:
        return RuleResult("no_suspicious_signals", [], False)
    strong = False
    if f.has("verification") and sequence:
        strong = True
        add("VERIFICATION_WITH_SYSTEM_EXECUTION", "Verification instructions request system command execution.",
            ["verification", "system", "paste", "execute"])
    if f.has("repair") and sequence:
        strong = True
        add("REPAIR_WITH_PASTE_AND_RUN", "Browser repair instructions request pasting and running a command.",
            ["repair", "system", "paste", "execute"])
    if f.has("command") and f.has("paste") and f.has("execute"):
        strong = True
        add("SUSPICIOUS_COMMAND_IN_INSTRUCTION_CONTEXT", "Execution instructions include a risky command pattern.",
            ["command", "paste", "execute"])
    if not lure and run_sequence:
        strong = True
        add("SUSPICIOUS_SYSTEM_EXECUTION_SEQUENCE", "Instructions request opening Windows Run, pasting clipboard content, and executing it.",
            ["run_dialog", "paste", "execute"])
    if lure and f.has("system") and f.has("paste") and dialog and block.context.has_copy_button:
        strong = True
        add("DIALOG_LURE_WITH_COPY_AND_SYSTEM_PASTE", "A verification or repair dialog combines copying and system paste instructions.",
            ["system", "paste"])
    has_img = bool(re.search(r"\[Instruction Image:\s*[^\]]+\]", block.text, re.I))
    has_img_instructions = bool(re.search(r"\[Instruction Image:\s*[^\]]*(?:step\s*\d|powershell|cmd(?:\.exe)?|terminal|shortcut|\bpress\b|\bpaste\b|\bexecute\b|run\s+command)[^\]]*\]", block.text, re.I))
    if f.has("verification") and has_img:
        if dialog or block.context.has_copy_button or f.has("system") or f.has("paste") or has_img_instructions:
            strong = True
            add("INSTRUCTION_IMAGE_VERIFICATION_LURE", "Verification instructions display an instructional image to evade text inspection.",
                ["verification"])
        else:
            partial = True
    if strong and f.has("reporting") and not dialog:
        add("CONFLICTING_EDUCATIONAL_CONTEXT", "The passage may be reporting an attack rather than requesting it.",
            ["reporting"])
        return RuleResult("uncertain", findings, True)
    if strong:
        return RuleResult("suspicious", findings, True)
    partial = lure and f.has("system")
    if partial:
        add("PARTIAL_SYSTEM_EXECUTION_LURE", "A verification or repair claim refers to a system command interface.",
            ["verification", "repair", "system"])
    return RuleResult("uncertain" if partial else "no_suspicious_signals", findings, partial)
