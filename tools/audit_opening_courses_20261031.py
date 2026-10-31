"""Read-only local opening audit: full bounded screen, then deeper suspicious decisions.

Original PGNs and account data are never modified. Engine evaluations cannot verify
source fidelity, publication rights, learning quality or FM readiness.
"""
from __future__ import annotations
import argparse,collections,concurrent.futures,csv,datetime,hashlib,io,json,os,threading,time
from pathlib import Path
import chess,chess.engine,chess.pgn

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'audit/2026-10-31-prepublication-openings'
ENGINE=ROOT/'resources/essentials-2026-10-18/stockfish19/stockfish/stockfish-windows-x86-64-universal.exe'
BASE=ROOT/'outputs/book-courses-2026-10-31-best-available'
SUP=ROOT/'outputs/lichess-supplements-2026-10-31'
SOURCES=[('OnlyMove White',BASE/'OnlyMove/White_London_Coherent.pgn',True),
 ('OnlyMove Black',BASE/'OnlyMove/Black_Caro_Coherent.pgn',False),
 ('Caro book',BASE/'Caro_Kann_Training_94.pgn',False),
 ('London book',BASE/'London_Practical_Recall_Exercises.pgn',True),
 ('London conversion',BASE/'London_Middlegame_and_Conversion_Recall.pgn',True),
 ('Caro supplements',SUP/'Caro_Lichess_Gap_Fillers.pgn',False),
 ('d4 supplements',SUP/'Black_C6_Non_E4_Supplement.pgn',False),
 ('London supplements',SUP/'London_Lichess_Planning_Recall.pgn',True)]
SETTINGS={'screen':{'multipv':3,'nodes':500000,'forced_nodes':500000,'threads':3,'hash_mb':256},
 'deep':{'multipv':3,'depth':24,'max_seconds_per_root':90,'threads':3,'hash_mb':512}}
LOCAL=threading.local();ENGINES=[];LOCK=threading.Lock()

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp')
 tmp.write_text(json.dumps(obj,indent=2),encoding='utf8')
 # Windows readers can briefly deny delete-sharing while polling progress.
 # Preserve the old valid JSON and retry replacement, never truncate it in place.
 for attempt in range(50):
  try:tmp.replace(path);break
  except PermissionError:
   if attempt==49:raise
   time.sleep(.1)
def load(path):return json.loads(path.read_text(encoding='utf8'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def identity(b,move):return hashlib.sha256((b.epd()+'|'+move.uci()).encode()).hexdigest()[:24]

def prepare():
 rows={};sources=[];conflicts=[]
 for label,path,side in SOURCES:
  own=collections.defaultdict(set);games=0;edges=0
  with path.open(encoding='utf-8-sig')as f:
   while(g:=chess.pgn.read_game(f))is not None:
    games+=1;assert not g.errors
    assert str(chess.pgn.read_game(io.StringIO(str(g))))==str(g)
    stack=[g]
    while stack:
     n=stack.pop();b=n.board();assert b.is_valid()
     for c in n.variations:
      assert c.move in b.legal_moves;edges+=1
      if b.turn==side:
       rid=identity(b,c.move)
       own[b.epd()].add(c.move.uci())
       row=rows.setdefault(rid,{'id':rid,'fen':b.fen(),'epd':b.epd(),'side':'white'if side else'black',
        'chosen_uci':c.move.uci(),'chosen_san':b.san(c.move),'references':[]})
       row['references'].append({'source':label,'file':str(path.relative_to(ROOT)),
        'lesson':g.headers.get('Event',''),'route':g.board().variation_san(b.move_stack),
        'start_fen':g.board().fen(),'ply':c.ply(),'leaf_decision':not c.variations})
     stack.extend(n.variations)
  for epd,moves in own.items():
   if len(moves)>1:conflicts.append({'source':label,'epd':epd,'moves':sorted(moves),'disposition':'report book alternatives; do not silently change'})
  sources.append({'source':label,'file':str(path.relative_to(ROOT)),'sha256':digest(path),'games':games,'legal_edges':edges,'unique_decisions':sum(map(len,own.values()))})
 inventory={'created_utc':now(),'decisions':len(rows),'positions':len({x['epd']for x in rows.values()}),'source_files':sources,
  'within_source_multiple_choices':conflicts,'settings':SETTINGS,'engine_sha256':digest(ENGINE),'scope':'All learner decisions in eight current opening training PGNs. Historical reading games, strategy and endings are outside this opening audit.'}
 if (OUT/'inventory.json').exists():assert load(OUT/'inventory.json')['source_files']==sources,'Inputs changed: use a new audit directory.'
 else:save(OUT/'inventory.json',inventory)
 save(OUT/'positions.json',list(rows.values()))
 print(json.dumps({k:inventory[k]for k in ['decisions','positions','within_source_multiple_choices']},indent=2),flush=True)

def init_engine(phase):
 e=chess.engine.SimpleEngine.popen_uci(str(ENGINE),timeout=180)
 assert e.id['name']=='Stockfish 19';s=SETTINGS[phase]
 e.configure({'Threads':s['threads'],'Hash':s['hash_mb']})
 LOCAL.engine=e
 with LOCK:ENGINES.append(e)

def packed(info,b):
 pv=info.get('pv',[]);test=b.copy()
 for move in pv:assert move in test.legal_moves;test.push(move)
 pov=info['score'].pov(b.turn)
 return {'move_uci':pv[0].uci(),'move_san':b.san(pv[0]),'cp_learner':pov.score(mate_score=100000),
  'mate_learner':pov.mate(),'depth':info.get('depth'),'seldepth':info.get('seldepth'),
  'nodes':info.get('nodes'),'seconds':info.get('time'),'pv_uci':[m.uci()for m in pv],
  'pv_san':b.variation_san(pv)}

def analyse(row,phase):
 file=OUT/phase/(row['id']+'.json');sig={'engine_sha256':load(OUT/'inventory.json')['engine_sha256'],'settings':SETTINGS[phase],'decision':row['id']}
 if file.exists():
  d=load(file);assert d['signature']==sig;return d
 b=chess.Board(row['fen']);e=LOCAL.engine;s=SETTINGS[phase];t=time.monotonic()
 e.configure({'Clear Hash':None})
 limit=chess.engine.Limit(nodes=s['nodes'])if phase=='screen'else chess.engine.Limit(depth=s['depth'],time=s['max_seconds_per_root'])
 infos=e.analyse(b,limit,multipv=3,game=object());pvs=[packed(i,b)for i in infos]
 selected=next((i for i in pvs if i['move_uci']==row['chosen_uci']),None)
 constrained=selected is None
 if constrained:
  e.configure({'Clear Hash':None})
  lim=chess.engine.Limit(nodes=s['forced_nodes'])if phase=='screen'else limit
  selected=packed(e.analyse(b,lim,root_moves=[chess.Move.from_uci(row['chosen_uci'])],game=object()),b)
 best=max(pvs,key=lambda x:x['cp_learner'])
 d={'created_utc':now(),'signature':sig,'phase':phase,'id':row['id'],'fen':row['fen'],
  'chosen_uci':row['chosen_uci'],'chosen_san':row['chosen_san'],'pvs':pvs,'selected':selected,'best':best,
  'loss_cp':max(0,best['cp_learner']-selected['cp_learner']),'selected_separate_root_search':constrained,
  'wall_seconds':round(time.monotonic()-t,3),
  'depth24_complete':phase=='deep'and min([i['depth']for i in pvs]+[selected['depth']])>=24}
 save(file,d);return d

def flagged(result):return result['loss_cp']>=50 or result['selected']['cp_learner']<=-100

def anchor_ids(rows):
 ids=set()
 for sans in ['d4 c6 c4','d4 c6 Bf4','d4 c6 Nf3','d4 c6 e3','d4 c6 e4','e4 c6 Nf3','e4 c6 d4']:
  b=chess.Board()
  for san in sans.split():b.push_san(san)
  ids.update(r['id']for r in rows if r['epd']==b.epd())
 return ids

def run(phase):
 rows=load(OUT/'positions.json');original_count=len(rows)
 if phase=='deep':
  assert all((OUT/'screen'/(r['id']+'.json')).exists()for r in rows),'Screen must finish before deeper selection'
  anchors=anchor_ids(rows)
  rows=[r for r in rows if flagged(load(OUT/'screen'/(r['id']+'.json')))or r['id']in anchors]
  save(OUT/'deep-targets.json',{'count':len(rows),'anchor_ids':sorted(anchors),'ids':[r['id']for r in rows],
   'selection':'screen loss >=0.50 pawn, or selected position <=-1.00 for learner (including already-unfavourable positions), plus seven requested Black branch anchors'})
  rows.sort(key=lambda r:load(OUT/'screen'/(r['id']+'.json'))['loss_cp'],reverse=True)
 pending=[r for r in rows if not(OUT/phase/(r['id']+'.json')).exists()]
 done=len(rows)-len(pending);started=time.monotonic()
 save(OUT/'RUN_STATE.json',{'status':'running_'+phase,'phase':phase,'completed':done,'total':len(rows),'all_opening_decisions':original_count,'started_utc':now(),'pid':os.getpid(),'originals_modified':False})
 print(f'{phase}: {done} cached, {len(pending)} pending; two engines, 3 threads each',flush=True)
 try:
  with concurrent.futures.ThreadPoolExecutor(max_workers=2,initializer=init_engine,initargs=(phase,))as pool:
   futs={pool.submit(analyse,r,phase):r for r in pending}
   for future in concurrent.futures.as_completed(futs):
    row=futs[future];d=future.result();done+=1
    state={'status':'running_'+phase,'phase':phase,'completed':done,'total':len(rows),'elapsed_seconds':round(time.monotonic()-started),'updated_utc':now(),'pid':os.getpid(),'last_id':row['id'],'originals_modified':False}
    save(OUT/'RUN_STATE.json',state)
    if done%25==0 or done==len(rows)or(phase=='deep'):
     print(f"{phase} {done}/{len(rows)} {row['side']} {row['chosen_san']}: loss {d['loss_cp']}cp, chosen {d['selected']['cp_learner']}cp, depth {d['selected']['depth']}",flush=True)
 finally:
  for e in ENGINES:
   try:e.quit()
   except Exception:pass
  ENGINES.clear()
 save(OUT/'RUN_STATE.json',{'status':phase+'_complete','completed':done,'total':len(rows),'updated_utc':now(),'originals_modified':False})

def report():
 rows=load(OUT/'positions.json');issues=[];data=[];screened=0;deepcount=0;depth24=0
 for row in rows:
  screen=OUT/'screen'/(row['id']+'.json');deep=OUT/'deep'/(row['id']+'.json')
  if not screen.exists():continue
  screened+=1;d=load(deep if deep.exists()else screen)
  if deep.exists():deepcount+=1;depth24+=d['depth24_complete']
  rating='review_required'if flagged(d)else'no_issue_at_audit_threshold'
  if deep.exists()and not d['depth24_complete']:rating='depth_limited_'+rating
  item={'id':row['id'],'side':row['side'],'chosen':row['chosen_san'],'chosen_uci':row['chosen_uci'],'best':d['best']['move_san'],
   'loss_cp':d['loss_cp'],'chosen_cp_learner':d['selected']['cp_learner'],'depth':d['selected']['depth'],'phase':d['phase'],'status':rating,
   'sources':sorted(set(x['source']for x in row['references'])),'references':row['references'],'fen':row['fen'],'best_pv':d['best']['pv_san'],
   'best_pv_uci':d['best']['pv_uci'],'depth24_complete':d['depth24_complete']}
  data.append(item)
  if 'review_required'in rating:issues.append(item)
 inv=load(OUT/'inventory.json')
 for s in inv['source_files']:assert digest(ROOT/s['file'])==s['sha256'],'Original PGN changed'
 for d in issues:
  if d['chosen_cp_learner']<=-100 and d['loss_cp']<50:d['assessment']='unfavourable_incoming_position_not_necessarily_a_move_error'
  elif d['chosen_cp_learner']<=-150:d['assessment']='soundness_concern_requires_line_context'
  elif d['chosen_cp_learner']>=200:d['assessment']='winning_position_precision'
  else:d['assessment']='playable_move_with_stronger_alternative'
 summary={'created_utc':now(),'screened':screened,'total':len(rows),'deeper_checked':deepcount,'depth24_completed':depth24,'review_required':len(issues),
  'phase_status':load(OUT/'RUN_STATE.json')['status'],'sources_unchanged':True,'engine':'Stockfish 19','multipv':3,
  'settings':SETTINGS,'scope':inv['scope'],'public_publication_performed':False,
  'publication_boundary':'Private book-derived PGNs and teaching material remain excluded from public packaging, even if engine soundness is confirmed.',
  'assessment_counts':dict(collections.Counter(d['assessment']for d in issues))}
 save(OUT/'SUMMARY.json',summary);save(OUT/'REVIEW_REQUIRED.json',sorted(issues,key=lambda x:x['loss_cp'],reverse=True));save(OUT/'RESULTS.json',data)
 with(OUT/'DECISIONS.csv').open('w',encoding='utf-8-sig',newline='')as f:
  w=csv.writer(f);w.writerow(['Side','Move','Best reported','Loss cp','Chosen cp for learner','Depth','Phase','Status','Sources','FEN'])
  for d in data:w.writerow([d['side'],d['chosen'],d['best'],d['loss_cp'],d['chosen_cp_learner'],d['depth'],d['phase'],d['status'],'; '.join(d['sources']),d['fen']])
 md=['# Opening course audit',json.dumps(summary,indent=2),'','## Decisions requiring review']
 for d in sorted(issues,key=lambda x:x['loss_cp'],reverse=True):
  refs='; '.join(x['source']+': '+x['lesson']for x in d['references'][:3])
  md.extend([f"- {d['id']}: {d['side']} {d['chosen']} versus {d['best']}; loss {d['loss_cp']/100:.2f}, selected {d['chosen_cp_learner']/100:+.2f} for learner; depth {d['depth']} ({d['phase']}). {refs}",f"  FEN: {d['fen']}",f"  Best PV: {d['best_pv']}"])
 (OUT/'REPORT.md').write_text('\n'.join(md)+'\n',encoding='utf8');print(json.dumps(summary,indent=2),flush=True)
 proposals=[]
 for d in sorted(issues,key=lambda x:x['loss_cp'],reverse=True):
  if not d['depth24_complete']or d['chosen_uci']==d['best_pv_uci'][0]:continue
  g=chess.pgn.Game();g.setup(chess.Board(d['fen']))
  g.headers.update({'Event':'PROPOSED ONLY - '+d['side']+' '+d['chosen']+' to '+d['best'],
   'Date':'2026.10.31','Result':'*','TrainingSide':d['side'],'AuditID':d['id'],
   'Annotator':'Independent local Stockfish 19 audit; not applied to a live course'})
  g.comment=f"Reviewable proposal, not applied. Current move {d['chosen']} screened at {d['loss_cp']/100:.2f} pawns below the best reported choice after the deeper search. Source groups: {', '.join(d['sources'])}. Consider practical plans and repertoire consistency before replacing a line. Depth 24 complete."
  n=g
  for uci in d['best_pv_uci'][:10]:n=n.add_variation(chess.Move.from_uci(uci))
  old=g.add_variation(chess.Move.from_uci(d['chosen_uci']))
  old.comment='Current training choice, retained here for comparison. This variation is not a mandatory exercise.'
  assert not chess.pgn.read_game(io.StringIO(str(g))).errors;proposals.append(g)
 (OUT/'CORRECTIONS_PROPOSED_NOT_APPLIED.pgn').write_text('\n\n'.join(str(g)for g in proposals)+'\n',encoding='utf8')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['prepare','screen','deep','report','all']);args=p.parse_args();OUT.mkdir(parents=True,exist_ok=True)
 if args.phase in ['prepare','all']:prepare()
 if args.phase in ['screen','all']:run('screen')
 if args.phase in ['deep','all']:run('deep')
 if args.phase in ['report','all']:report()
