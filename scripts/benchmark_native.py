"""Reproducible developer benchmark; timing is evidence, not a CI threshold."""
import json,random,time,platform
import muniquant_core

def python_distance(a,b):
    row=list(range(len(b)+1))
    for i,left in enumerate(a,1):
        nxt=[i]
        for j,right in enumerate(b,1): nxt.append(min(nxt[-1]+1,row[j]+1,row[j-1]+(left!=right)))
        row=nxt
    return row[-1]

random.seed(42)
pairs=[(''.join(random.choices('aluminium café smelter refinery',k=64)),''.join(random.choices('aluminium café smelter refinery',k=64))) for _ in range(1000)]
results={}
outputs=[]
for name,fn in [('python',python_distance),('cpp',muniquant_core.name_distance)]:
    start=time.perf_counter();values=[fn(a,b) for a,b in pairs];results[name]=time.perf_counter()-start;outputs.append(values)
assert outputs[0]==outputs[1]
print(json.dumps({'python_version':platform.python_version(),'platform':platform.platform(),'pairs':len(pairs),'characters_per_name':64,'equivalent':True,'seconds':results,'speedup':results['python']/results['cpp']},indent=2))
