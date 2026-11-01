const {test} = require('node:test');
const assert = require('node:assert/strict');
require('../extension/cloud.js');
const blocks = [{block_id:'b',text:'Verify yourself. Open Run and paste the copied text.',context:{}}];
const good = {verdict:'suspicious',findings:[{block_id:'b',evidence:'Open Run',message:'Requests a system interface.'}]};
test('cloud assessment must cite submitted text and obey bounds', () => {
  assert.deepEqual(BlankCloud.validate(good,blocks),good);
  for(const bad of [null, {...good,extra:true}, {...good,verdict:'safe'},
    {...good,findings:[{...good.findings[0],evidence:'fabricated'}]},
    {...good,findings:[{...good.findings[0],block_id:'other'}]},
    {...good,findings:[]}, {...good,findings:[{...good.findings[0],message:'x'.repeat(241)}]}]) {
    assert.throws(() => BlankCloud.validate(bad,blocks));
  }
});
test('requests use fixed origins and headers, no tools or URL fields', async () => {
  for(const provider of ['groq','gemini']) {
    let called;
    const fake = async (url,options) => {
      called = {url,options};
      const payload = provider==='groq' ? {choices:[{message:{content:JSON.stringify(good)}}]} :
        {candidates:[{content:{parts:[{text:JSON.stringify(good)}]},finishReason:'STOP'}]};
      return new Response(JSON.stringify(payload),{headers:{'Content-Type':'application/json'}});
    };
    const actual=await BlankCloud.request(provider,'fixture-personal-key',blocks,new AbortController().signal,fake);
    assert.equal(actual.verdict,'suspicious');
    assert.equal(called.options.redirect,'error');
    assert.equal(called.options.credentials,'omit');
    assert.ok(!called.url.includes('fixture-personal-key'));
    assert.ok(!called.options.body.includes('fixture-personal-key'));
    assert.ok(!('tools' in JSON.parse(called.options.body)));
  }
  await assert.rejects(BlankCloud.request('unknown','key',blocks),/provider/);
});
test('operational failures are distinct and never clean verdicts', async () => {
  for(const [status,code] of [[401,'authentication_error'],[403,'permission_error'],[429,'quota_exceeded'],[500,'provider_unavailable']]) {
    await assert.rejects(BlankCloud.request('groq','key',blocks,undefined,async()=>new Response('secret upstream error',{status})),e=>e.code===code && !e.message.includes('secret'));
  }
  for(const body of ['x'.repeat(65537),JSON.stringify({choices:[]}),JSON.stringify({choices:[{message:{content:'not json'}}]})]) {
    await assert.rejects(BlankCloud.request('groq','key',blocks,undefined,async()=>new Response(body)));
  }
  await assert.rejects(BlankCloud.request('groq','key',Array(7).fill(blocks[0])));
});
