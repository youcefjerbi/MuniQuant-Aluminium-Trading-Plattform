'use strict';
const map=L.map('geography',{worldCopyJump:true}).setView([23,10],2);
let countryLayer=null;
fetch('/static/vendor/world-countries.geojson').then(r=>r.json()).then(data=>{countryLayer=L.geoJSON(data,{style:{color:'#2b3a30',weight:1,fillColor:'#18231c',fillOpacity:1},onEachFeature:(f,l)=>l.bindTooltip(f.properties.NAME)}).addTo(map);countryLayer.bringToBack()}).catch(()=>document.querySelector('#map-health').textContent='Country boundaries could not load.');
map.attributionControl.addAttribution('Countries: <a href="https://www.naturalearthdata.com/" target="_blank" rel="noopener">Natural Earth</a>');
let overlays=L.layerGroup().addTo(map);
const escapeMap=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
window.addEventListener('message',event=>{if(event.origin!==location.origin||event.source!==parent||event.data?.type!=='asset-map-data')return;
 overlays.clearLayers();const graph=event.data.graph,nodes=new Map(graph.nodes.map(n=>[n.entity.id,n]));
 for(const n of graph.nodes){if(!n.location)continue;const p=n.location;
 L.circleMarker([p.latitude,p.longitude],{radius:8,color:p.synthetic?'#ff727b':'#4ade80',fillOpacity:0.8}).bindPopup(`<strong>${escapeMap(n.entity.name)}</strong><br>${escapeMap(n.entity.country)} · ${escapeMap(n.entity.facility_type||n.entity.kind)}<br>${escapeMap(p.precision)}${p.synthetic?' · FICTIONAL LOCATION':''}<br>Source document: ${escapeMap(p.document_id)}<br>Recorded: ${escapeMap(p.recorded_at)}`).addTo(overlays);}
 for(const d of graph.dependencies){const a=nodes.get(d.from_entity_id),b=nodes.get(d.to_entity_id);if(!a?.location||!b?.location)continue;
 const start=[a.location.latitude,a.location.longitude],end=[b.location.latitude,b.location.longitude];
 // Wrap across the shorter longitudinal span; this is schematic, not a shipping route.
 while(end[1]-start[1]>180)end[1]-=360;while(end[1]-start[1]<-180)end[1]+=360;
 const dy=end[0]-start[0],dx=end[1]-start[1],distance=Math.hypot(dx,dy);
 if(distance>0){const size=Math.min(2,distance*.15),tip=[start[0]+dy*.55,start[1]+dx*.55],back=[tip[0]-dy/distance*size,tip[1]-dx/distance*size];L.polyline([[back[0]+dx/distance*size*.5,back[1]-dy/distance*size*.5],tip,[back[0]-dx/distance*size*.5,back[1]+dy/distance*size*.5]],{color:d.synthetic?'#ff727b':'#4ade80',weight:3,interactive:false}).addTo(overlays)}
 L.polyline([start,end],{color:d.synthetic?'#ff727b':'#4ade80',weight:3,dashArray:d.status==='hypothesis'?'6 6':null}).bindPopup(`<strong>${escapeMap(a.entity.name)} → ${escapeMap(b.entity.name)}</strong><br>${escapeMap(d.product)} · ${escapeMap(d.kind)} · ${escapeMap(d.status)}${d.synthetic?' · FICTIONAL':''}<br>${escapeMap(d.note)}<br>Valid ${escapeMap(d.valid_from)}–${escapeMap(d.valid_to||'open')}<br>Source document: ${escapeMap(d.document_id)}`).addTo(overlays);}
 document.querySelector('#map-health').textContent=`${graph.nodes.filter(n=>n.location).length} located assets · ${graph.missing_locations} missing locations. Click assets or links for evidence.`;
});
parent.postMessage({type:'asset-map-ready'},location.origin);
