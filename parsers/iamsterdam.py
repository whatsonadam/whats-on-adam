"""I amsterdam Uitagenda: server-rendered listing pages (?page=N), 16 cards each.
Keeps dated events inside Amsterdam; drops the wider metro area (tags 'ama*'), restaurants/shops,
and recurring non-exhibition items that only show an end date ('t/m')."""
import datetime, re
from bs4 import BeautifulSoup
MON={'jan':1,'feb':2,'mrt':3,'apr':4,'mei':5,'jun':6,'jul':7,'aug':8,'sep':9,'okt':10,'nov':11,'dec':12}
SKIPT={'restaurant','accommodation','hotels','shops','shopping'}
def cat(tags):
    T=set(tags)
    for keys,c in [({'clubbing','djs','dancemusic','housemusic','electro','techno'},'club'),({'comedy'},'comedy'),({'filmevent','film','cinema','filmfestival','documentaryfilm'},'film'),({'reading','debate'},'talk'),({'workshop'},'workshop'),({'exhibition','historicalexhibition','museum'},'exhibition'),({'theatreproduction','performingarts','dance','musical','opera'},'theatre'),({'music','livemusic','classicalmusic','poprock','musicevent','jazz'},'music'),({'kids'},'kids')]:
        if T&keys: return c
    return 'other'
def cards(html):
    s=BeautifulSoup(html,'html.parser'); out=[]
    for a in s.select('a > article'):
        for sv in a.select('svg'): sv.decompose()
        tags=a.select_one('[data-testid=card-tags]')
        out.append((a.parent.get('href'), list(a.stripped_strings), tags.get_text() if tags else ''))
    return out
def parse_pages(pages, today):
    seen=set(); out=[]; end=today+datetime.timedelta(days=120)
    for html in pages:
        for href,p,t in cards(html):
            if not href or href in seen: continue
            seen.add(href)
            tags=[x.strip() for x in t.split(',') if x.strip()]
            if any(x.startswith('ama') for x in tags): continue
            i=0; until=False
            if p and p[0]=='t/m': until=True; i=1
            if len(p)<i+3 or not re.fullmatch(r'\d{1,2}',p[i]): continue
            m=re.fullmatch(r"(\w+) '(\d\d)",p[i+1])
            if not m or m.group(1) not in MON: continue
            try: d=datetime.date(2000+int(m.group(2)),MON[m.group(1)],int(p[i]))
            except ValueError: continue
            c=cat(tags)
            if set(tags)&SKIPT and c=='other': continue
            e={'t':p[i+2],'v':p[p.index('Locatie')+1] if 'Locatie' in p else '','s':'iamsterdam','u':'https://www.iamsterdam.com'+href,'c':c}
            e['tags']=tags
            if 'dutchlanguage' in tags: e['nl']=1
            if 'Gratis toegang' in p: e['p']='Free'
            if 'Uitverkocht' in p: e['p']='Sold out'
            if until:
                if c!='exhibition' and 'festivals' not in tags: continue
                if d<today: continue
                e['d']=today.isoformat(); e['ed']=d.isoformat()
            else:
                if d<today or d>end: continue
                e['d']=d.isoformat()
                if 'Datum en/of tijd' in p:
                    mm=re.match(r'(\d\d:\d\d)\s*-\s*(\d\d:\d\d)',p[p.index('Datum en/of tijd')+1])
                    if mm and mm.groups()!=('00:00','23:59'):
                        e['h']=mm.group(1)
                        if mm.group(2)!=mm.group(1): e['eh']=mm.group(2)
            out.append(e)
    return out
