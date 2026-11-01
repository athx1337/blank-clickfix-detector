import esbuild from 'esbuild';
import fs from 'node:fs';
import path from 'node:path';

const rootDir = process.cwd();
const semanticDir = path.join(rootDir, 'extension', 'assets', 'semantic');
const wasmDir = path.join(semanticDir, 'wasm');

fs.mkdirSync(wasmDir, { recursive: true });

// Copy onnxruntime wasm files
const ortDist = path.join(rootDir, 'node_modules', 'onnxruntime-web', 'dist');
const wasmFiles = [
  'ort-wasm-simd-threaded.jsep.wasm',
  'ort-wasm-simd-threaded.wasm',
  'ort-wasm-simd.wasm',
  'ort-wasm.wasm',
  'ort-wasm-simd-threaded.jsep.mjs',
  'ort-wasm-simd-threaded.mjs'
];

for (const file of wasmFiles) {
  const src = path.join(ortDist, file);
  if (fs.existsSync(src)) {
    fs.copyFileSync(src, path.join(wasmDir, file));
  }
}
console.log(`Copied WASM assets to ${wasmDir}`);

// Bundle transformers and onnxruntime-web for browser
await esbuild.build({
  entryPoints: [path.join(rootDir, 'tools', 'transformers-entry.js')],
  bundle: true,
  format: 'esm',
  outfile: path.join(semanticDir, 'transformers.bundle.js'),
  platform: 'browser',
  target: 'es2022',
  minify: true,
  sourcemap: false,
  define: {
    'process.env.NODE_ENV': '"production"'
  }
});
console.log(`Built transformers.bundle.js in ${semanticDir}`);
