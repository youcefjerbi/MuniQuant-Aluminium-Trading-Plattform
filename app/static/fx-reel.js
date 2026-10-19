/* Video reel for the overview (bento grid with custom controls) and an ambient film banner under
   every other tab title. All films are original, silent, locally served loops. */
(()=>{
  'use strict';
  const MEDIA='/static/media/';
  const FILMS=[
    {id:'aluminium-motion',title:'Aluminium sculpture',note:'Machined fins in slow rotation',span:'wide'},
    {id:'signal-contours',title:'Signal contours',note:'Interference of source signals',span:'tall'},
    {id:'market-terrain',title:'Market terrain',note:'A wave surface in perspective',span:'tile'},
  ];
  const BANNER_FILMS={facilities:'aluminium-motion',evidence:'signal-contours',review:'market-terrain',leads:'signal-contours',
    research:'market-terrain',investigations:'aluminium-motion',map:'market-terrain',quality:'signal-contours'};
  const POSTERS={'aluminium-motion':'aluminium-poster.jpg','signal-contours':'signal-contours-poster.jpg','market-terrain':'market-terrain-poster.jpg'};
  const SPEEDS=[.5,1,1.5,2];
  const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)');
  const motionOn=()=>document.body.dataset.motion!=='off'&&!reducedMotion.matches;
  const visible=new Set();
  let observer=null;

  function element(tag,className,text){
    const node=document.createElement(tag);
    if(className)node.className=className;
    if(text!==undefined)node.textContent=text;
    return node;
  }
  function film(id,loopClass){
    const video=element('video',loopClass);
    Object.assign(video,{muted:true,loop:true,playsInline:true,preload:'metadata',poster:MEDIA+POSTERS[id]});
    video.setAttribute('aria-hidden','true');
    video.tabIndex=-1;
    const source=element('source');source.src=`${MEDIA}${id}.mp4`;source.type='video/mp4';
    video.append(source);return video;
  }
  function shouldPlay(video){
    if(video.dataset.userPaused==='1')return false;
    return motionOn()&&!document.hidden&&visible.has(video)&&!document.getElementById('film-dialog')?.open;
  }
  function syncPlayback(){
    document.querySelectorAll('.fx-film').forEach(video=>{
      if(shouldPlay(video))video.play().catch(()=>{/* Poster stays visible when autoplay is blocked. */});
      else video.pause();
    });
  }
  function formatTime(seconds){
    const whole=Math.floor(seconds||0);
    return `${Math.floor(whole/60)}:${String(whole%60).padStart(2,'0')}`;
  }

  function controls(video,label){
    const bar=element('div','fx-controls');bar.setAttribute('role','group');bar.setAttribute('aria-label',`${label} controls`);
    const play=element('button','fx-control','Pause');play.type='button';
    const scrub=element('input','fx-scrub');
    Object.assign(scrub,{type:'range',min:'0',max:'1000',value:'0',step:'1'});scrub.setAttribute('aria-label',`${label} position`);
    const time=element('span','fx-time','0:00');
    const speed=element('button','fx-control','1×');speed.type='button';speed.setAttribute('aria-label',`${label} playback speed`);
    const full=element('button','fx-control','Full');full.type='button';full.setAttribute('aria-label',`${label} fullscreen`);
    bar.append(play,scrub,time,speed,full);

    const paintState=()=>{play.textContent=video.paused?'Play':'Pause';play.setAttribute('aria-pressed',String(video.paused))};
    play.addEventListener('click',()=>{
      if(video.paused){video.dataset.userPaused='0';video.play().catch(()=>{})}
      else{video.dataset.userPaused='1';video.pause()}
    });
    video.addEventListener('play',paintState);video.addEventListener('pause',paintState);
    video.addEventListener('timeupdate',()=>{
      if(!video.duration)return;
      scrub.value=String(Math.round(video.currentTime/video.duration*1000));time.textContent=formatTime(video.currentTime);
    });
    scrub.addEventListener('input',()=>{if(video.duration)video.currentTime=Number(scrub.value)/1000*video.duration});
    speed.addEventListener('click',()=>{
      const next=SPEEDS[(SPEEDS.indexOf(video.playbackRate)+1)%SPEEDS.length]??1;
      video.playbackRate=next;speed.textContent=`${next}×`;
    });
    full.addEventListener('click',()=>{video.parentElement.requestFullscreen?.().catch(()=>{})});
    paintState();return bar;
  }

  function tile(spec){
    const figure=element('figure',`fx-tile fx-${spec.span}`);
    const video=film(spec.id,'fx-film');
    const caption=element('figcaption','fx-caption');
    caption.append(element('strong',null,spec.title),element('span',null,spec.note));
    figure.append(video,caption,controls(video,spec.title));
    figure.addEventListener('pointerenter',()=>{if(video.dataset.userPaused!=='1'&&motionOn())video.play().catch(()=>{})});
    return figure;
  }
  function reel(){
    const section=element('section','fx-reel');section.setAttribute('aria-labelledby','fx-reel-title');
    const head=element('div','fx-reel-head');
    const eyebrow=element('div','eyebrow','MOTION REEL');
    const title=element('h2',null,'Original films, rendered locally');title.id='fx-reel-title';
    head.append(eyebrow,title,element('p',null,'Decorative artwork generated for this workspace. It is not footage of a facility and not a live data feed.'));
    const grid=element('div','fx-bento');grid.append(...FILMS.map(tile));
    section.append(head,grid);return section;
  }
  function banner(id){
    const strip=element('div','fx-banner');strip.setAttribute('role','presentation');
    const video=film(id,'fx-film');strip.append(video,element('span','fx-banner-label','ORIGINAL ARTWORK · SILENT LOOP'));
    return strip;
  }

  function mount(main){
    main.querySelectorAll('.fx-film').forEach(video=>observer?.unobserve(video));
    visible.clear();
    const page=(location.hash||'#overview').slice(1);
    if(page==='overview'&&!main.querySelector('.fx-reel')){
      const anchor=main.querySelector('.platform-cinema')||main.querySelector('.data-intro');
      if(anchor)anchor.before(reel());else main.append(reel());
    }else if(page!=='overview'&&BANNER_FILMS[page]&&!main.querySelector('.fx-banner')){
      const title=main.querySelector('.page-title');
      if(title)title.after(banner(BANNER_FILMS[page]));
    }
    main.querySelectorAll('.fx-film').forEach(video=>observer?.observe(video));
    if(!observer)main.querySelectorAll('.fx-film').forEach(video=>visible.add(video));
    syncPlayback();
  }
  function boot(){
    const main=document.getElementById('content');if(!main)return;
    if('IntersectionObserver' in window){
      observer=new IntersectionObserver(entries=>{
        entries.forEach(entry=>{if(entry.isIntersecting)visible.add(entry.target);else visible.delete(entry.target)});
        syncPlayback();
      },{threshold:.25});
    }
    document.addEventListener('visibilitychange',syncPlayback);
    reducedMotion.addEventListener('change',syncPlayback);
    new MutationObserver(syncPlayback).observe(document.body,{attributes:true,attributeFilter:['data-motion']});
    document.getElementById('film-dialog')?.addEventListener('close',syncPlayback);
    let pending=0;
    new MutationObserver(()=>{
      if(pending)return;
      pending=requestAnimationFrame(()=>{pending=0;mount(main)});
    }).observe(main,{childList:true});
    if(main.querySelector('.page-title,.workspace-hero'))mount(main);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
