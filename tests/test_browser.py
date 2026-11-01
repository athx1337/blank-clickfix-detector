"""Real offline MV3 integration; no API process is started.

The fixture adds loopback host access to a COPY for automated popup-tab testing.
Real toolbar activeTab/permission-prompt acceptance remains a manual browser check.
"""
import functools
import json
import os
import shutil
import threading
import zipfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import pytest

from backend.config import ROOT
from tools.package_extension import package

pytestmark = pytest.mark.browser


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def wait_for_intro(context, worker, extension_id):
    # onInstalled opens Settings asynchronously. Wait before creating a popup tab,
    # or Chrome may reuse that new extension tab for the pending introduction.
    url = f"chrome-extension://{extension_id}/options.html"
    for _ in range(100):
        pages = [page for page in context.pages if page.url == url]
        if pages:
            pages[0].wait_for_load_state("domcontentloaded")
            return
        worker.evaluate("() => new Promise(resolve => setTimeout(resolve, 50))")
    raise AssertionError("First-install introduction did not open")


@pytest.fixture(scope="module")
def browser_lab(tmp_path_factory):
    from playwright.sync_api import expect, sync_playwright

    profile = tmp_path_factory.mktemp("blank-browser")
    extension = profile / "extension"
    shutil.copytree(ROOT / "extension", extension)
    manifest = json.loads((extension / "manifest.json").read_text())
    assert "host_permissions" not in manifest
    manifest["host_permissions"] = ["http://127.0.0.1/*"]
    (extension / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    handler = functools.partial(QuietHandler, directory=str(ROOT / "demo"))
    demos = ThreadingHTTPServer(("127.0.0.1", 8080), handler)
    thread = threading.Thread(target=demos.serve_forever, daemon=True)
    thread.start()
    with sync_playwright() as playwright:
        options = {"channel": "chromium", "headless": True,
                   "args": [f"--disable-extensions-except={extension}", f"--load-extension={extension}"]}
        if os.environ.get("blank_browser_executable"):
            options["executable_path"] = os.environ["blank_browser_executable"]
        context = playwright.chromium.launch_persistent_context(str(profile / "profile"), **options)
        requests = []
        context.on("request", lambda request: requests.append(request.url))
        worker = context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker")
        extension_id = urlparse(worker.url).netloc
        wait_for_intro(context, worker, extension_id)
        page = context.new_page()
        settings = context.new_page()
        settings.goto(f"chrome-extension://{extension_id}/options.html")
        settings.locator("#test").click()
        expect(settings.locator("#status")).to_contain_text("Local detector working")
        assert settings.locator("#token").count() == 0
        settings.close()
        print("Actual automated browser:", context.browser.version)
        yield context, worker, page, extension_id, requests
        assert not [url for url in requests if url.startswith(("https://", "http://"))
                    and not url.startswith("http://127.0.0.1:8080/")], requests
        context.close()
    demos.shutdown()
    demos.server_close()
    thread.join(timeout=5)


def visit(lab, name):
    context, _, page, extension_id, _ = lab
    page.goto(f"http://127.0.0.1:8080/{name}")
    popup = context.new_page()
    popup.goto(f"chrome-extension://{extension_id}/popup.html")
    page.bring_to_front()
    popup.reload()
    popup.wait_for_timeout(150)
    return popup, page


def click_scan(popup):
    from playwright.sync_api import expect

    popup.locator("#scan").click()
    expect(popup.locator("#scan")).to_be_enabled(timeout=10000)
    return popup.locator("#state").inner_text()


def test_offline_manual_scans(browser_lab):
    # No backend exists. Model-only uncertainty on legitimate pages is visible.
    for name, allowed in [("fake-verification.html", ["Suspicious"]),
                          ("fake-troubleshooting.html", ["Suspicious"]),
                          ("legitimate-tutorial.html", ["No suspicious signals found", "Uncertain"]),
                          ("legitimate-verification.html", ["No suspicious signals found", "Uncertain"]),
                          ("ordinary-page.html", ["No suspicious signals found"]),
                          ("reporting.html", ["Uncertain"])]:
        popup, page = visit(browser_lab, name)
        assert click_scan(popup) in allowed
        assert "Hybrid" in popup.locator("#meta").inner_text()
        if allowed == ["Suspicious"]:
            assert popup.locator(".finding").count() > 0
            assert page.locator("[data-blank-warning]").count() == 1
            (ROOT / "test-results").mkdir(exist_ok=True)
            popup.locator("body").screenshot(path=str(ROOT / "test-results/popup-offline.png"))
        popup.close()


def test_extraction_finds_late_split_and_nonkeyword_instructions(browser_lab):
    _, worker, _, _, _ = browser_lab
    popup,page=visit(browser_lab,'ordinary-page.html')
    page.evaluate("""() => {
      const main=document.querySelector('main')||document.body;
      for(let i=0;i<45;i++){const p=document.createElement('p');p.textContent='Campus schedules and ordinary project notes. '.repeat(5);main.append(p)}
      const box=document.createElement('section');
      box.innerHTML='<h2>Verify you are human</h2><ol><li>Open the Windows Run dialog.</li><li>Paste the supplied text.</li><li>Press Enter.</li></ol>';
      main.append(box);
      const novel=document.createElement('dialog');novel.open=true;
      novel.innerHTML='<h2>Additional access step</h2><ol><li>Launch the system execution window.</li><li>Insert the supplied material.</li><li>Confirm to finish.</li></ol>';
      document.body.append(novel);
    }""")
    assert click_scan(popup)=='Suspicious'
    extracted=worker.evaluate("""async()=>{
      const [tab]=await chrome.tabs.query({url:'http://127.0.0.1:8080/*'});
      return chrome.tabs.sendMessage(tab.id,{type:'blank_extract'});
    }""")
    assert any('Launch the system execution window' in b['text'] for b in extracted['blocks'])
    assert all(len(b['text'])<=2000 for b in extracted['blocks'])
    popup.close()


def test_image_lure_clickfix_detected(browser_lab):
    popup, page = visit(browser_lab, 'ordinary-page.html')
    page.evaluate("""() => {
      document.body.innerHTML = `
      <div class="card">
        <div class="recaptcha-img"></div>
        <div class="instructions">
          <h3>What to do? (Windows)</h3>
          <ul>
            <li>Press Windows + R</li>
            <li>Press Ctrl + V</li>
            <li>Press Enter</li>
          </ul>
        </div>
      </div>
      `;
    }""")
    assert click_scan(popup) == 'Suspicious'
    assert popup.locator('.finding').count() > 0
    popup.close()


def test_cloud_without_key_is_optional_and_local_still_works(browser_lab):
    popup,_=visit(browser_lab,'fake-verification.html')
    assert click_scan(popup)=='Suspicious'
    popup.locator('#cloud-preview').click()
    from playwright.sync_api import expect

    expect(popup.locator('#cloud-status')).to_contain_text('your own provider key')
    assert popup.locator('#state').inner_text()=='Suspicious'
    popup.close()


def test_cloud_preview_validation_key_isolation_and_cancellation(browser_lab):
    from playwright.sync_api import expect

    context,worker,_,extension_id,_=browser_lab
    # Permission grant is a test-only Chrome API stub. fetch is also stubbed: no live provider traffic.
    worker.evaluate("""async()=>{
      globalThis.blank_original_contains=chrome.permissions.contains;
      chrome.permissions.contains=async value => value.origins?.some(x=>x.includes('api.groq.com')) ? true : blank_original_contains(value);
    }""")
    settings = context.new_page()
    settings.goto(f"chrome-extension://{extension_id}/options.html")
    configured = settings.evaluate("""()=>chrome.runtime.sendMessage({type:'blank_cloud_configure',provider:'groq',key:'fixture-personal-cloud-key'})""")
    assert configured == {"saved": True}
    settings.close()
    popup, page = visit(browser_lab, "fake-verification.html")
    try:
        assert click_scan(popup) == "Suspicious"
        popup.locator("#cloud-preview").click()
        expect(popup.locator("#cloud-form")).to_be_visible()
        assert popup.locator("#cloud-passages blockquote").count() > 0
        data = worker.evaluate("""async()=>{
          const [tab]=await chrome.tabs.query({url:'http://127.0.0.1:8080/*'});
          return chrome.scripting.executeScript({target:{tabId:tab.id},func:async()=>{
            try{return await chrome.storage.session.get(null)}catch{return {denied:true}}
          }});
        }""")
        assert "fixture-personal-cloud-key" not in json.dumps(data)
        worker.evaluate("""()=>{
          globalThis.blank_original_cloud_request=BlankCloud.request;
          globalThis.blank_original_fetch=fetch;
          globalThis.fetch=async (url,options)=>{
            if(String(url).startsWith('https://api.groq.com/')) {
              const blocks=JSON.parse(JSON.parse(options.body).messages[1].content);
              const result={verdict:'no_suspicious_signals',findings:[{block_id:blocks[0].block_id,evidence:blocks[0].text.slice(0,50),message:'Fixture disagreement.'}]};
              return new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify(result)}}]}));
            }
            return blank_original_fetch(url,options);
          };
        }""")
        popup.locator("#cloud-consent").check()
        popup.locator("#cloud-send").click()
        expect(popup.locator("#cloud-status")).to_contain_text("Disagrees with local analysis")
        assert popup.locator("#state").inner_text() == "Suspicious"
        # A late provider response after navigation must be discarded.
        worker.evaluate("""()=>{globalThis.fetch=async (url,options)=>{
          if(String(url).startsWith('https://api.groq.com/')) {
            globalThis.blank_cloud_test_started=true;
            await new Promise(resolve=>{globalThis.blank_cloud_test_release=resolve});
            return new Response(JSON.stringify({choices:[{message:{content:'{}'}}]}));
          }
          return blank_original_fetch(url,options);
        }}""")
        popup.locator("#cloud-consent").check()
        popup.locator("#cloud-send").click()
        for _ in range(40):
            if worker.evaluate('()=>Boolean(globalThis.blank_cloud_test_started)'):
                break
            page.wait_for_timeout(50)
        assert worker.evaluate('()=>Boolean(globalThis.blank_cloud_test_started)')
        page.goto('http://127.0.0.1:8080/ordinary-page.html')
        worker.evaluate('()=>blank_cloud_test_release()')
        expect(popup.locator('#cloud-status')).to_contain_text('cancelled')
    finally:
        worker.evaluate("""async()=>{
          globalThis.fetch=blank_original_fetch; chrome.permissions.contains=blank_original_contains;
          await chrome.storage.session.remove(['blank_cloud_key_groq','blank_cloud_key_gemini']); blank_cloud_cancel();
        }""")
        popup.close()


def test_private_exclusion_and_storage_isolation(browser_lab):
    _, worker, _, _, _ = browser_lab
    popup, page = visit(browser_lab, "ordinary-page.html")
    page.evaluate("""() => {
      const box = document.createElement('div');
      const lure = ' Verify you are human. Press Win+R, Ctrl+V and Enter.';
      box.innerHTML = '<input value="PRIVATE_INPUT"><textarea>PRIVATE_TEXTAREA'+lure+'</textarea><div contenteditable>PRIVATE_EDITABLE'+lure+'</div><p hidden>PRIVATE_HIDDEN'+lure+'</p><p style="display:none">PRIVATE_CSS'+lure+'</p>';
      document.body.append(box);
    }""")
    assert click_scan(popup) == "No suspicious signals found"
    worker.evaluate("() => chrome.storage.local.set({blank_test_private:'trusted-only'})")
    data = worker.evaluate("""async () => {
      const [tab] = await chrome.tabs.query({url:'http://127.0.0.1:8080/*'});
      const extracted = await chrome.tabs.sendMessage(tab.id,{type:'blank_extract'});
      const storage = await chrome.scripting.executeScript({target:{tabId:tab.id},func:async () => {
        try {return await chrome.storage.local.get(null)} catch {return {denied:true}}
      }});
      await chrome.storage.local.remove('blank_test_private');
      return {extracted,storage};
    }""")
    assert "PRIVATE_" not in json.dumps(data["extracted"])
    assert "trusted-only" not in json.dumps(data["storage"])
    popup.close()


def test_evidence_is_text_and_large_dom_is_uncertain(browser_lab):
    popup, page = visit(browser_lab, "fake-verification.html")
    page.evaluate("""() => {
      const literal = document.createElement('p');
      literal.textContent = '<img src=x onerror="window.blank_injected=true">';
      document.getElementById('title').after(literal);
    }""")
    assert click_scan(popup) == "Suspicious"
    assert "<img" in popup.locator("#findings").inner_text()
    assert popup.locator("#findings img").count() == 0
    assert popup.evaluate("() => window.blank_injected === undefined")
    popup.close()
    popup, page = visit(browser_lab, "ordinary-page.html")
    page.evaluate("""() => {
      const fragment = document.createDocumentFragment();
      for(let i=0;i<6200;i++){const p=document.createElement('p');p.textContent='Ordinary campus information';fragment.append(p)}
      document.body.append(fragment);
    }""")
    assert click_scan(popup) == "Uncertain"
    assert "incomplete" in popup.locator("#meta").inner_text()
    popup.close()


def test_navigation_clears_results(browser_lab):
    _, worker, _, _, _ = browser_lab
    popup, page = visit(browser_lab, "fake-verification.html")
    assert click_scan(popup) == "Suspicious"
    page.goto("http://127.0.0.1:8080/ordinary-page.html")
    page.wait_for_timeout(200)
    assert page.locator("[data-blank-warning]").count() == 0
    result = worker.evaluate("""async () => {
      const [tab]=await chrome.tabs.query({url:'http://127.0.0.1:8080/*'});
      return (await chrome.storage.session.get(`blank_result_${tab.id}`))[`blank_result_${tab.id}`] || null;
    }""")
    assert result is None
    popup.close()


def test_dismissal_survives_unchanged_manual_rescan(browser_lab):
    popup, page = visit(browser_lab, "fake-verification.html")
    assert click_scan(popup) == "Suspicious"
    host = page.locator("[data-blank-warning]")
    box = host.bounding_box()
    # Closed shadow warning: use the actual dismiss button's visible bottom-left position.
    page.mouse.click(box["x"] + 90, box["y"] + box["height"] - 35)
    assert host.count() == 0
    assert click_scan(popup) == "Suspicious"
    assert host.count() == 0
    popup.close()


def test_dynamic_opt_in_and_disable(browser_lab):
    _, worker, _, _, _ = browser_lab
    popup, page = visit(browser_lab, "dynamic.html")
    assert click_scan(popup) == "No suspicious signals found"
    page.locator("#insert").click()
    page.wait_for_timeout(1500)
    assert page.locator("[data-blank-warning]").count() == 0  # disabled means no background scan
    page.reload()
    popup.locator("#auto").check()
    page.wait_for_timeout(1600)
    page.locator("#insert").click()
    page.locator("[data-blank-warning]").wait_for(timeout=12000)
    before = worker.evaluate("async () => JSON.stringify(await chrome.storage.session.get(null))")
    page.wait_for_timeout(5500)
    after = worker.evaluate("async () => JSON.stringify(await chrome.storage.session.get(null))")
    assert before == after
    popup.locator("#auto").uncheck()
    page.reload()
    page.locator("#insert").click()
    page.wait_for_timeout(5500)
    assert page.locator("[data-blank-warning]").count() == 0
    popup.close()


def test_extraction_keeps_unchanged_revision(browser_lab):
    _, worker, _, _, _ = browser_lab
    popup, _ = visit(browser_lab, "fake-verification.html")
    assert click_scan(popup) == "Suspicious"
    snapshots = worker.evaluate("""async () => {
      const [tab] = await chrome.tabs.query({url:'http://127.0.0.1:8080/*'});
      const first = await chrome.tabs.sendMessage(tab.id, {type:'blank_extract'});
      const second = await chrome.tabs.sendMessage(tab.id, {type:'blank_extract'});
      return [first, second];
    }""")
    assert snapshots[0]["revision"] == snapshots[1]["revision"]
    popup.close()


def test_extraction_excludes_editable_root(browser_lab):
    _, worker, _, _, _ = browser_lab
    popup, page = visit(browser_lab, "fake-verification.html")
    assert click_scan(popup) == "Suspicious"
    page.evaluate("() => {document.body.contentEditable = 'true'}")
    extracted = worker.evaluate("""async () => {
      const [tab] = await chrome.tabs.query({url:'http://127.0.0.1:8080/*'});
      return chrome.tabs.sendMessage(tab.id, {type:'blank_extract'});
    }""")
    assert extracted["blocks"] == []
    page.evaluate("() => {document.body.contentEditable = 'false'}")
    popup.close()


def test_pause_all_and_unsupported_page(browser_lab):
    from playwright.sync_api import expect

    context, _, page, extension_id, _ = browser_lab
    popup, page = visit(browser_lab, "dynamic.html")
    popup.locator("#auto").check()
    settings = context.new_page()
    settings.goto(f"chrome-extension://{extension_id}/options.html")
    expect(settings.locator("#sites")).to_contain_text("127.0.0.1")
    settings.locator("#pause").click()
    expect(settings.locator("#sites")).to_contain_text("None")
    page.reload()
    page.locator("#insert").click()
    page.wait_for_timeout(5500)
    assert page.locator("[data-blank-warning]").count() == 0
    settings.close()
    popup.close()
    page.goto("about:blank")
    popup = context.new_page()
    popup.goto(f"chrome-extension://{extension_id}/popup.html")
    page.bring_to_front()
    popup.reload()
    popup.wait_for_timeout(200)
    assert click_scan(popup) == "Unsupported page"
    popup.close()


def test_local_inference_failure_is_unavailable(browser_lab):
    _, worker, _, _, _ = browser_lab
    popup, _ = visit(browser_lab, "ordinary-page.html")
    worker.evaluate("""async () => {
      const detector = await blank_detector;
      globalThis.blank_original_analyze = detector.analyze;
      detector.analyze = () => {throw Error('failure fixture')};
    }""")
    try:
        assert click_scan(popup) == "Scan unavailable"
    finally:
        worker.evaluate("async () => {(await blank_detector).analyze = globalThis.blank_original_analyze}")
        popup.close()


@pytest.mark.parametrize("invalidate", ["opt_out", "navigation"])
def test_invalidation_during_result_commit_discards_session_result(browser_lab, invalidate):
    _, worker, _, _, _ = browser_lab
    popup, _ = visit(browser_lab, "dynamic.html")
    popup.locator("#auto").check()
    worker.evaluate("""async () => {
      const [tab] = await chrome.tabs.query({url:'http://127.0.0.1:8080/*'});
      blank_states.delete(tab.id);
      globalThis.blank_original_store = blank_store_result;
      globalThis.blank_gate = new Promise(resolve => {globalThis.blank_release = resolve});
      blank_store_result = async (...args) => {await blank_gate; return blank_original_store(...args)};
      globalThis.blank_pending_test = blank_analyze(tab.id, {document_key:'race', revision:1,
        blocks:[{block_id:'b',text:'Verify you are human. Press Win+R, paste and press Enter.'}],
        extraction:{}}, true, 'http://127.0.0.1/*');
    }""")
    if invalidate == "opt_out":
        popup.locator("#auto").uncheck()
    else:
        browser_lab[2].goto("http://127.0.0.1:8080/ordinary-page.html")
    try:
        result = worker.evaluate("""async () => {
          blank_release(); await blank_pending_test;
          const [tab] = await chrome.tabs.query({url:'http://127.0.0.1:8080/*'});
          return (await chrome.storage.session.get(`blank_result_${tab.id}`))[`blank_result_${tab.id}`] || null;
        }""")
        assert result is None or result["verdict"] != "suspicious"
    finally:
        worker.evaluate("() => {blank_store_result = blank_original_store}")
        if invalidate == "navigation":
            worker.evaluate("async () => {await chrome.storage.local.set({blank_sites:[]}); await blank_sync_sites()}")
        popup.close()


@pytest.mark.parametrize("broken,expected", [("model", "Rules only"), ("rules", "Scan unavailable")])
def test_bundle_failures(browser_lab, tmp_path, broken, expected):
    from contextlib import nullcontext

    extension = tmp_path / "extension"
    shutil.copytree(ROOT / "extension", extension)
    (extension / f"assets/{broken}.json").write_text("{corrupt", encoding="utf-8")
    manifest = json.loads((extension / "manifest.json").read_text())
    manifest["host_permissions"] = ["http://127.0.0.1/*"]
    (extension / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with nullcontext(browser_lab[0].browser.browser_type) as browser_type:
        options = {"channel": "chromium", "headless": True,
                   "args": [f"--disable-extensions-except={extension}", f"--load-extension={extension}"]}
        if os.environ.get("blank_browser_executable"):
            options["executable_path"] = os.environ["blank_browser_executable"]
        context = browser_type.launch_persistent_context(str(tmp_path / "profile"), **options)
        try:
            worker = context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker")
            extension_id = urlparse(worker.url).netloc
            wait_for_intro(context, worker, extension_id)
            page = context.new_page()
            page.goto("http://127.0.0.1:8080/fake-verification.html")
            popup = context.new_page()
            popup.goto(f"chrome-extension://{extension_id}/popup.html")
            page.bring_to_front()
            popup.reload()
            popup.wait_for_timeout(150)
            state = click_scan(popup)
            if broken == "model":
                assert state == "Suspicious"
                assert expected in popup.locator("#meta").inner_text()
            else:
                assert state == expected
                assert not page.locator("[data-blank-warning]").count()
        finally:
            context.close()


def test_educational_search_results_clean_and_ai_reconciliation(browser_lab):
    popup, page = visit(browser_lab, 'ordinary-page.html')
    page.evaluate("""() => {
      document.body.innerHTML = `
        <main>
          <h1>Search Results: real clickfix sites for testing</h1>
          <div class="ai-overview">
            <p>Safe and legitimate platforms exist to test, learn about, and simulate ClickFix (fake CAPTCHA and clipboard-injection) attacks without exposing your system to real malware:</p>
            <img alt="www.click-fix.nl" src="favicon.ico">
            <ul>
              <li>ClickFix Simulation Hub: An interactive educational website dedicated to understanding ClickFix mechanics.</li>
              <li>ClickFix Awareness App: breaks down how fake Cloudflare verification and auto-copy malicious payloads work.</li>
            </ul>
          </div>
        </main>
      `;
    }""")
    assert click_scan(popup) == "No suspicious signals found"
    assert popup.locator("#findings .oxide-clean-banner").count() == 1
    assert page.locator("[data-blank-warning]").count() == 0
    popup.close()


def test_blank_ai_reconciliation_overrides_heuristic_alert(browser_lab):
    context, worker, _, extension_id, _ = browser_lab
    popup, page = visit(browser_lab, 'fake-verification.html')
    assert click_scan(popup) == "Suspicious"
    assert page.locator("[data-blank-warning]").count() == 1

    reconciliation = worker.evaluate("""async () => {
        const [tab] = await chrome.tabs.query({ url: 'http://127.0.0.1:8080/*' });
        const originalRequest = BlankAI.request;
        BlankAI.request = async () => ({
            status: "completed",
            verdict: "legitimate",
            score: 0.10,
            headline: "Educational Context Verified",
            explanation: "Educational research safe context.",
            reasons: ["Safe test lab"]
        });
        const res = await blank_ai_analyze(tab.id, null);
        BlankAI.request = originalRequest;
        return res;
    }""")
    assert reconciliation.get("reconciled") is True
    assert reconciliation.get("updated_local_verdict") == "no_suspicious_signals"
    assert page.locator("[data-blank-warning]").count() == 0

    badge = worker.evaluate("""async () => {
        const [tab] = await chrome.tabs.query({ url: 'http://127.0.0.1:8080/*' });
        return chrome.action.getBadgeText({ tabId: tab.id });
    }""")
    assert badge == ""
    popup.close()


def test_unmodified_release_zip_starts_without_hosts_or_pairing(browser_lab, tmp_path):
    from playwright.sync_api import expect

    archive_path = package(tmp_path / "dist")
    extension = tmp_path / "unpacked"
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(extension)  # Trusted allowlisted package built just above.
    options = {"channel": "chromium", "headless": True,
               "args": [f"--disable-extensions-except={extension}", f"--load-extension={extension}"]}
    if os.environ.get("blank_browser_executable"):
        options["executable_path"] = os.environ["blank_browser_executable"]
    context = browser_lab[0].browser.browser_type.launch_persistent_context(str(tmp_path / "profile"), **options)
    try:
        worker = context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker")
        permissions = worker.evaluate("() => chrome.permissions.getAll()")
        assert permissions.get("origins", []) == []
        extension_id = urlparse(worker.url).netloc
        wait_for_intro(context, worker, extension_id)
        page = context.new_page()
        page.goto(f"chrome-extension://{extension_id}/options.html")
        page.locator("#test").click()
        expect(page.locator("#status")).to_contain_text("Local detector working · hybrid")
        assert page.locator("#token").count() == 0
        assert "None" in page.locator("#sites").inner_text()
    finally:
        context.close()
