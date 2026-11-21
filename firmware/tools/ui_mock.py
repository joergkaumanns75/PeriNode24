import http.server, json, re, sys, math, urllib.parse
SRC = open(sys.argv[1]).read()
HTML = re.search(r'R"rawliteral\((.*)\)rawliteral"', SRC, re.S).group(1)
ch = [
 dict(st=2,name="Konstantstrom",v=13.214,i=0.600,t=24.5,vt=14.31,ah=0.912,ts=4210,en=True,err=""),
 dict(st=3,name="Konstantspannung",v=14.309,i=0.214,t=25.1,vt=14.31,ah=1.633,ts=2950,en=True,err=""),
 dict(st=4,name="Erhaltung",v=13.561,i=0.019,t=23.9,vt=13.56,ah=1.884,ts=312,en=True,err=""),
 dict(st=6,name="Fehler",v=10.454,i=0.0,t=26.2,vt=0,ah=0.476,ts=880,en=True,err="Tiefentladen/defekt"),
 dict(st=0,name="kein Akku",v=0.0,i=0.0,t=None,vt=0,ah=0,ts=43200,en=True,err=""),
 dict(st=7,name="Aus",v=12.71,i=0.0,t=22.0,vt=0,ah=0,ts=60,en=False,err=""),
]
params = dict(vAbs=14.4,vFloat=13.65,tk=-18.0,iBulk=0.6,iPre=0.24,iTerm=0.072,iRebulk=0.3,tMax=45.0,hAbsMax=4.0,hChgMax=10.0,ssid="Heimnetz")
posts = []
def hist(k):
    v=[];i=[]
    for n in range(240):
        x=n/240
        if x<0.55: v.append(int(12400+1900*x/0.55)); i.append(600)
        else: v.append(14310); i.append(int(600*math.exp(-(x-0.55)*6)))
    return dict(ch=k,step=30,v=v,i=i)
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def out(self,code,obj,ct="application/json"):
        b = obj.encode() if isinstance(obj,str) else json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type",ct); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        u=urllib.parse.urlparse(self.path); q=urllib.parse.parse_qs(u.query)
        if u.path=="/": return self.out(200,HTML,"text/html; charset=utf-8")
        if u.path=="/api/status": return self.out(200,dict(fw="2.0",up=43210,vbus=24.1,wifi=dict(sta=True,ssid="Heimnetz",ip="192.168.1.57",rssi=-61,ap=False),ch=ch))
        if u.path=="/api/history": return self.out(200,hist(int(q.get("ch",["0"])[0])))
        if u.path=="/api/params": return self.out(200,params)
        self.out(404,"nicht gefunden","text/plain")
    def do_POST(self):
        n=int(self.headers.get("Content-Length",0)); d=dict(urllib.parse.parse_qsl(self.rfile.read(n).decode()))
        posts.append((self.path,d)); open(sys.argv[2],"a").write(json.dumps([self.path,d])+"\n")
        if d.get("pw")!="perinode24": return self.out(403,dict(ok=False,msg="Admin-Passwort falsch"))
        if self.path=="/api/cmd":
            k=d["ch"]
            if d["action"] in("enable","disable"):
                c=ch[int(k)]; c["en"]=d["action"]=="enable"; c["st"],c["name"]=(0,"kein Akku") if c["en"] else (7,"Aus")
            if d["action"]=="reset":
                for c in ch:
                    if c["st"]==6: c.update(st=0,name="kein Akku",err="")
            return self.out(200,dict(ok=True))
        if self.path=="/api/params":
            for kk in params:
                if kk in d and kk!="ssid": params[kk]=float(d[kk])
            return self.out(200,dict(ok=True,msg="Gespeichert"))
        return self.out(200,dict(ok=True,msg="Gespeichert - Neustart in 2 s"))
http.server.ThreadingHTTPServer(("127.0.0.1",8765),H).serve_forever()
