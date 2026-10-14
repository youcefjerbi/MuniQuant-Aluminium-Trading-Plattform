/* Cinematic motion is optional; all content and navigation work without it. */
(()=>{
  'use strict';
  const reduced=matchMedia('(prefers-reduced-motion: reduce)'), key='muniquant-motion';
  let paused=false, route=null, revealObserver=null, mediaObserver=null, scrollFrame=0;
  const running=new Set(), visibleMedia=new Set();
  try{paused=localStorage.getItem(key)==='off'}catch{}
  const enabled=()=>!paused&&!reduced.matches;
  function syncMedia(){
    document.querySelectorAll('.hero-film').forEach(video=>{
      if(enabled()&&!document.hidden&&!document.getElementById('film-dialog')?.open&&visibleMedia.has(video)){
        video.play().catch(()=>{/* The poster remains visible if autoplay is blocked. */});
      }else video.pause();
    });
  }
  function sync(){
    document.body.dataset.motion=enabled()?'on':'off';
    document.querySelectorAll('.motion-toggle').forEach(button=>{
      button.textContent=reduced.matches?'Reduced motion enabled':paused?'Play animation':'Pause animation';
      button.setAttribute('aria-pressed',String(!enabled()));button.disabled=reduced.matches;
    });
    if(!enabled()){
      revealObserver?.disconnect();
      running.forEach(animation=>animation.cancel());running.clear();
      document.querySelectorAll('.magnetic').forEach(el=>el.style.removeProperty('transform'));
      document.documentElement.style.setProperty('--hero-drift','0px');
    }
    syncMedia();
  }
  function animate(element,frames,delay=0,duration=700){
    if(!enabled()||!element?.animate)return;
    const animation=element.animate(frames,{duration,delay,easing:'cubic-bezier(.16,1,.3,1)',fill:'backwards'});
    running.add(animation);
    animation.finished.then(()=>running.delete(animation),()=>running.delete(animation));
  }
  function enhance(){
    const main=document.getElementById('content');if(!main)return;
    // Each render replaces the hero video. Retire observers for detached elements.
    mediaObserver?.disconnect();visibleMedia.clear();
    if('IntersectionObserver' in window){
      mediaObserver=new IntersectionObserver(entries=>{
        entries.forEach(entry=>{if(entry.isIntersecting)visibleMedia.add(entry.target);else visibleMedia.delete(entry.target)});
        syncMedia();
      },{threshold:.05});
      main.querySelectorAll('.hero-film').forEach(video=>mediaObserver.observe(video));
    }else main.querySelectorAll('.hero-film').forEach(video=>visibleMedia.add(video));
    sync();
    // Refreshing data must not replay entrance animations or shift controls.
    const next=location.hash||'#overview';if(next===route)return;
    if(route!==null){window.scrollTo({top:0,behavior:'instant'});main.focus({preventScroll:true})}
    route=next;revealObserver?.disconnect();
    running.forEach(animation=>animation.cancel());running.clear();
    if(!enabled())return;
    main.querySelectorAll('.hero-topline,.hero-copy .eyebrow,.hero-copy h1>span,.hero-copy p,.hero-copy .actions,.hero-bottomline').forEach((el,i)=>{
      animate(el,[{opacity:0,transform:'translateY(30px)',filter:'blur(5px)'},{opacity:1,transform:'translateY(0)',filter:'blur(0)'}],90+i*100,1000);
    });
    animate(main.querySelector('.page-title'),[{opacity:0,transform:'translateY(15px)'},{opacity:1,transform:'translateY(0)'}]);
    if(!('IntersectionObserver' in window))return;
    revealObserver=new IntersectionObserver(entries=>{
      let stagger=0;
      entries.forEach(entry=>{
        if(!entry.isIntersecting)return;
        animate(entry.target,[{opacity:0,transform:'translateY(35px)'},{opacity:1,transform:'translateY(0)'}],stagger++*75,850);
        revealObserver.unobserve(entry.target);
      });
    },{threshold:.12});
    main.querySelectorAll('.stat,.card,.notice,.section-intro,.workflow-card,.platform-cinema,.export-panel').forEach(el=>revealObserver.observe(el));
  }
  function updateScroll(){
    scrollFrame=0;
    const root=document.documentElement, extent=root.scrollHeight-innerHeight;
    root.style.setProperty('--scroll-progress',`${extent>0?Math.min(100,scrollY/extent*100):0}%`);
    const hero=document.querySelector('.cinema-hero');
    root.style.setProperty('--hero-drift',enabled()&&hero?`${Math.max(-32,Math.min(32,-hero.getBoundingClientRect().top*.07))}px`:'0px');
  }
  function boot(){
    const main=document.getElementById('content');if(!main)return;
    const dialog=document.getElementById('film-dialog'), film=document.getElementById('platform-film');
    let filmTrigger=null;
    document.addEventListener('click',event=>{
      if(event.target.closest('.motion-toggle')){
        paused=!paused;try{localStorage.setItem(key,paused?'off':'on')}catch{}sync();
      }
      if(event.target.closest('.film-launch')&&dialog){
        filmTrigger=event.target.closest('.film-launch');dialog.showModal();
        document.querySelectorAll('.hero-film').forEach(video=>video.pause());
        film.play().catch(()=>{/* Native playback controls remain available. */});
      }
      if(event.target.closest('#film-close'))dialog.close();
      if(event.target.closest('.hero-scroll'))document.getElementById('overview-data')?.scrollIntoView({behavior:enabled()?'smooth':'auto',block:'start'});
    });
    dialog?.addEventListener('close',()=>{film.pause();if(filmTrigger?.isConnected)filmTrigger.focus();syncMedia()});
    document.addEventListener('pointermove',event=>{
      if(!enabled()||event.pointerType!=='mouse')return;
      const button=event.target.closest('.magnetic');
      if(button){const bounds=button.getBoundingClientRect();button.style.transform=`translate(${(event.clientX-bounds.left-bounds.width/2)*.07}px,${(event.clientY-bounds.top-bounds.height/2)*.12}px)`;}
    });
    document.addEventListener('pointerout',event=>{const button=event.target.closest('.magnetic');if(button&&!button.contains(event.relatedTarget))button.style.removeProperty('transform')});
    reduced.addEventListener('change',sync);
    document.addEventListener('visibilitychange',()=>{
      document.body.classList.toggle('motion-background',document.hidden);
      if(document.hidden)film?.pause();syncMedia();
    });
    window.addEventListener('scroll',()=>{if(!scrollFrame)scrollFrame=requestAnimationFrame(updateScroll)},{passive:true});
    window.addEventListener('resize',updateScroll);
    new MutationObserver(()=>{enhance();updateScroll()}).observe(main,{childList:true});
    if(main.querySelector('.page-title,.workspace-hero'))enhance();else sync();
    updateScroll();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
