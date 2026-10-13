'use strict';
(()=>{
  let history=[], pending=null, aiAvailable=false;
  const toggle=document.querySelector('#chat-toggle');
  const panel=document.querySelector('#chat-panel');
  const log=document.querySelector('#chat-log');
  const form=document.querySelector('#chat-form');
  const input=document.querySelector('#chat-message');
  const ai=document.querySelector('#chat-ai');
  const send=document.querySelector('#chat-send');
  const status=document.querySelector('#chat-status');
  function message(role,text){
    const article=document.createElement('article');
    article.className='chat-message '+role;
    const title=document.createElement('strong');
    title.textContent=role==='user'?'You':'Trader assistant';
    const body=document.createElement('p');
    body.textContent=text;
    article.append(title,body);log.append(article);
    log.scrollTop=log.scrollHeight;
    return article;
  }
  function close(){panel.hidden=true;toggle.setAttribute('aria-expanded','false');toggle.focus()}
  toggle.onclick=async()=>{
    panel.hidden=!panel.hidden;toggle.setAttribute('aria-expanded',String(!panel.hidden));
    if(panel.hidden)return;
    input.focus();
    try{
      const result=await api('chat/status');aiAvailable=result.ai_available;
      ai.disabled=!aiAvailable;
      if(!aiAvailable)ai.checked=false;
      document.querySelector('#chat-ai-note').textContent=aiAvailable?
        'AI sends your question, recent chat and retrieved excerpts to OpenAI. Workspace access is required.':
        'Local mode · AI summaries are not configured.';
    }catch(error){status.textContent=error.message}
  };
  document.querySelector('#chat-close').onclick=close;
  panel.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();close()}});
  document.querySelector('#chat-clear').onclick=()=>{
    if(pending)pending.abort();pending=null;history=[];log.replaceChildren();status.textContent='';
    message('assistant','Ask about stored events, asset evidence, investigations or paper decisions. Choose a scope to narrow your search.');input.focus();
  };
  for(const chip of panel.querySelectorAll('[data-chat-prompt]')){
    chip.onclick=()=>{document.querySelector('#chat-scope').value=chip.dataset.chatScope;
      input.value=chip.dataset.chatPrompt;input.focus()};
  }
  form.onsubmit=async e=>{
    e.preventDefault();const question=input.value.trim();if(!question||pending)return;
    const controller=new AbortController();pending=controller;
    message('user',question);input.value='';send.disabled=true;status.textContent='Checking stored information…';
    log.setAttribute('aria-busy','true');
    try{
      const response=await fetch('/api/chat',{method:'POST',signal:controller.signal,
        headers:{'Content-Type':'application/json',...(token?{'Authorization':'Bearer '+token}:{})},
        body:JSON.stringify({message:question,scope:document.querySelector('#chat-scope').value,
          history:history.slice(-8),use_ai:aiAvailable&&ai.checked})});
      const result=await response.json();
      if(!response.ok)throw Error(typeof result.detail==='string'?result.detail:'Unable to answer. Check the question and workspace access.');
      if(pending!==controller)return;
      const article=message('assistant',result.answer);
      if(result.sources.length){
        const details=document.createElement('details');details.className='chat-sources';
        const summary=document.createElement('summary');summary.textContent='Inspect '+result.sources.length+' stored sources';
        details.append(summary);
        for(const source of result.sources){
          const item=document.createElement('div');item.className='chat-source';
          const link=document.createElement('a');
          // Destinations are server-created workspace anchors, never model URLs.
          link.href=source.href;link.textContent='['+source.citation+'] '+source.title;
          link.onclick=close;
          const meta=document.createElement('small');
          meta.textContent=source.classification+(source.as_of?' · '+source.as_of:'')+' · '+source.record_id;
          const excerpt=document.createElement('p');excerpt.textContent=source.excerpt;
          item.append(link,meta,excerpt);
          if(source.document_id){
            const button=document.createElement('button');button.className='btn';button.type='button';
            button.textContent='Open evidence document';button.dataset.action='document';button.dataset.id=source.document_id;
            button.onclick=close;item.append(button);
          }
          const actions={asset:['Open asset','facility'],investigation:['Open investigation','case-open']};
          if(actions[source.kind]){
            const button=document.createElement('button');button.className='btn';button.type='button';
            button.textContent=actions[source.kind][0];button.dataset.action=actions[source.kind][1];
            button.dataset.id=source.record_id;button.onclick=close;item.append(button);
          }
          details.append(item);
        }
        article.append(details);
      }
      history.push({role:'user',content:question},{role:'assistant',content:result.answer.slice(0,1500)});
      history=history.slice(-8);
      status.textContent=(result.mode==='ai'?'AI summary':'Local records')+' · '+result.retrieved_at+
        (result.warning?' · '+result.warning:'');
      log.scrollTop=log.scrollHeight;
    }catch(error){
      if(error.name!=='AbortError'&&pending===controller){
        status.textContent=error.message;input.value=question;
      }
    }finally{
      if(pending===controller){pending=null;send.disabled=false;log.setAttribute('aria-busy','false')}
      if(!pending){send.disabled=false;log.setAttribute('aria-busy','false')}
    }
  };
  message('assistant','Ask about stored events, asset evidence, investigations or paper decisions. Answers link to your workspace sources.');
})();
