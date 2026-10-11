"""Verzetsmuseum /nl/agenda (rendered markdown). Each activity is one link block:
'[DD\\n\\nMAAND\\n\\nTitle\\n\\nDD maand YYYY\\n\\nHH:MM - HH:MM uur | Meerdere tijden\\n\\nLees meer](/nl/agenda/slug)'."""
import re, datetime
M={'januari':1,'februari':2,'maart':3,'april':4,'mei':5,'juni':6,'juli':7,'augustus':8,'september':9,'oktober':10,'november':11,'december':12}
BLOCK=re.compile(r'\[\d{1,2}\s*\n\s*[A-Z]+\s*\n(.*?)Lees meer\]\((/nl/agenda/[^)\s]+)\)', re.S)
def cat(t):
    t=t.lower()
    if 'film' in t: return 'film'
    if 'familie' in t or 'kinder' in t or 'koffer' in t: return 'kids'
    if 'dialoog' in t or 'lezing' in t or 'gesprek' in t: return 'talk'
    if 'herdenking' in t or 'sobibor' in t: return 'community'
    return 'other'
def parse(text, today):
    out=[]; end=today+datetime.timedelta(days=120)
    for m in BLOCK.finditer(text):
        lines=[l.strip() for l in m.group(1).split('\n') if l.strip()]
        di=next((i for i,l in enumerate(lines) if re.fullmatch(r'\d{1,2} [a-z]+ \d{4}', l)), None)
        if di is None or di==0: continue
        dd,mn,yy=lines[di].split()
        if mn not in M: continue
        try: d=datetime.date(int(yy),M[mn],int(dd))
        except ValueError: continue
        if d<today or d>end: continue
        title=' '.join(lines[:di])
        e={'t':title,'d':d.isoformat(),'v':'Verzetsmuseum Amsterdam','s':'verzetsmuseum','u':'https://www.verzetsmuseum.org'+m.group(2),'c':cat(title)}
        if di+1<len(lines):
            tm=re.match(r'(\d{1,2}):(\d\d)\s*-\s*(\d{1,2}):(\d\d)', lines[di+1])
            if tm:
                e['h']=f"{int(tm.group(1)):02d}:{tm.group(2)}"; e['eh']=f"{int(tm.group(3)):02d}:{tm.group(4)}"
            elif 'tijden' in lines[di+1]: e['b']='Multiple times available'
        out.append(e)
    return out
