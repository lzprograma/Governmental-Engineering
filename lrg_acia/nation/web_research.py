"""Pesquisa e leitura web com bloqueio de endereços locais e limites de conteúdo."""
from __future__ import annotations
import ipaddress, socket, re
from html.parser import HTMLParser
from urllib.parse import urlparse, urljoin, urlencode
import httpx

MAX_BYTES = 2_000_000
USER_AGENT = "LunzResearch/0.3 (+local research prototype)"

class WebResearchError(RuntimeError): pass


def validate_public_url(url: str) -> str:
    p=urlparse(url)
    if p.scheme not in {"http","https"} or not p.hostname: raise WebResearchError("Somente URLs http(s) são aceitas.")
    if p.username or p.password: raise WebResearchError("URLs com credenciais embutidas são bloqueadas.")
    host=p.hostname.rstrip(".").lower()
    if host in {"localhost","localhost.localdomain"} or host.endswith(".localhost") or host.endswith(".local"):
        raise WebResearchError("Hosts locais não podem ser acessados pelo mecanismo web.")
    try:
        infos=socket.getaddrinfo(host,p.port or (443 if p.scheme=="https" else 80),type=socket.SOCK_STREAM)
    except socket.gaierror as exc: raise WebResearchError("Não foi possível resolver o domínio informado.") from exc
    if not infos: raise WebResearchError("Domínio sem endereço resolvido.")
    for info in infos:
        ip=ipaddress.ip_address(info[4][0].split("%",1)[0])
        if not ip.is_global:
            raise WebResearchError("Acesso a IP privado, reservado ou link-local foi bloqueado.")
    return url

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.title=""; self.text=[]; self.links=[]; self._title=False; self._skip=0
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag=="title": self._title=True
        if tag in {"script","style","noscript","svg","iframe","nav","footer"}: self._skip+=1
        if tag=="a" and attrs.get("href"):
            self.links.append({"href":attrs["href"],"text":""})
        if tag=="br" or tag in {"p","div","li","h1","h2","h3","article"}: self.text.append("\n")
    def handle_endtag(self, tag):
        if tag=="title": self._title=False
        if tag in {"script","style","noscript","svg","iframe","nav","footer"} and self._skip: self._skip-=1
    def handle_data(self,data):
        if self._title: self.title+=data.strip()+" "
        if self._skip==0 and data.strip(): self.text.append(data.strip())
        if self.links and data.strip(): self.links[-1]["text"] += data.strip()+" "


def fetch_page(url: str, timeout: float=15) -> dict:
    current=validate_public_url(url)
    headers={"User-Agent":USER_AGENT,"Accept":"text/html,text/plain;q=0.9,*/*;q=0.2"}
    with httpx.Client(timeout=timeout,follow_redirects=False,verify=True,trust_env=True,headers=headers) as client:
        for _ in range(6):
            validate_public_url(current)
            try:
                with client.stream("GET",current) as response:
                    if response.status_code in {301,302,303,307,308}:
                        location=response.headers.get("location")
                        if not location: raise WebResearchError("Redirecionamento sem destino.")
                        current=urljoin(str(response.url),location)
                        continue
                    if response.status_code>=400: raise WebResearchError(f"O site retornou HTTP {response.status_code}.")
                    ctype=response.headers.get("content-type","").lower()
                    if not ("text/html" in ctype or "text/plain" in ctype or "application/xhtml" in ctype):
                        raise WebResearchError(f"Tipo de conteúdo não suportado: {ctype or 'desconhecido'}.")
                    chunks=[]; total=0; truncated=False
                    for chunk in response.iter_bytes():
                        if not chunk: continue
                        room=MAX_BYTES-total
                        if room<=0:
                            truncated=True; break
                        chunks.append(chunk[:room]); total += min(len(chunk),room)
                        if len(chunk)>room:
                            truncated=True; break
                    raw=b"".join(chunks)
                    encoding=response.encoding or "utf-8"
                    final_url=str(response.url)
            except httpx.HTTPError as exc: raise WebResearchError(f"Falha de rede: {exc}") from exc
            text=raw.decode(encoding,errors="replace")
            if "html" in ctype:
                parser=PageParser(); parser.feed(text)
                content=re.sub(r"\n{3,}","\n\n","\n".join(parser.text)).strip()
                title=parser.title.strip() or final_url
                links=[]
                for item in parser.links:
                    href=urljoin(final_url,item["href"])
                    if urlparse(href).scheme in {"http","https"} and item["text"].strip():
                        links.append({"url":href,"title":item["text"].strip()[:240]})
            else: title=final_url; content=text; links=[]
            if not content: raise WebResearchError("Não foi possível extrair texto útil desta página.")
            return {"url":final_url,"title":title[:300],"content":content[:60000],
                    "links":links[:60],"content_type":ctype,"bytes_read":len(raw),"truncated":truncated}
    raise WebResearchError("Limite de redirecionamentos excedido.")

class SearchParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.results=[]; self._active=None; self._snippet=False; self._capture=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs); cls=a.get("class","")
        if tag=="a" and "result__a" in cls:
            self._active={"url":a.get("href",""),"title":""}; self._capture=True; self._snippet=False
        elif "result__snippet" in cls: self._snippet=True; self._capture=True
    def handle_endtag(self,tag):
        if tag=="a" and self._active and self._capture:
            if self._active.get("title"): self.results.append(self._active)
            self._active=None; self._capture=False
        if tag in {"div","td"} and self._snippet: self._snippet=False; self._capture=False
    def handle_data(self,data):
        if self._active is not None and self._capture and data.strip(): self._active["title"]+=data.strip()+" "


def search_web(query: str, max_results: int=8, timeout: float=15) -> list[dict]:
    if not query.strip(): raise WebResearchError("Informe uma consulta de pesquisa.")
    url="https://html.duckduckgo.com/html/?"+urlencode({"q":query.strip()[:500]})
    validate_public_url(url)
    try:
        r=httpx.get(url,timeout=timeout,follow_redirects=False,headers={"User-Agent":USER_AGENT,"Accept":"text/html"},trust_env=True)
    except httpx.HTTPError as exc: raise WebResearchError(f"Falha na busca web: {exc}") from exc
    if r.status_code>=400: raise WebResearchError(f"O serviço de busca retornou HTTP {r.status_code}.")
    parser=SearchParser(); parser.feed(r.text)
    out=[]; seen=set()
    for item in parser.results:
        raw=item["url"].strip()
        # DDG redireciona por uddg; parse the query parameter when present.
        if raw.startswith("//"): raw="https:"+raw
        p=urlparse(raw)
        if p.netloc.endswith("duckduckgo.com") and "uddg" in p.query:
            from urllib.parse import parse_qs
            raw=parse_qs(p.query).get("uddg",[""])[0]
        if not raw.startswith("http") or raw in seen: continue
        seen.add(raw); out.append({"title":item["title"].strip(),"url":raw,"snippet":"Resultado indexado; abra a página para validar o conteúdo e a data."})
        if len(out)>=max(1,min(max_results,20)): break
    return out
