/* Apply the preference before styles load to avoid a theme flash. */
(()=>{
  const key='muniquant-theme',system=window.matchMedia('(prefers-color-scheme: dark)');
  let preference=null;
  try{preference=localStorage.getItem(key)}catch{/* Preferences remain usable when storage is unavailable. */}
  const valid=value=>value==='light'||value==='dark';
  function apply(theme){
    document.documentElement.dataset.theme=theme;
    const button=document.getElementById('theme-toggle');
    if(button){button.textContent=theme==='dark'?'☀ Light mode':'☾ Dark mode';button.setAttribute('aria-label',`Switch to ${theme==='dark'?'light':'dark'} mode`);button.setAttribute('aria-pressed',String(theme==='dark'));}
    const frame=document.getElementById('tradingview-chart');
    if(frame){const url=new URL(frame.src,location.origin);url.searchParams.set('theme',theme);frame.src=url.href;}
    document.querySelectorAll('iframe.map-frame').forEach(frame=>{try{frame.contentWindow.postMessage({type:'muniquant-theme',theme},location.origin)}catch{}});
    window.dispatchEvent(new CustomEvent('muniquant-theme-change',{detail:{theme}}));
  }
  apply(valid(preference)?preference:(system.matches?'dark':'light'));
  system.addEventListener('change',()=>{if(!valid(preference))apply(system.matches?'dark':'light')});
  window.addEventListener('storage',event=>{if(event.key===key){preference=event.newValue;apply(valid(preference)?preference:(system.matches?'dark':'light'))}});
  window.addEventListener('message',event=>{if(event.origin===location.origin&&event.source===parent&&event.data?.type==='muniquant-theme'&&valid(event.data.theme))apply(event.data.theme)});
  document.addEventListener('DOMContentLoaded',()=>{
    apply(document.documentElement.dataset.theme);
    const button=document.getElementById('theme-toggle');
    if(button){button.title='Switch appearance · Alt+T';button.setAttribute('aria-keyshortcuts','Alt+T')}
    document.addEventListener('keydown',event=>{if(event.altKey&&event.key.toLowerCase()==='t'&&!event.ctrlKey&&!event.metaKey&&button){event.preventDefault();button.click()}});
    button?.addEventListener('click',()=>{preference=document.documentElement.dataset.theme==='dark'?'light':'dark';try{localStorage.setItem(key,preference)}catch{}apply(preference)});
    const content=document.getElementById('content');
    if(content)new MutationObserver(()=>{content.classList.remove('page-arriving');requestAnimationFrame(()=>content.classList.add('page-arriving'))}).observe(content,{childList:true});
  });
})();
