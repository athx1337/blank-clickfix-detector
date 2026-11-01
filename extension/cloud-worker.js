/* Loaded only by the trusted background worker. No content-script credential API. */
const blank_previews = new Map();
let blank_cloud_flight = null;
let blank_cloud_generation = 0;
let blank_cloud_cooldown = 0;

function blank_cloud_cancel(tabId) {
  if(tabId===undefined || blank_cloud_flight?.tabId===tabId) {
    blank_cloud_flight?.controller.abort(); blank_cloud_flight=null;
  }
  if(tabId===undefined) {blank_previews.clear(); blank_cloud_generation++;}
  else blank_previews.delete(tabId);
}

async function blank_cloud_settings() {
  const {blank_cloud_provider='groq',blank_semantic_enabled=false}=await chrome.storage.local.get(['blank_cloud_provider','blank_semantic_enabled']);
  const keys=await chrome.storage.session.get(['blank_cloud_key_groq','blank_cloud_key_gemini']);
  return {provider:blank_cloud_provider,semantic_enabled:blank_semantic_enabled,
    configured:Object.fromEntries(Object.keys(BlankCloud.providers).map(p=>[p,Boolean(keys[`blank_cloud_key_${p}`])])),
    models:Object.fromEntries(Object.entries(BlankCloud.providers).map(([p,v])=>[p,v.model]))};
}

async function blank_cloud_dispatch(message) {
  switch(message.type) {
    case 'blank_cloud_settings': return blank_cloud_settings();
    case 'blank_cloud_configure': {
      const p=message.provider;
      if(!Object.hasOwn(BlankCloud.providers,p)) throw Error('Unknown provider.');
      if(typeof message.key!=='string'||message.key.trim().length<16||message.key.length>512||/\s/.test(message.key.trim())) throw Error('Invalid key format.');
      if(!await chrome.permissions.contains({origins:[BlankCloud.providers[p].origin]})) throw Error('Provider access was not granted.');
      blank_cloud_cancel();
      await chrome.storage.session.set({[`blank_cloud_key_${p}`]:message.key.trim()});
      await chrome.storage.local.set({blank_cloud_provider:p});
      return {saved:true};
    }
    case 'blank_cloud_forget': {
      blank_cloud_cancel();
      await chrome.storage.session.remove(['blank_cloud_key_groq','blank_cloud_key_gemini']);
      return {forgotten:true};
    }
    case 'blank_cloud_cancel': blank_cloud_cancel(message.tab_id); return {cancelled:true};
    case 'blank_cloud_preview': {
      const {provider}=await blank_cloud_settings();
      const local=await blank_manual_scan(message.tab_id);
      if(!local?.scan_id) throw Error('Run a successful local scan on a supported page first.');
      const epoch=blank_epochs.get(message.tab_id);
      const extracted=await chrome.tabs.sendMessage(message.tab_id,{type:'blank_extract'},{frameId:0});
      if(blank_epochs.get(message.tab_id)!==epoch) throw Error('Page changed. Rescan first.');
      const ranked=[...extracted.blocks].sort((a,b)=>
        Number(local.findings.some(f=>f.block_id===b.block_id))-Number(local.findings.some(f=>f.block_id===a.block_id)));
      const blocks=[]; let size=0;
      for(const block of ranked) if(blocks.length<6 && size+Array.from(block.text).length<=6000) {
        blocks.push(block); size+=Array.from(block.text).length;
      }
      if(!blocks.length) throw Error('No instruction passages available for cloud analysis.');
      const preview={nonce:crypto.randomUUID(),tabId:message.tab_id,epoch,provider,extracted,blocks,
        generation:blank_cloud_generation,expires:Date.now()+300000,local_verdict:local.verdict};
      blank_previews.set(message.tab_id,preview);
      return {nonce:preview.nonce,provider,model:BlankCloud.providers[provider].model,blocks,local_result:local,
        omitted_blocks:extracted.blocks.length-blocks.length};
    }
    case 'blank_cloud_analyze': {
      const preview=blank_previews.get(message.tab_id);
      if(!preview||preview.nonce!==message.nonce||preview.expires<Date.now()||message.confirmed!==true||
        preview.epoch!==blank_epochs.get(message.tab_id)||preview.generation!==blank_cloud_generation) throw Error('Preview expired. Review passages again.');
      if(!Array.isArray(message.block_ids)||!message.block_ids.length||new Set(message.block_ids).size!==message.block_ids.length||
        message.block_ids.some(id=>!preview.blocks.some(b=>b.block_id===id))) throw Error('Invalid passage selection.');
      const blocks=preview.blocks.filter(b=>message.block_ids.includes(b.block_id));
      BlankCloud.checkBlocks(blocks);
      const provider=preview.provider, config=BlankCloud.providers[provider];
      const { [ `blank_cloud_key_${provider}` ]:key }=await chrome.storage.session.get(`blank_cloud_key_${provider}`);
      if(!key) return {status:'key_required',provider,model:config.model};
      if(!await chrome.permissions.contains({origins:[config.origin]})) return {status:'permission_required',provider,model:config.model};
      const current=await chrome.tabs.sendMessage(message.tab_id,{type:'blank_extract'},{frameId:0}).catch(()=>null);
      if(current?.document_key!==preview.extracted.document_key||current?.revision!==preview.extracted.revision) throw Error('Instructions changed. Review a fresh preview.');
      if(preview.generation!==blank_cloud_generation||preview.epoch!==blank_epochs.get(message.tab_id)||blank_previews.get(message.tab_id)!==preview) throw Error('Preview expired.');
      if(Date.now()<blank_cloud_cooldown) return {status:'quota_exceeded',provider,model:config.model};
      blank_cloud_flight?.controller.abort();
      const flight={tabId:message.tab_id,controller:new AbortController()}; blank_cloud_flight=flight;
      const request_id=crypto.randomUUID(), started=performance.now();
      let result;
      try {
        const assessment=await BlankCloud.request(provider,key,blocks,flight.controller.signal);
        result={status:'completed',...assessment};
      } catch(error) {
        result={status:error.code||'provider_unavailable'};
        if(result.status==='quota_exceeded') blank_cloud_cooldown=Date.now()+30000;
      }
      const latest=await chrome.tabs.sendMessage(message.tab_id,{type:'blank_extract'},{frameId:0}).catch(()=>null);
      if(blank_cloud_flight!==flight||preview.epoch!==blank_epochs.get(message.tab_id)||
        preview.generation!==blank_cloud_generation||latest?.document_key!==preview.extracted.document_key||latest?.revision!==preview.extracted.revision) return {status:'cancelled'};
      blank_cloud_flight=null;
      return {...result,provider,model:config.model,request_id,document_key:preview.extracted.document_key,
        revision:preview.extracted.revision,processing_ms:Math.round(performance.now()-started),
        local_verdict:preview.local_verdict,disagreement:result.status==='completed'&&result.verdict!==preview.local_verdict};
    }
    default: throw Error('Unknown cloud operation.');
  }
}
