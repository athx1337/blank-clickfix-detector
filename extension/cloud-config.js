/* BLANK.ai API client default settings - BYOK (Bring Your Own Key) */
const BLANK_AI_CONFIG = Object.freeze({
  provider: 'groq',
  endpoint: 'https://api.groq.com/openai/v1/chat/completions',
  model: 'openai/gpt-oss-20b',
  apiKey: ''
});

if (typeof self !== 'undefined') self.BLANK_AI_CONFIG = BLANK_AI_CONFIG;
if (typeof window !== 'undefined') window.BLANK_AI_CONFIG = BLANK_AI_CONFIG;
