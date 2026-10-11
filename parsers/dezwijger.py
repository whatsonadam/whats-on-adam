"""Pakhuis de Zwijger /agenda (rendered markdown). Each programme ends with a
'[Reserveer](ticket-url)' line; the date line looks like 'Vandaag, 18.00', 'Morgen, 20.00',
'ma 5 okt, 19.30' or '7 okt 2026 - 8 okt 2026'. Falls back to WebFetch pipe lines."""
import re, datetime
from pipe_lines import parse_lines
MON={'jan':1,'feb':2,'mrt':3,'apr':4,'mei':5,'jun':6,'jul':7,'aug':8,'sep':9,'okt':10,'nov':11,'dec':12}
DAY=re.compile(r'^(?:(vandaag|morgen)|(?:ma|di|wo|do|vr|za|zo) (\d{1,2}) (\w{3}))(?:, (\d{1,2})[.:](\d\d))?$', re.I)
RANGE=re.compile(r'^(\d{1,2}) (\w{3}) (\d{4}) - (\d{1,2}) (\w{3}) (\d{4})$')
def year_for(m, today): return today.year + (1 if m < today.month - 2 else 0)
def parse(text, today):
    if '[Reserveer]' not in text:
        return parse_lines(text, today, 'dezwijger', 'Pakhuis de Zwijger', 'talk')
    out=[]; end=today+datetime.timedelta(days=120)
    parts=re.split(r'\n\[Reserveer\]\((https?://[^)]+)\)', text)
    for i in range(0, len(parts)-1, 2):
        lines=[l.strip() for l in parts[i].split('\n') if l.strip() and not re.fullmatch(r'\d+', l.strip())]
        url=parts[i+1]
        di=None; d=ed=None; h=None
        for j in range(len(lines)-1, -1, -1):
            m=DAY.match(lines[j]); r=RANGE.match(lines[j])
            if m:
                if m.group(1): d=today+datetime.timedelta(days=0 if m.group(1).lower()=='vandaag' else 1)
                else:
                    mo=MON.get(m.group(3).lower()[:3])
                    if not mo: continue
                    try: d=datetime.date(year_for(mo,today), mo, int(m.group(2)))
                    except ValueError: continue
                if m.group(4): h=f"{int(m.group(4)):02d}:{m.group(5)}"
                di=j; break
            if r and MON.get(r.group(2)) and MON.get(r.group(5)):
                d=datetime.date(int(r.group(3)),MON[r.group(2)],int(r.group(1))); ed=datetime.date(int(r.group(6)),MON[r.group(5)],int(r.group(4)))
                di=j; break
        if di is None or di < 2: continue
        last=ed or d
        if last < today or d > end: continue
        title, blurb = lines[di-2], lines[di-1]
        room = lines[di+1] if di+1 < len(lines) else ''
        e={'t':title,'d':d.isoformat(),'v':'Pakhuis de Zwijger','s':'dezwijger','u':url,'c':'talk','b':blurb[:120]}
        if room and 'PDZ' in room: e['v']=f"Pakhuis de Zwijger · {room.replace(' PDZ','')}"
        if ed and (ed-d).days>=1: e['ed']=ed.isoformat(); e['c']='other'
        if h: e['h']=h
        tail=' '.join(lines[di+1:]).lower()
        if 'english' in tail: e['en']=1
        out.append(e)
    return out
