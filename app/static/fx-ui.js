/* Interaction layer: spring physics, card tilt and spotlight, cursor aura, kinetic typography,
   scroll-scrubbed text, count-up numbers, a gliding nav indicator, click ripples, a command
   palette and a live UTC clock. Honors the motion toggle in motion.js and prefers-reduced-motion. */
(()=>{
  'use strict';
  const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)'), finePointer=matchMedia('(pointer: fine)');
  const motionOn=()=>document.body.dataset.motion!=='off'&&!reducedMotion.matches;
  const SPRING_STIFFNESS=170, SPRING_DAMPING=19, SPRING_REST=.002, MAX_TILT_DEGREES=5;
  const WORD_STAGGER_MS=55, COUNT_UP_MS=1100, ROW_STAGGER_MS=22, MAX_STAGGERED_ROWS=30;
  const OVERSHOOT='cubic-bezier(.34,1.56,.64,1)';
  const TILT_TARGETS='.workflow-card,.fx-tile,.stat';
  const GLOW_TARGETS='.card,.stat,.workflow-card,.fx-tile,.notice,.export-panel';
  const KINETIC_TARGETS='.page-title h1,.section-intro h2,.platform-cinema h2,.fx-reel-head h2';
  const SCRUB_TARGETS='.section-intro h2,.fx-reel-head h2';

  // ---- Spring physics: one shared rAF loop drives every active spring. ----
  const springs=new Set();
  let springFrame=0, lastTick=0;
  function tick(now){
    const dt=Math.min(.032,(now-lastTick)/1000||.016);lastTick=now;
    springs.forEach(spring=>{
      const acceleration=-SPRING_STIFFNESS*(spring.value-spring.target)-SPRING_DAMPING*spring.velocity;
      spring.velocity+=acceleration*dt;spring.value+=spring.velocity*dt;
      spring.apply(spring.value);
      if(Math.abs(spring.velocity)<SPRING_REST&&Math.abs(spring.value-spring.target)<SPRING_REST){
        spring.value=spring.target;spring.apply(spring.value);springs.delete(spring);
      }
    });
    springFrame=springs.size?requestAnimationFrame(tick):0;
  }
  function createSpring(apply,initial=0){
    const spring={value:initial,velocity:0,target:initial,apply};
    spring.to=target=>{
      spring.target=target;springs.add(spring);
      if(!springFrame){lastTick=performance.now();springFrame=requestAnimationFrame(tick)}
    };
    return spring;
  }

  // ---- Card spotlight + tilt, driven by the pointer position over each card. ----
  const tilts=new WeakMap();
  function tiltFor(card){
    const existing=tilts.get(card);if(existing)return existing;
    const pose={x:0,y:0};
    const paint=()=>{card.style.transform=`perspective(900px) rotateX(${pose.x}deg) rotateY(${pose.y}deg)`};
    const tilt={x:createSpring(value=>{pose.x=value;paint()}),y:createSpring(value=>{pose.y=value;paint()})};
    tilts.set(card,tilt);return tilt;
  }
  function releaseTilt(card){
    const tilt=tilts.get(card);if(!tilt)return;
    tilt.x.to(0);tilt.y.to(0);
  }
  function onPointerMove(event){
    if(event.pointerType!=='mouse'||!motionOn())return;
    const card=event.target.closest?.(GLOW_TARGETS);
    if(!card)return;
    const bounds=card.getBoundingClientRect();
    card.style.setProperty('--mx',`${event.clientX-bounds.left}px`);
    card.style.setProperty('--my',`${event.clientY-bounds.top}px`);
    if(!card.matches(TILT_TARGETS))return;
    const tilt=tiltFor(card), relativeX=(event.clientX-bounds.left)/bounds.width-.5, relativeY=(event.clientY-bounds.top)/bounds.height-.5;
    tilt.x.to(-relativeY*MAX_TILT_DEGREES*2);tilt.y.to(relativeX*MAX_TILT_DEGREES*2);
  }
  function onPointerOut(event){
    const card=event.target.closest?.(TILT_TARGETS);
    if(card&&!card.contains(event.relatedTarget))releaseTilt(card);
  }

  // ---- Cursor aura: a ring that trails the pointer and grows over controls. ----
  function setupCursor(){
    if(!finePointer.matches)return;
    const ring=document.createElement('div');
    ring.className='fx-cursor';ring.setAttribute('aria-hidden','true');document.body.append(ring);
    const pose={x:-100,y:-100,scale:1};
    const paint=()=>{ring.style.transform=`translate(${pose.x}px,${pose.y}px) translate(-50%,-50%) scale(${pose.scale})`};
    const follow={x:createSpring(value=>{pose.x=value;paint()},-100),y:createSpring(value=>{pose.y=value;paint()},-100),
      scale:createSpring(value=>{pose.scale=value;paint()},1)};
    document.addEventListener('pointermove',event=>{
      if(event.pointerType!=='mouse')return;
      ring.classList.toggle('visible',motionOn());
      follow.x.to(event.clientX);follow.y.to(event.clientY);
      follow.scale.to(event.target.closest?.('a,button,.btn,input,select,summary,[role="button"]')?1.9:1);
    },{passive:true});
    document.addEventListener('pointerleave',()=>ring.classList.remove('visible'));
    document.addEventListener('pointerdown',()=>follow.scale.to(.7));
    document.addEventListener('pointerup',()=>follow.scale.to(1));
  }

  // ---- Click ripple on buttons. ----
  function onPointerDown(event){
    const button=event.target.closest?.('.btn');
    if(!button||!motionOn()||!button.animate)return;
    const bounds=button.getBoundingClientRect(), size=Math.max(bounds.width,bounds.height)*2.2;
    const ripple=document.createElement('span');
    ripple.className='fx-ripple';ripple.setAttribute('aria-hidden','true');
    Object.assign(ripple.style,{width:`${size}px`,height:`${size}px`,left:`${event.clientX-bounds.left-size/2}px`,top:`${event.clientY-bounds.top-size/2}px`});
    button.append(ripple);
    ripple.animate([{transform:'scale(0)',opacity:.45},{transform:'scale(1)',opacity:0}],{duration:650,easing:'ease-out'}).finished.then(()=>ripple.remove(),()=>ripple.remove());
  }

  // ---- Kinetic typography: split headings into words that spring up in sequence. ----
  function splitWords(heading){
    if(heading.dataset.fxSplit)return [];
    heading.dataset.fxSplit='1';
    heading.setAttribute('aria-label',heading.textContent.replace(/\s+/g,' ').trim());
    const words=[];
    const walker=document.createTreeWalker(heading,NodeFilter.SHOW_TEXT);
    const textNodes=[];
    while(walker.nextNode())textNodes.push(walker.currentNode);
    textNodes.forEach(node=>{
      const fragment=document.createDocumentFragment();
      node.textContent.split(/(\s+)/).forEach(part=>{
        if(!part)return;
        if(/^\s+$/.test(part)){fragment.append(' ');return}
        const mask=document.createElement('span'), inner=document.createElement('span');
        mask.className='fx-word';mask.setAttribute('aria-hidden','true');
        inner.className='fx-word-in';inner.textContent=part;mask.append(inner);fragment.append(mask);words.push(inner);
      });
      node.replaceWith(fragment);
    });
    return words;
  }
  function revealHeadings(main){
    main.querySelectorAll(KINETIC_TARGETS).forEach(heading=>{
      const words=splitWords(heading);
      if(!motionOn())return;
      words.forEach((word,index)=>word.animate(
        [{transform:'translateY(115%) rotate(6deg)',opacity:0},{transform:'translateY(0) rotate(0)',opacity:1}],
        {duration:900,delay:120+index*WORD_STAGGER_MS,easing:OVERSHOOT,fill:'backwards'}));
    });
  }

  // ---- Scroll-scrubbed text: words light up as the heading crosses the viewport. ----
  let scrubFrame=0;
  function scrub(){
    scrubFrame=0;
    document.querySelectorAll(SCRUB_TARGETS).forEach(heading=>{
      const words=heading.querySelectorAll('.fx-word');if(!words.length)return;
      if(!motionOn()){words.forEach(word=>word.style.removeProperty('opacity'));return}
      const top=heading.getBoundingClientRect().top;
      const progress=Math.min(1,Math.max(0,(innerHeight*.9-top)/(innerHeight*.45)));
      words.forEach((word,index)=>word.style.setProperty('opacity',String(.22+.78*Math.min(1,Math.max(0,progress*words.length-index)))));
    });
  }
  const queueScrub=()=>{if(!scrubFrame)scrubFrame=requestAnimationFrame(scrub)};

  // ---- Marquee skews with scroll velocity. ----
  const skew={previous:scrollY,spring:null};
  function setupVelocitySkew(){
    skew.spring=createSpring(value=>{
      document.querySelectorAll('.industry-marquee>div').forEach(track=>track.style.setProperty('--fx-skew',`${value}deg`));
    });
    window.addEventListener('scroll',()=>{
      if(!motionOn())return;
      const velocity=scrollY-skew.previous;skew.previous=scrollY;
      skew.spring.value=Math.max(-8,Math.min(8,velocity*.35));skew.spring.to(0);
    },{passive:true});
  }

  // ---- Count-up numbers: preserves zero padding such as "07". ----
  function countUp(main){
    if(!motionOn())return;
    main.querySelectorAll('.stat strong').forEach(element=>{
      const text=element.textContent.trim();
      if(!/^\d{1,6}$/.test(text)||element.dataset.fxCounted)return;
      element.dataset.fxCounted='1';
      const final=Number(text), width=text.length, start=performance.now();
      const step=now=>{
        const progress=Math.min(1,(now-start)/COUNT_UP_MS), eased=1-Math.pow(1-progress,4);
        element.textContent=String(Math.round(final*eased)).padStart(width,'0');
        if(progress<1)requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    });
  }

  // ---- Table rows cascade in once per navigation. ----
  function cascadeRows(main){
    if(!motionOn())return;
    main.querySelectorAll('tbody').forEach(body=>{
      [...body.rows].slice(0,MAX_STAGGERED_ROWS).forEach((row,index)=>row.animate(
        [{opacity:0,transform:'translateX(-14px)'},{opacity:1,transform:'translateX(0)'}],
        {duration:520,delay:index*ROW_STAGGER_MS,easing:'cubic-bezier(.16,1,.3,1)',fill:'backwards'}));
    });
  }

  // ---- Gliding nav indicator (shared-layout transition between tabs). ----
  function setupNavPill(){
    const nav=document.querySelector('.sidebar nav');if(!nav)return;
    const pill=document.createElement('span');
    pill.className='fx-nav-pill';pill.setAttribute('aria-hidden','true');nav.prepend(pill);
    const place=()=>{
      const active=nav.querySelector('a.active');
      if(!active){pill.classList.remove('ready');return}
      pill.style.height=`${active.offsetHeight}px`;
      pill.style.transform=`translateY(${active.offsetTop}px)`;
      pill.classList.add('ready');
    };
    new MutationObserver(place).observe(nav,{attributes:true,attributeFilter:['class'],subtree:true});
    window.addEventListener('resize',place);place();
  }

  // ---- Command palette (Ctrl/Cmd+K): jump to a tab or run a workspace action. ----
  function paletteActions(){
    const pages=[...document.querySelectorAll('.sidebar nav a[data-page]')].map(link=>({
      label:link.querySelector('span')?.textContent.trim()||link.dataset.page,hint:'Go to tab',run:()=>{location.hash=link.getAttribute('href')}}));
    const click=selector=>()=>document.querySelector(selector)?.click();
    return [...pages,
      {label:'Switch color theme',hint:'Alt+T',run:click('#theme-toggle')},
      {label:'Pause or play animation',hint:'Motion',run:click('.motion-toggle')},
      {label:'Watch the platform film',hint:'Video',run:click('.film-launch')},
      {label:'Open trader assistant',hint:'Chat',run:click('#chat-toggle')},
      {label:'Scroll to top',hint:'Page',run:()=>window.scrollTo({top:0,behavior:motionOn()?'smooth':'auto'})}];
  }
  function setupPalette(){
    const dialog=document.createElement('dialog');
    dialog.className='fx-palette';dialog.setAttribute('aria-label','Command palette');
    const input=document.createElement('input');
    Object.assign(input,{type:'text',placeholder:'Jump to a tab or run an action…',autocomplete:'off',spellcheck:false});
    input.setAttribute('role','combobox');input.setAttribute('aria-expanded','true');input.setAttribute('aria-controls','fx-palette-list');
    const list=document.createElement('ul');list.id='fx-palette-list';list.setAttribute('role','listbox');
    dialog.append(input,list);document.body.append(dialog);
    let items=[], selected=0;
    function render(){
      const query=input.value.trim().toLowerCase();
      items=paletteActions().filter(item=>item.label.toLowerCase().includes(query));
      selected=Math.min(selected,Math.max(0,items.length-1));
      list.replaceChildren(...items.map((item,index)=>{
        const row=document.createElement('li');
        row.setAttribute('role','option');row.setAttribute('aria-selected',String(index===selected));
        const label=document.createElement('span'), hint=document.createElement('kbd');
        label.textContent=item.label;hint.textContent=item.hint;row.append(label,hint);
        row.addEventListener('click',()=>choose(index));return row;
      }));
      if(!items.length){const empty=document.createElement('li');empty.className='empty';empty.textContent='No matching command';list.append(empty)}
    }
    function choose(index){const item=items[index];dialog.close();item?.run()}
    input.addEventListener('input',()=>{selected=0;render()});
    input.addEventListener('keydown',event=>{
      if(event.key==='ArrowDown'||event.key==='ArrowUp'){
        event.preventDefault();selected=(selected+(event.key==='ArrowDown'?1:-1)+items.length)%Math.max(1,items.length);render();
      }else if(event.key==='Enter'){event.preventDefault();choose(selected)}
    });
    dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close()});
    const open=()=>{input.value='';selected=0;render();if(!dialog.open)dialog.showModal();input.focus()};
    document.addEventListener('keydown',event=>{
      const typing=/^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName)||event.target.isContentEditable;
      if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='k'){event.preventDefault();open()}
      else if(event.key==='/'&&!typing&&!event.metaKey&&!event.ctrlKey){event.preventDefault();open()}
    });
    document.addEventListener('click',event=>{if(event.target.closest('.fx-palette-launch'))open()});
  }

  // ---- Header extras: palette launcher, live UTC clock; footer: scroll-progress ring. ----
  function setupChrome(){
    const right=document.querySelector('.header-right');
    if(right){
      const launch=document.createElement('button');
      launch.type='button';launch.className='btn fx-palette-launch';launch.setAttribute('aria-keyshortcuts','Control+K Meta+K');
      launch.textContent='Search · Ctrl K';right.prepend(launch);
      const clock=document.createElement('time');clock.className='fx-clock';clock.setAttribute('aria-hidden','true');right.prepend(clock);
      const paint=()=>{clock.textContent=`${new Date().toISOString().slice(11,19)} UTC`};
      paint();setInterval(()=>{if(!document.hidden)paint()},1000);
    }
    const top=document.createElement('button');
    top.type='button';top.className='fx-top';top.setAttribute('aria-label','Scroll to top');top.textContent='↑';
    top.addEventListener('click',()=>window.scrollTo({top:0,behavior:motionOn()?'smooth':'auto'}));
    document.body.append(top);
    window.addEventListener('scroll',()=>top.classList.toggle('visible',scrollY>500),{passive:true});
  }

  // ---- Re-run page enhancements after each render; animate only on navigation. ----
  let lastRoute=null;
  function enhance(main){
    const navigated=(location.hash||'#overview')!==lastRoute;
    lastRoute=location.hash||'#overview';
    main.querySelectorAll('.card-head .btn,.export-panel .btn,.actions .btn').forEach(button=>button.classList.add('magnetic'));
    if(navigated){revealHeadings(main);cascadeRows(main);countUp(main)}
    else main.querySelectorAll(KINETIC_TARGETS).forEach(splitWords);
    queueScrub();
  }
  function boot(){
    const main=document.getElementById('content');if(!main)return;
    document.addEventListener('pointermove',onPointerMove,{passive:true});
    document.addEventListener('pointerout',onPointerOut);
    document.addEventListener('pointerdown',onPointerDown);
    window.addEventListener('scroll',queueScrub,{passive:true});
    setupCursor();setupVelocitySkew();setupNavPill();setupPalette();setupChrome();
    let pending=0;
    new MutationObserver(()=>{
      if(pending)return;
      pending=requestAnimationFrame(()=>{pending=0;enhance(main)});
    }).observe(main,{childList:true});
    if(main.querySelector('.page-title,.workspace-hero'))enhance(main);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
