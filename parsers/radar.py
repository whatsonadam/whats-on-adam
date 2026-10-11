"""radar.squat.net public API (JSON), city = Amsterdam. Bar/food/office-hours-only listings are skipped."""
import datetime, re
SKIP={'bar/cafe','food','advice/help/office hours','work space/diy','book shop/info shop/library','meeting','(free) shop/market'}
CAT=[('party','club'),('music/concert','music'),('film','film'),('discussion/presentation','talk'),('course/workshop','workshop'),('exhibition','exhibition'),('theater','theatre'),('action/protest/camp','protest'),("children's activity",'kids')]
FIX={'Astaro Theatro Sint':'Astaro Theatro','AstaroTheatro Sint':'Astaro Theatro','Boedapest Pesthuislaan By the Buddha statue':'Boedapest (Pesthuislaan)','Budapest Pesthuislaan':'Boedapest (Pesthuislaan)','De Hoek Joan':'De Hoek','De Nieuwe Anita Frederik':'De Nieuwe Anita','De Verdieping (bij Kaboem) Anna':'De Verdieping (Kaboem)','Dokhuis Galerie Plantage':'Dokhuis Galerie','Dokhuis Plantage':'Dokhuis Galerie','Filmhuis Cavia Van':'Filmhuis Cavia','Het Groene Veld / ADM Noord':'ADM Noord/Het Groene Veld','Huis de Pinto St.':'Huis de Pinto','Mime Fabriek Burgemeester de':'Mime Fabriek','Molli Chaoot Van':'Molli Chaoot','Nassaukerk De':'Nassaukerk','NieuwLand Pieter':'NieuwLand','Amsterdam':'Amsterdam (various)','FC':'FC Kraak',"Joe's":"Joe's Garage",'Villa':'Villa Kamal','Huis':'Huis Vrederiks','Café':'Café Gilde'}
def venue(t):
    s=re.split(r'\s+Amsterdam\b',t)[0].strip()
    s2=re.sub(r'\s+(?:Eerste |Tweede |Derde )?[^\s\d]+\s\d[\w\-/]*$','',s).strip()
    v=s2 or s or 'Amsterdam'
    return FIX.get(v,v)
def parse_api(results, today):
    out=[]; end=today+datetime.timedelta(days=120)
    for v in results.values():
        cats=[c['name'] for c in v.get('category',[])]
        if cats and set(cats)<=SKIP: continue
        cat=next((m for c,m in CAT if c in cats),'other')
        ven=venue(v['offline'][0]['title']) if v.get('offline') else 'Amsterdam (various)'
        addr=None
        if v.get('offline'):
            s0=re.split(r'\s+Amsterdam\b',v['offline'][0]['title'])[0].strip()
            m=re.search(r'((?:Eerste |Tweede |Derde )?[^\s\d]+\s\d[\w\-/]*)$',s0)
            if m: addr=m.group(1)
        for dt in v.get('date_time',[]):
            s=dt.get('time_start') or ''; e=dt.get('time_end') or ''
            if len(s)<16: continue
            d=datetime.date.fromisoformat(s[:10])
            if d<today or d>end: continue
            ev={'t':v['title'],'d':d.isoformat(),'v':ven,'s':'radar','u':v['url'],'c':cat}
            if addr: ev['addr']=addr
            if s[11:16]!='00:00': ev['h']=s[11:16]
            if e and e[11:16]!=s[11:16]: ev['eh']=e[11:16]
            if e and e[:10]!=s[:10]:
                ed=datetime.date.fromisoformat(e[:10])
                if (ed-d).days>=2: ev['ed']=ed.isoformat()
            out.append(ev)
    return out
