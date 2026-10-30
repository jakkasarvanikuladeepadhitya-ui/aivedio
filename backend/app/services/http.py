"""Small stdlib HTTP helpers (no extra dependency). Returns (status, parsed_json_or_text)."""
import json,urllib.error,urllib.request
from pathlib import Path
def request(method:str,url:str,headers=None,body=None,timeout=60):
 data=json.dumps(body).encode() if body is not None else None; h={"Content-Type":"application/json","Accept":"application/json",**(headers or {})}; req=urllib.request.Request(url,data=data,headers=h,method=method)
 try:
  with urllib.request.urlopen(req,timeout=timeout) as r: raw,status=r.read().decode(errors="ignore"),r.status
 except urllib.error.HTTPError as e: raw,status=e.read().decode(errors="ignore"),e.code
 except (urllib.error.URLError,TimeoutError,ConnectionError,OSError) as e: raise RuntimeError(f"Network error calling {url.split('?')[0]}: {e}")
 try:return status,json.loads(raw)
 except ValueError:return status,raw
def download(url:str,out:Path,timeout=300)->Path:
 try:
  with urllib.request.urlopen(url,timeout=timeout) as r: out.write_bytes(r.read())
 except (urllib.error.URLError,TimeoutError,OSError) as e: raise RuntimeError(f"Download failed: {e}")
 return out
