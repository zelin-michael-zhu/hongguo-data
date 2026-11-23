"""Compare the available first-episode and whole-series public previews."""
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parent
SRC = OUT.parents[1] / "hongguo_expansion_2026-11-21"
SEED = "20261121-C-1"
SCOPES = ["first_episode_comment", "series_review"]
PATTERNS = {
    "前后落差": r"高开低走|虎头蛇尾|开头.{0,10}(?:不错|还行|挺好|很好|好看|有意思|可以).{0,25}(?:后面|后边|后来|结局|烂尾)|(?:前面|前半段|前期).{0,8}(?:不错|还行|好看|挺好|很好|有意思).{0,25}(?:后面|后边|后期|后半|结局|烂尾)",
    "续季比较或疲劳": r"(?:不如|比不上|没有).{0,5}(?:前几季|第一季|上一季|前两季).{0,6}(?:好看|精彩|好)?|(?:一季不如一季|越拍越差|越拍越烂|越拍越水|一季比一季差)|还是(?:上一季|第一季|前几季).{0,5}(?:好看|精彩)",
    "前季依赖或导航": r"(?:没看|没追|没刷|没补).{0,4}(?:前几季|上一季|前面几季|第一季)|(?:前几季|第一季|上一季|前两季).{0,8}(?:在哪|哪里看|哪儿看|找不到|搜不到|怎么看)|(?:从哪一季|从第几季|要从第一季|得从第一季)|(?:没看懂|看不懂).{0,10}(?:前几季|上一季|第一季)|(?:前几季|上一季|第一季).{0,12}(?:看不懂|看不明白|接不上|衔接不上)",
    "首集前瞻": r"期待后续|期待后面|期待后边|想看后续|好奇后面|想知道后面|开头.{0,7}(?:吸引|有意思|不错|挺好看|好看)",
}
AUDIT = {
    "完成或结尾表达": r"看完(?:了)?(?:来|回来)?回评|看到结尾|看完(?:了)?来评论",
    "未看完表达": r"还没(?:有)?看完|还没(?:有)?追完|还没(?:有)?刷完",
    "从首季追看号召": r"(?:谁|有谁|有没有人|有多少人|多少人).{0,7}从第[一1]季.{0,7}(?:看到|追到)",
    "版本导航搜索": r"(?:[前上][一几两]?[季部]|第[一二三四五1-5][季部]).{0,7}(?:在哪[里儿]?看|哪里[看找]|哪[儿里]能看|叫什么名字|叫啥名|搜不到|找不到)|(?:搜不到|找不到|在哪里看|在哪看).{0,5}(?:[前上][一几两]?[季部]|第[一二三四五1-5][季部])",
    "跨季衔接疑问": r"(?:[前上][一几两]?[季部]|第[一二三四五1-5][季部]).{0,15}(?:接不上|衔接不上|连不上|看不懂|没看懂|对不上)|(?:没看懂|看不懂|接不上|对不上|衔接不上).{0,12}(?:[前上][一几两]?[季部]|第[一二三四五1-5][季部])",
}
def read(name):
    with (SRC/name).open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))
def write(name, rows):
    with (OUT/name).open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)
def order(*parts):
    return hashlib.sha256("|".join([SEED,*parts]).encode()).hexdigest()
def run():
    reviews = read("reviews_preview.csv")
    series = {x["series_id"]:x for x in read("series_coverage.csv")}
    numbered = {x["series_id"]:int(x["title_season_number"]) for x in read("identity/explicit_seasons.csv")}
    pairs = read("identity/explicit_adjacent_seasons.csv")
    eligible = {i for i,s in series.items() if s["detail_status"]==s["first_page_status"]=="ok"}
    by = defaultdict(lambda:defaultdict(list))
    for r in reviews:
        by[r["series_id"]][r["scope"]].append(r)
    def stratum(i):
        if i not in numbered: return "无核实的标题季号"
        return "明示第1至2季" if numbered[i]<=2 else "明示第3季及以上"
    thresholds=[]
    for a,b in [(1,1),(5,5),(10,8),(15,9)]:
        ids={i for i in eligible if len(by[i][SCOPES[0]])>=a and len(by[i][SCOPES[1]])>=b}
        thresholds.append(dict(min_first=a,min_series=b,titles=len(ids),explicit_number=len(ids & set(numbered)),
            season_3_plus=sum(numbered.get(i,0)>=3 for i in ids),adjacent_pairs_both_meet=sum(p["old_id"] in ids and p["new_id"] in ids for p in pairs)))
    write("coverage_thresholds.csv",thresholds)
    sample=[]; sample_frames=[]
    for grp in ["无核实的标题季号","明示第1至2季","明示第3季及以上"]:
        pool=[i for i in eligible if stratum(i)==grp]
        sample_frames.append((grp,len(pool)))
        for i in sorted(pool,key=lambda i:order("title",i))[:4]:
            for tag in SCOPES:
                rows=sorted(by[i][tag],key=lambda r:order("row",i,tag,r["display_position"]))
                for r in rows[:3]:
                    sample.append(dict(case=len(sample)//6+1,series_id=i,title=series[i]["catalog_title"],stratum=grp,
                                       season=numbered.get(i,""),scope=tag,position=r["display_position"],text=r["text"]))
    write("random_reading.csv",sample)
    candidates=[]; counts=[]; matched=defaultdict(set)
    for label,pattern in PATTERNS.items():
        hits=[]
        for r in reviews:
            m=re.search(pattern,r["text"],flags=re.DOTALL)
            if not m: continue
            i,tag,pos=r["series_id"],r["scope"],r["display_position"]
            matched[(label,tag)].add(i)
            hits.append(dict(mechanism=label,series_id=i,title=series[i]["catalog_title"],explicit_season=numbered.get(i,""),
                     scope=tag,position=pos,match=m.group(),context=r["text"][max(0,m.start()-100):m.end()+120],text=r["text"]))
        for scope in SCOPES:
            frame=[h for h in hits if h["scope"]==scope]
            counts.append(dict(label=label,scope=scope,rows=len(frame),titles=len({r["series_id"] for r in frame})))
            ranked=sorted(frame,key=lambda r:order("target",label,scope,r["series_id"],r["position"]))
            selected = set()
            for h in ranked:
                if h["series_id"] in selected:continue
                candidates.append(h)
                selected.add(h["series_id"])
                if len(selected)==4:break
    write("target_reading.csv",candidates); write("keyword_screen_counts.csv",counts)
    overlap=matched[("首集前瞻",SCOPES[0])] & matched[("前后落差",SCOPES[1])]
    overlap_rows=[dict(series_id=i,title=series[i]["catalog_title"],scope=tag,position=r['display_position'],text=r['text'])
       for i in sorted(overlap) for tag,label in [(SCOPES[0],"首集前瞻"),(SCOPES[1],"前后落差")] for r in by[i][tag] if re.search(PATTERNS[label],r['text'],re.S)]
    if overlap_rows:write("cross_scope_keyword_candidates.csv",overlap_rows)
    audit_counts=[];extra_reads=[]
    for label,pattern in AUDIT.items():
        for tag in SCOPES:
            hits=[r for r in reviews if r['scope']==tag and re.search(pattern,r['text'])]
            audit_counts.append(dict(label=label,scope=tag,rows=len(hits),titles=len({r['series_id'] for r in hits})))
            if label in ('版本导航搜索','跨季衔接疑问'):
                for r in hits:
                    extra_reads.append(dict(label=label,series_id=r['series_id'],title=series[r['series_id']]['catalog_title'],
                                   scope=tag,position=r['display_position'],text=r['text']))
    write('scope_and_continuity_audit.csv',audit_counts)
    write('continuity_candidates.csv',extra_reads)
    stats=dict(seed=SEED,sample_frames=dict(sample_frames),titles_both=len(eligible),sample_titles=len({r['series_id'] for r in sample}),sample_rows=len(sample),
               targeted_rows=len(candidates),scope_pattern_overlap_titles=len(overlap),thresholds=thresholds,keyword_counts=counts)
    (OUT/"summary.json").write_text(json.dumps(stats,ensure_ascii=False,indent=2))
    print(json.dumps(stats,ensure_ascii=False))
if __name__=="__main__":
    run()
