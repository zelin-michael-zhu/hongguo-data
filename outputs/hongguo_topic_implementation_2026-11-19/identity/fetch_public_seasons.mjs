// Read public title and album metadata with the distributed openhongguo@0.4.0 client.
// Run: node fetch_public_seasons.mjs /absolute/path/to/openhongguo/index.js
import { readFile, writeFile, rename } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, join } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
const directory = dirname(fileURLToPath(import.meta.url));
const cachePath = join(directory, 'public_season_metadata.json');
const { createClient, memoryProfileStore, nodeTransport } = await import(process.argv[2] ? pathToFileURL(process.argv[2]).href : 'openhongguo');
const pairs = JSON.parse(await readFile(join(directory, 'independent_candidate_selection.json'), 'utf8'));
const ids = [...new Set(pairs.flatMap(pair => [pair.pre, pair.post]))];
let result;
try { result = JSON.parse(await readFile(cachePath, 'utf8')); }
catch(error) { if (error.code !== 'ENOENT') throw error; result={package:'openhongguo@0.4.0', started_at:new Date().toISOString(), details:{}, albums:{}, requests:[], failures:[]}; }
async function persist() { await writeFile(cachePath+'.partial', JSON.stringify(result,null,2)); await rename(cachePath+'.partial',cachePath); }
const transport = nodeTransport({timeoutMs:9000});
let previous=0, stop=false;
const client = await createClient({profile:memoryProfileStore(),retryAttempts:1,deviceResets:0, transport:async request=>{
 if(stop)throw Error('A previous request hit an access or rate limit.');
 await delay(Math.max(0,1250-(Date.now()-previous)));previous=Date.now();
 const url=new URL(request.url); const record={time:new Date().toISOString(),url:url.origin+url.pathname}; result.requests.push(record);
 try {const response=await transport(request);record.status=response.status;if([401,403,429].includes(response.status))stop=true;return response;}
 catch(err){record.error=err.name;throw err;}
}});
const uncollected=ids.filter(id=>!result.details[id]);
for(let i=0;i<uncollected.length&&!stop;i+=8){
 const batch=uncollected.slice(i,i+8);
 try{const returned=await client.getSeriesBatch(batch);const time=new Date().toISOString(); for(const d of returned){const s=d.series;if(!batch.includes(s.id))continue;result.details[s.id]={time,id:s.id,title:s.title,description:s.description,episode_count:s.episode_count,content_type:s.content_type,is_multi_season:s.is_multi_season??null,season_index:s.season_index??null,related_album_id:s.related_album_id??null,related_novel_book_id:s.related_novel_book_id??null,season_row:(s.rows??[]).filter(r=>r.kind===0).map(r=>r.text),source_page:'https://hongguoduanju.com/detail?series_id='+s.id};}for(const id of batch.filter(id=>!result.details[id]))result.failures.push({stage:'detail_omitted',id,time});}
 catch(error){result.failures.push({stage:'detail_error',ids:batch,time:new Date().toISOString(),error_name:error.name,code:error.code??null});if(!Object.keys(result.details).length||stop)stop=true;}
 await persist(); console.log('detail',Object.keys(result.details).length,'/',ids.length);
}
// Only fetch an album when both seasons independently returned the same album ID.
const albums=[...new Set(pairs.map(p=>{const l=result.details[p.pre]?.related_album_id;return l&&l===result.details[p.post]?.related_album_id?l:null;}).filter(Boolean))];
for (const id of albums.filter(id=>!result.albums[id])){if(stop)break;
 try{const a=await client.getAlbum(id);result.albums[id]={time:new Date().toISOString(),requested_id:id,returned_id:a.id??null,title:a.title??null,seasons:(a.seasons??[]).map(s=>({id:s.series_id,index:s.index??null,title:s.title??null}))};}
 catch(error){result.failures.push({stage:'album_error',id,time:new Date().toISOString(),error_name:error.name,code:error.code??null});}
 await persist();}
result.ended_at=new Date().toISOString();result.planned_title_count=ids.length;result.planned_album_count=albums.length;await persist();console.log('done',Object.keys(result.details).length,Object.keys(result.albums).length,'errors',result.failures.length);process.exit(0);
