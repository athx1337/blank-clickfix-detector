import { AutoTokenizer, env } from '@huggingface/transformers';
import * as ort from 'onnxruntime-web';

// Ensure 100% offline execution; never make outbound network requests for models
env.allowRemoteModels = false;
env.allowLocalModels = true;
env.useBrowserCache = false;
env.useCustomCache = false;

export { AutoTokenizer, env, ort };
