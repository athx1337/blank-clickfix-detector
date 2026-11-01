// Provide safe fallback if any library checks global chrome in Web Worker context
globalThis.chrome = globalThis.chrome || {
  runtime: {
    getURL: (path) => new URL(path, (typeof location !== 'undefined' ? location.href : '')).href
  }
};
if (typeof self !== 'undefined') {
  self.chrome = globalThis.chrome;
}
var chrome = globalThis.chrome;

// Intercept Cache API in Web Worker to prevent Chrome's "Request scheme 'chrome-extension' is unsupported" error
if (typeof caches !== 'undefined' && caches && caches.open) {
  const origOpen = caches.open.bind(caches);
  caches.open = async (cacheName) => {
    try {
      const c = await origOpen(cacheName);
      return {
        match: (...args) => c.match(...args).catch(() => undefined),
        put: async () => {}, // Suppress unsupported chrome-extension: scheme error
        delete: (...args) => c.delete(...args).catch(() => false),
        keys: (...args) => c.keys(...args).catch(() => [])
      };
    } catch {
      return {
        match: async () => undefined,
        put: async () => {},
        delete: async () => false,
        keys: async () => []
      };
    }
  };
}

// Dynamically import transformers after polyfills and cache interception are established
const { AutoTokenizer, env, ort } = await import('./assets/semantic/transformers.bundle.js');

// Resolve extension asset URLs strictly using standard Web Worker location semantics
const getAssetUrl = (path) => new URL(path, self.location.href).href;

// Strictly local execution; no remote model loading or browser cache put errors
env.allowRemoteModels = false;
env.allowLocalModels = true;
env.useBrowserCache = false;
env.useCustomCache = false;
env.localModelPath = getAssetUrl('assets/semantic/model/');
ort.env.wasm.numThreads = 1;
ort.env.wasm.simd = true;
ort.env.wasm.wasmPaths = getAssetUrl('assets/semantic/wasm/');

let session = null;
let tokenizer = null;
let metadata = null;

async function loadAssets() {
  if (session && tokenizer && metadata) return;
  const metaUrl = getAssetUrl('assets/semantic/classifier.json');
  const metaResp = await fetch(metaUrl);
  metadata = await metaResp.json();

  const modelUrl = getAssetUrl('assets/semantic/model/onnx/model_quantized.onnx');
  const modelResp = await fetch(modelUrl);
  const buffer = await modelResp.arrayBuffer();
  session = await ort.InferenceSession.create(buffer, { executionProviders: ['wasm'], intraOpNumThreads: 1 });

  const modelDirUrl = getAssetUrl('assets/semantic/model/');
  tokenizer = await AutoTokenizer.from_pretrained(modelDirUrl, { local_files_only: true });
}

function tokenWindows(ids, size = 254, overlap = 32, cap = 8) {
  const step = size - overlap;
  const windows = [];
  for (let start = 0; start < Math.max(1, ids.length); start += step) {
    if (windows.length === cap) return { windows, truncated: true };
    windows.push(ids.slice(start, start + size));
    if (start + size >= ids.length) break;
  }
  return { windows, truncated: false };
}

function aggregateEmbeddings(rows) {
  const norms = rows.map(r => {
    let sum = 0;
    for (let i = 0; i < r.length; i++) sum += r[i] * r[i];
    return Math.sqrt(sum) || 1e-12;
  });
  const normalized = rows.map((r, rowIdx) => r.map(val => val / norms[rowIdx]));
  const dim = rows[0].length;
  const average = new Array(dim).fill(0);
  for (let d = 0; d < dim; d++) {
    for (let rowIdx = 0; rowIdx < normalized.length; rowIdx++) {
      average[d] += normalized[rowIdx][d];
    }
    average[d] /= normalized.length;
  }
  let avgNorm = 0;
  for (let d = 0; d < dim; d++) avgNorm += average[d] * average[d];
  avgNorm = Math.sqrt(avgNorm) || 1e-12;
  return average.map(v => v / avgNorm);
}

self.onmessage = async (event) => {
  const { id, blocks } = event.data;
  try {
    await loadAssets();
    const scores = [];
    for (const block of blocks) {
      const text = block.text || '';
      const ids = tokenizer.encode(text, { add_special_tokens: false });
      const { windows, truncated } = tokenWindows(ids);

      const windowVectors = [];
      for (const win of windows) {
        const fullIds = [101, ...win, 102];
        const seqLen = fullIds.length;
        const feeds = {
          input_ids: new ort.Tensor('int64', BigInt64Array.from(fullIds.map(BigInt)), [1, seqLen]),
          attention_mask: new ort.Tensor('int64', new BigInt64Array(seqLen).fill(1n), [1, seqLen]),
          token_type_ids: new ort.Tensor('int64', new BigInt64Array(seqLen).fill(0n), [1, seqLen])
        };
        const output = await session.run(feeds);
        const data = output.last_hidden_state.data;
        const hiddenDim = 384;
        const pooled = new Array(hiddenDim).fill(0);
        for (let t = 0; t < seqLen; t++) {
          const offset = t * hiddenDim;
          for (let d = 0; d < hiddenDim; d++) pooled[d] += data[offset + d];
        }
        for (let d = 0; d < hiddenDim; d++) pooled[d] /= seqLen;
        windowVectors.push(pooled);
      }

      const vector = aggregateEmbeddings(windowVectors);
      let logit = metadata.intercept;
      for (let d = 0; d < vector.length; d++) {
        logit += vector[d] * metadata.weights[d];
      }
      const score = 1 / (1 + Math.exp(-logit));
      scores.push({ block_id: block.block_id, score, truncated });
    }
    self.postMessage({ id, result: { scores, model_version: metadata.model_version, thresholds: metadata.thresholds } });
  } catch (error) {
    self.postMessage({ id, error: error.message });
  }
};
