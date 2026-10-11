"""Shared format for sites that block automated browsers (De Zwijger, The School of Life).
Claude fetches them with WebFetch and saves lines: 'YYYY-MM-DD | HH:MM | title | url'."""
import datetime
def parse_lines(text, today, source, venue, cat):
    out=[]; end=today+datetime.timedelta(days=120)
    for line in text.splitlines():
        p=[x.strip() for x in line.split('|')]
        if len(p)<4: continue
        try: d=datetime.date.fromisoformat(p[0])
        except ValueError: continue
        if d<today or d>end: continue
        e={'t':p[2],'d':d.isoformat(),'v':venue,'s':source,'u':p[3],'c':cat}
        if len(p[1])==5 and p[1][2]==':': e['h']=p[1]
        out.append(e)
    return out
