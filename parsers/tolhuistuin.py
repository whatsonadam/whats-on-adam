"""Tolhuistuin: markdown of /en/agenda after clicking 'load more'. Day headers like
'donderdag 24 september' followed by '* [### Title\n\n blurb](url)' items."""
import re, datetime
M={'januari':1,'februari':2,'maart':3,'april':4,'mei':5,'juni':6,'juli':7,'augustus':8,'september':9,'oktober':10,'november':11,'december':12}
def cat(s):
    s=s.lower()
    for k,c in [('clubnacht','club'),('club','club'),('workshop','workshop'),('talk','talk'),('lezing','talk'),('theater','theatre'),('film','film'),('markt','community'),('koor','music'),('kinder','kids'),('expo','exhibition')]:
        if k in s: return c
    return 'music'
def parse(text, today):
    parts=re.split(r'\n(?:#+ )?(?:maandag|dinsdag|woensdag|donderdag|vrijdag|zaterdag|zondag) (\d{1,2}) (\w+)\n(?:-+\n)?',text)
    out=[]; end=today+datetime.timedelta(days=120)
    for i in range(1,len(parts),3):
        m=M.get(parts[i+1].lower())
        if not m: continue
        y=today.year+(1 if m<today.month-2 else 0)
        try: d=datetime.date(y,m,int(parts[i]))
        except ValueError: continue
        if d<today or d>end: continue
        for mm in re.finditer(r'\[### (.+?)\n\n\s*(.*?)\]\((https://tolhuistuin[^)]+)\)(.*?)(?=\n\* \[###|\Z)',parts[i+2],re.S):
            title,blurb,url,rest=mm.groups()
            e={'t':title.strip(),'d':d.isoformat(),'v':'Tolhuistuin','s':'tolhuistuin','u':url,'c':cat(title+' '+blurb)}
            b=blurb.strip()[:120]
            if b and b!='wordt nog aangeleverd': e['b']=b
            if 'Free' in rest[:40]: e['p']='Free'
            out.append(e)
    return out
