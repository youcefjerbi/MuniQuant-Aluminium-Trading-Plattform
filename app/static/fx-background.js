/* Living WebGL background: a domain-warped noise field that follows the cursor, drifts with scroll
   and eases its palette between workspace tabs. Decorative only; the page works without it. */
(()=>{
  'use strict';
  const MAX_PIXEL_RATIO=1.5, RENDER_SCALE=.5, COLOR_EASE=.045, POINTER_EASE=.07, PULSE_DECAY=.94;
  // [accent A, accent B, dark base, light base] per tab, 0-1 RGB. Brand stays green / black / red.
  const PALETTES={
    overview:[[.18,.78,.38],[.05,.38,.24],[.02,.045,.03],[.93,.96,.93]],
    facilities:[[.16,.74,.52],[.04,.30,.30],[.02,.05,.045],[.92,.96,.95]],
    evidence:[[.34,.82,.30],[.10,.42,.16],[.025,.05,.025],[.94,.96,.92]],
    review:[[.80,.62,.22],[.38,.26,.07],[.05,.04,.02],[.97,.95,.90]],
    leads:[[.86,.30,.38],[.36,.08,.14],[.055,.025,.03],[.97,.92,.93]],
    research:[[.20,.70,.64],[.06,.26,.36],[.02,.045,.055],[.92,.96,.97]],
    investigations:[[.62,.80,.26],[.22,.38,.08],[.035,.05,.02],[.95,.97,.91]],
    map:[[.12,.72,.46],[.03,.28,.22],[.015,.045,.035],[.91,.96,.94]],
    quality:[[.88,.34,.30],[.30,.14,.08],[.05,.035,.03],[.97,.93,.92]],
  };
  const VERTEX='attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}';
  const FRAGMENT=`precision mediump float;
uniform vec2 uRes,uMouse;uniform float uTime,uScroll,uPulse,uLight;uniform vec3 uA,uB,uBase;
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
  return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x),f.y);}
float fbm(vec2 p){float v=0.,a=.5;for(int i=0;i<4;i++){v+=a*noise(p);p=p*2.03+vec2(1.7,9.2);a*=.5;}return v;}
void main(){
  float aspect=uRes.x/uRes.y;
  vec2 uv=gl_FragCoord.xy/uRes;
  vec2 p=(uv-.5)*vec2(aspect,1.);
  vec2 m=(uMouse-.5)*vec2(aspect,1.);
  float d=length(p-m);
  float t=uTime*.05;
  vec2 q=p*1.7+vec2(0.,uScroll*.35);
  vec2 warp=vec2(fbm(q+t),fbm(q+vec2(5.2,1.3)-t));
  warp+=(p-m)*exp(-d*3.5)*(.22+uPulse*.9);
  float n=fbm(q+2.2*warp+t*.5);
  float ridge=1.-abs(n*2.-1.);
  float body=smoothstep(.38,.92,n);
  float filament=pow(ridge,6.);
  float aura=exp(-d*d*7.);
  vec3 tint=mix(uB,uA,body);
  vec3 glow=tint*(body*.55+filament*.6)+uA*aura*(.22+uPulse*.5);
  glow+=glow*glow*.9;
  float vignette=smoothstep(1.25,.25,length(p*vec2(.8,1.)));
  vec3 dark=uBase+glow*vignette*.8;
  vec3 light=mix(uBase,mix(uBase,tint,.5),body*.32+filament*.18+aura*.2);
  vec3 col=mix(dark,light,uLight);
  col+=(hash(gl_FragCoord.xy+uTime)-.5)*.012;
  gl_FragColor=vec4(col,1.);
}`;
  const canvas=document.createElement('canvas');
  canvas.className='fx-background';canvas.setAttribute('aria-hidden','true');
  const gl=canvas.getContext('webgl',{alpha:false,antialias:false,powerPreference:'low-power'});
  if(!gl){document.documentElement.classList.add('fx-no-webgl');return}
  function compile(type,source){
    const shader=gl.createShader(type);gl.shaderSource(shader,source);gl.compileShader(shader);
    return gl.getShaderParameter(shader,gl.COMPILE_STATUS)?shader:null;
  }
  const program=gl.createProgram(), vs=compile(gl.VERTEX_SHADER,VERTEX), fs=compile(gl.FRAGMENT_SHADER,FRAGMENT);
  if(!vs||!fs){document.documentElement.classList.add('fx-no-webgl');return}
  gl.attachShader(program,vs);gl.attachShader(program,fs);gl.linkProgram(program);
  if(!gl.getProgramParameter(program,gl.LINK_STATUS)){document.documentElement.classList.add('fx-no-webgl');return}
  gl.useProgram(program);
  gl.bindBuffer(gl.ARRAY_BUFFER,gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,3,-1,-1,3]),gl.STATIC_DRAW);
  const position=gl.getAttribLocation(program,'p');
  gl.enableVertexAttribArray(position);gl.vertexAttribPointer(position,2,gl.FLOAT,false,0,0);
  const uniform=name=>gl.getUniformLocation(program,name);
  const loc={res:uniform('uRes'),mouse:uniform('uMouse'),time:uniform('uTime'),scroll:uniform('uScroll'),pulse:uniform('uPulse'),
    light:uniform('uLight'),a:uniform('uA'),b:uniform('uB'),base:uniform('uBase')};

  const state={mouse:[.62,.42],target:[.62,.42],pulse:0,light:0,colors:null,goal:null,frame:0,start:performance.now(),frozen:0};
  const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)');
  const motionOn=()=>document.body?.dataset.motion!=='off'&&!reducedMotion.matches;
  const route=()=>(location.hash||'#overview').slice(1);
  const paletteFor=theme=>{
    const [a,b,dark,light]=PALETTES[route()]||PALETTES.overview;
    return [...a,...b,...(theme==='light'?light:dark)];
  };
  const theme=()=>document.documentElement.dataset.theme==='light'?'light':'dark';
  function retarget(){
    state.goal=paletteFor(theme());
    if(!state.colors)state.colors=state.goal.slice();
  }
  function resize(){
    const ratio=Math.min(devicePixelRatio||1,MAX_PIXEL_RATIO)*RENDER_SCALE;
    const width=Math.max(2,Math.round(innerWidth*ratio)), height=Math.max(2,Math.round(innerHeight*ratio));
    if(canvas.width!==width||canvas.height!==height){canvas.width=width;canvas.height=height;gl.viewport(0,0,width,height)}
  }
  function draw(now){
    state.frame=0;
    const live=motionOn();
    const elapsed=live?(now-state.start)/1000:state.frozen;
    if(live)state.frozen=elapsed;
    state.mouse=state.mouse.map((value,index)=>value+(state.target[index]-value)*POINTER_EASE);
    state.colors=state.colors.map((value,index)=>value+(state.goal[index]-value)*COLOR_EASE);
    state.pulse*=PULSE_DECAY;
    state.light+=((theme()==='light'?1:0)-state.light)*.12;
    const c=state.colors;
    gl.uniform2f(loc.res,canvas.width,canvas.height);
    gl.uniform2f(loc.mouse,state.mouse[0],state.mouse[1]);
    gl.uniform1f(loc.time,elapsed);
    gl.uniform1f(loc.scroll,scrollY/Math.max(1,innerHeight));
    gl.uniform1f(loc.pulse,state.pulse);
    gl.uniform1f(loc.light,state.light);
    gl.uniform3f(loc.a,c[0],c[1],c[2]);gl.uniform3f(loc.b,c[3],c[4],c[5]);gl.uniform3f(loc.base,c[6],c[7],c[8]);
    gl.drawArrays(gl.TRIANGLES,0,3);
    schedule(live||settling());
  }
  const settling=()=>state.colors.some((value,index)=>Math.abs(value-state.goal[index])>.002)||state.pulse>.01
    ||Math.abs(state.light-(theme()==='light'?1:0))>.01||state.mouse.some((value,index)=>Math.abs(value-state.target[index])>.001);
  function schedule(keepRunning=true){
    if(state.frame||document.hidden||!keepRunning)return;
    state.frame=requestAnimationFrame(draw);
  }
  function wake(){schedule(true)}

  document.addEventListener('pointermove',event=>{
    state.target=[event.clientX/innerWidth,1-event.clientY/innerHeight];wake();
  },{passive:true});
  document.addEventListener('pointerdown',()=>{state.pulse=1;wake()},{passive:true});
  window.addEventListener('scroll',wake,{passive:true});
  window.addEventListener('resize',()=>{resize();wake()});
  window.addEventListener('hashchange',()=>{retarget();state.pulse=1;wake()});
  window.addEventListener('muniquant-theme-change',()=>{retarget();wake()});
  document.addEventListener('visibilitychange',wake);
  reducedMotion.addEventListener('change',wake);
  canvas.addEventListener('webglcontextlost',event=>{event.preventDefault();document.documentElement.classList.add('fx-no-webgl')});

  function boot(){
    document.body.prepend(canvas);
    document.documentElement.classList.add('fx-webgl');
    new MutationObserver(wake).observe(document.body,{attributes:true,attributeFilter:['data-motion']});
    retarget();resize();wake();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
