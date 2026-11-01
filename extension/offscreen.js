/* Offscreen document coordinator running in isolated extension context.
   Communicates with a dedicated Web Worker to execute ONNX WebAssembly. */

let worker = null;
let currentResolve = null;
let currentReject = null;

function initWorker() {
  if (worker) return;
  worker = new Worker(chrome.runtime.getURL('semantic-worker.js'), { type: 'module' });
  worker.onmessage = (event) => {
    const { result, error } = event.data;
    if (error) {
      if (currentReject) currentReject(new Error(error));
    } else {
      if (currentResolve) currentResolve(result);
    }
    currentResolve = null;
    currentReject = null;
  };
  worker.onerror = (err) => {
    if (currentReject) currentReject(new Error(err.message || 'Worker failure'));
    currentResolve = null;
    currentReject = null;
    worker.terminate();
    worker = null;
  };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.target !== 'blank_offscreen') return false;
  if (message.type === 'blank_semantic_infer') {
    try {
      initWorker();
      let timer = null;
      const promise = new Promise((resolve, reject) => {
        timer = setTimeout(() => reject(new Error('Semantic infer timed out')), 3200);
        currentResolve = (val) => { clearTimeout(timer); resolve(val); };
        currentReject = (err) => { clearTimeout(timer); reject(err); };
      });
      worker.postMessage({ id: message.id, blocks: message.blocks });
      promise.then(res => sendResponse(res)).catch(err => sendResponse({ error: err.message }));
    } catch (err) {
      sendResponse({ error: err.message });
    }
    return true; // Keep message channel open for async response
  }
  if (message.type === 'blank_read_clipboard') {
    (async () => {
      let text = '';
      try {
        const timeout = new Promise(resolve => setTimeout(() => resolve(''), 300));
        const readTask = (async () => {
          if (navigator.clipboard?.readText) {
            return (await navigator.clipboard.readText()) || '';
          }
          return '';
        })();
        text = await Promise.race([readTask, timeout]);
      } catch (err) {}
      if (!text) {
        try {
          const textarea = document.createElement('textarea');
          document.body.appendChild(textarea);
          textarea.focus();
          textarea.select();
          document.execCommand('paste');
          text = textarea.value;
          textarea.remove();
        } catch (e) {}
      }
      sendResponse({ text: text || '' });
    })();
    return true;
  }
});
