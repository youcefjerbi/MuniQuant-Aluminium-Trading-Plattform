/* Progressive enhancement: content is visible and usable without animation or JS. */
(()=>{
  'use strict';
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  const storageKey='muniquant-motion';
  let paused=false, route=null, observer=null;
  const running=new Set();
  try{paused=localStorage.getItem(storageKey)==='off'}catch{}
  const enabled=()=>!paused&&!reduced.matches;
  function sync(){
    document.body.dataset.motion=enabled()?'on':'off';
    document.querySelectorAll('.motion-toggle').forEach(button=>{
      button.textContent=reduced.matches?'Reduced motion enabled':paused?'Play animation':'Pause animation';
      button.setAttribute('aria-pressed',String(!enabled()));
      button.disabled=reduced.matches;
    });
    if(!enabled()){
      observer?.disconnect();
      running.forEach(animation=>animation.cancel());running.clear();
    }
  }
  function animate(element,frames,delay=0,duration=550){
    if(!enabled()||!element?.animate)return;
    const animation=element.animate(frames,{duration,delay,easing:'cubic-bezier(.2,.7,.2,1)',fill:'backwards'});
    running.add(animation);
    animation.finished.then(()=>running.delete(animation),()=>running.delete(animation));
  }
  function enhance(){
    const main=document.getElementById('content');
    if(!main)return;
    sync();
    // Data refreshes and filtering should not repeatedly move the interface.
    const next=location.hash||'#overview';
    if(next===route)return;
    route=next;
    observer?.disconnect();
    running.forEach(animation=>animation.cancel());running.clear();
    if(!enabled())return;
    main.querySelectorAll('.hero-copy .eyebrow,.hero-copy h1>span,.hero-copy p,.hero-copy .actions,.hero-caption').forEach((el,i)=>{
      animate(el,[{opacity:0,transform:'translateY(14px)'},{opacity:1,transform:'translateY(0)'}],i*65,650);
    });
    animate(main.querySelector('.evidence-scene')||main.querySelector('.page-title'),[{opacity:0,transform:'translateY(12px)'},{opacity:1,transform:'translateY(0)'}],120,700);
    const sections=main.querySelectorAll('.stat,.card,.notice,.export-panel');
    if(!('IntersectionObserver' in window))return;
    let stagger=0;
    observer=new IntersectionObserver(entries=>{
      entries.forEach(entry=>{
        if(!entry.isIntersecting)return;
        animate(entry.target,[{opacity:0,transform:'translateY(16px)'},{opacity:1,transform:'translateY(0)'}],(stagger++%4)*55);
        observer.unobserve(entry.target);
      });
      stagger=0;
    },{threshold:.08});
    sections.forEach(element=>observer.observe(element));
  }
  function boot(){
    const main=document.getElementById('content');
    if(!main)return;
    document.addEventListener('click',event=>{
      if(!event.target.closest('.motion-toggle'))return;
      paused=!paused;
      try{localStorage.setItem(storageKey,paused?'off':'on')}catch{}
      sync();
    });
    reduced.addEventListener('change',sync);
    document.addEventListener('visibilitychange',()=>{
      document.body.classList.toggle('motion-background',document.hidden);
    });
    new MutationObserver(enhance).observe(main,{childList:true});
    // Wait for the initial API render before assigning its route.
    if(main.querySelector('.page-title,.workspace-hero'))enhance();
    else sync();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
