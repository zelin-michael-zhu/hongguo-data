"""Compare review cards in public SSR HTML to the array in the same HTTP response.

Never persist HTML, review text, reviewer identifiers, image URLs, or user accounts.
"""
from pathlib import Path
import csv
from datetime import datetime
import json
import re
import time
from html import unescape
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
OUTPUT = HERE/"render_order_audit.csv"
SENSITIVE = re.compile(r'(?:1[3-9][0-9]{9}|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,})')

class Cards(HTMLParser):
    """Only collect text nodes and emoji alternatives within review body paragraphs."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ignore, self.in_para = 0, False
        self.cards, self.fragments = [], []
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style"): self.ignore += 1
        if self.ignore: return
        attrs = dict(attrs)
        if tag=="p" and "review-content-" in attrs.get("class",""):
            self.in_para=True
            self.cards.append([])
            self.fragments.append([])
        if self.in_para and tag=="img":
            self.cards[-1].append(attrs.get("alt") or "")
    def handle_endtag(self,tag):
        if tag in ("script","style"): self.ignore=max(self.ignore-1,0)
        if self.in_para and tag=="p": self.in_para=False
    def handle_data(self,data):
        if self.in_para and not self.ignore:
            self.fragments[-1].append(data)
            self.cards[-1].append(data)

def norm(s):
    return re.sub(r'[\s\x00]+', '', unescape(SENSITIVE.sub('[redacted]',s or "")))

def locate(card_text, parts, reference):
    text=norm("".join(card_text))
    exact=[i for i,x in enumerate(reference,1) if x==text and text]
    if len(exact)==1: return exact[0],"exact"
    # A single distinctive fragment of >=8 characters, or multiple such fragments in order.
    pieces=[piece for r in parts if len(piece:=norm(r))>=8]
    if not pieces:return None,"ambiguous_or_short"
    found=[]
    for i,source in enumerate(reference,1):
        offset=0
        for piece in pieces:
            where=source.find(piece,offset)
            if where<0:break
            offset=where+len(piece)
        else:found.append(i)
    return (found[0],"unique_fragment") if len(found)==1 else (None,"ambiguous_or_missing")

def positions(value):
    return ",".join("?" if k is None else str(k) for k in value)

def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as f:return list(csv.DictReader(f))

def save(rows):
    fields=["series_id","stratum","old_timestamp","read_timestamp","url","http_status","status","old_array_n","same_response_array_n",
            "html_cards_n","unique_exact_matches","unique_fragment_matches","html_to_same_array_positions","html_to_old_array_positions",
            "same_response_all_positions","html_matches_all_old_positions","old_same_array_full_text_same","old_to_current_positions","error_type"]
    temp=OUTPUT.with_suffix(".partial")
    with temp.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,restval="");w.writeheader();w.writerows(rows)
    temp.replace(OUTPUT)

def audit(frame):
    old=json.loads((HERE/"sanitized_captures"/(frame["series_id"]+".json")).read_text())
    oldtxt=[norm(r["text"]) for r in old["reviews"]]
    url=old["url"]
    row=dict(series_id=frame["series_id"],stratum=frame["stratum"],old_timestamp=old["sample_time"],old_array_n=len(oldtxt),
             read_timestamp=datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),url=url)
    try:
        req=Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; University research; public page sample)"})
        with urlopen(req,timeout=12) as r:
            row["http_status"]=r.status
            html=r.read().decode("utf-8")
        p=Cards();p.feed(html);p.close()
        router,_=json.JSONDecoder().raw_decode(html.split("_ROUTER_DATA = ",1)[1])
        page=router["loaderData"]["detail_page"]
        assert str(page["seriesDetail"]["series_id"])==frame["series_id"]
        current=[norm(x.get("content")) for x in page["seriesSocialInfo"]["reviews"]["reviews"]]
        now=[locate(t,f,current) for t,f in zip(p.cards,p.fragments)]
        oldloc=[locate(t,f,oldtxt)[0] for t,f in zip(p.cards,p.fragments)]
        ix=[k for k,_ in now]
        oldmap=[current.index(v)+1 if v and current.count(v)==1 else None for v in oldtxt]
        row.update(status="audited",same_response_array_n=len(current),html_cards_n=len(p.cards),
                   unique_exact_matches=sum(method=="exact" for _,method in now),
                   unique_fragment_matches=sum(method=="unique_fragment" for _,method in now),
                   html_to_same_array_positions=positions(ix),html_to_old_array_positions=positions(oldloc),
                   same_response_all_positions=int(bool(current) and ix==list(range(1,len(current)+1))),
                   html_matches_all_old_positions=int(bool(oldtxt) and oldloc==list(range(1,len(oldtxt)+1))),
                   old_same_array_full_text_same=int(oldtxt==current),
                   old_to_current_positions=positions(oldmap))
    except (ValueError,KeyError,IndexError,HTTPError,URLError,OSError,AssertionError) as err:
        row.update(status="failed",error_type=type(err).__name__)
        if isinstance(err,HTTPError):row["http_status"]=err.code
    return row

if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--retry-unmatched",action="store_true",help="Recheck only previously ambiguous pages after transparent markup normalization.")
    args=ap.parse_args()
    rows=read_rows(OUTPUT) if OUTPUT.exists() else []
    prior={r["series_id"]:r for r in rows}
    done={r["series_id"] for r in rows if not args.retry_unmatched or str(r["same_response_all_positions"])=="1"}
    for frame in read_rows(HERE/"frozen_30.csv"):
        if frame["series_id"] in done:continue
        row=audit(frame)
        if frame["series_id"] in prior:
            rows[rows.index(prior[frame["series_id"]])]=row
        else:
            rows.append(row)
        save(rows)
        if row.get("http_status") in (401,403,429):break
        time.sleep(1.5)
    print(f"{len(rows)} pages checked")
