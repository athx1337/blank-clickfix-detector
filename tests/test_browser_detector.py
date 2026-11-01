"""Cross-runtime contract: exported browser inference must agree with Python."""
import json
import subprocess

import pytest

from backend.config import ROOT
from backend.detector import Detector
from backend.schemas import AnalyzeRequest
from ml.export_browser import export_browser
from ml.train import train


@pytest.fixture(scope="module")
def browser_model(tmp_path_factory):
    directory = tmp_path_factory.mktemp("browser-model")
    train(ROOT / "data/seed.jsonl", directory)
    export_browser(directory, directory / "export")
    return directory


def run_browser(directory, requests, model=True):
    script = """
const fs = require('node:fs');
require('./extension/detector.js');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const rules = JSON.parse(fs.readFileSync(input.directory + '/export/rules.json', 'utf8'));
const model = input.model ? JSON.parse(fs.readFileSync(input.directory + '/export/model.json', 'utf8')) : null;
const detector = new BlankDetector(rules, model);
process.stdout.write(JSON.stringify(input.requests.map(r => detector.analyze(r))));
"""
    result = subprocess.run(["node", "-e", script], input=json.dumps({
        "directory": str(directory), "requests": requests, "model": model,
    }), text=True, encoding="utf-8", capture_output=True, check=True, cwd=ROOT)
    return json.loads(result.stdout)


@pytest.mark.parametrize("use_model", [True, False])
def test_browser_python_parity(browser_model, use_model):
    rows = [json.loads(line) for line in (ROOT / "data/seed.jsonl").read_text().splitlines()]
    # Regression variations are parity checks, never additional research test samples.
    texts = [r["text"] for r in rows] + [
        "😀 Verify you are human. Press Ｗｉｎ＋Ｒ, paste with Ctrl+V and press Enter.",
        "Verify you are hu\u200bman. Press Win+R, paste and press Enter.",
        "Never paste and run commands for human verification in the Windows Run dialog.",
        "No verification or browser repair. Open terminal and paste a command then press Enter.",
        "é 中文 İ 𐐀 security check powershell paste Enter", "Ordinary campus news",
        "captcha powershell épaste pasteé enter", "captcha powershell paste enteré",
    ]
    requests = [{"scan_id": f"parity_{i}", "blocks": [{"block_id": "b", "text": text,
                 "context": {"inside_dialog": dialog, "has_copy_button": True}}],
                 "extraction": {"truncated": i % 7 == 0}}
                for i, text in enumerate(texts) for dialog in [False, True]]
    detector = Detector(browser_model if use_model else None)
    actual = run_browser(browser_model, requests, use_model)
    for request, result in zip(requests, actual):
        expected = detector.analyze(AnalyzeRequest.model_validate(request)).model_dump()
        assert result["verdict"] == expected["verdict"], request
        assert result["detector_mode"] == expected["detector_mode"]
        assert result["model_version"] == expected["model_version"]
        assert [f["code"] for f in result["findings"]] == [f["code"] for f in expected["findings"]]
        assert [f["evidence"] for f in result["findings"]] == [f["evidence"] for f in expected["findings"]]
        if use_model:
            assert result["model_scores"]["b"] == pytest.approx(expected["model_scores"]["b"], abs=1e-6)


def test_browser_rejects_invalid_input(browser_model):
    script = """
const fs = require('node:fs'); require('./extension/detector.js');
const rules = JSON.parse(fs.readFileSync(process.argv[1] + '/export/rules.json'));
const d = new BlankDetector(rules, null);
const invalid = [null, {}, {scan_id:'a',blocks:[{block_id:'b',text:'x',context:{has_code:'yes'}}]},
 {scan_id:'a',blocks:[{block_id:'b',text:'x'},{block_id:'b',text:'x'}]},
 {scan_id:'a',blocks:[{block_id:'b',text:'x'.repeat(2001)}]},
 {scan_id:'a',blocks:[],extraction:{truncated:'false'}}, {scan_id:'a',blocks:[],extraction:null}];
for (const input of invalid) {let rejected=false;try {d.analyze(input)} catch {rejected=true}
 if(!rejected) throw Error('Invalid input accepted');}
const bad = new BlankDetector(rules, {schema_version:999});
if(bad.analyze({scan_id:'a',blocks:[]}).detector_mode !== 'rules_only') throw Error('Bad fallback');
"""
    subprocess.run(["node", "-e", script, str(browser_model)], cwd=ROOT, check=True)


def test_packaged_data_matches_export(browser_model):
    for filename in ("rules.json", "model.json"):
        expected = json.loads((browser_model / "export" / filename).read_text(encoding="utf-8"))
        actual = json.loads((ROOT / "extension/assets" / filename).read_text(encoding="utf-8"))
        assert actual == expected, "Re-export bundled detector after training/rule changes"
