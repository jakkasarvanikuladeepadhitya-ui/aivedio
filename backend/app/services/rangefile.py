"""HTTP Range support for the MP4 endpoints (Safari and seeking need 206 responses)."""
from pathlib import Path
from typing import Iterator,Optional,Tuple
def parse_range(header:str,size:int)->Optional[Tuple[int,int]]:
 if size<=0 or not header or not header.lower().startswith("bytes="):return None
 spec=header.split("=",1)[1].split(",")[0].strip()
 if "-" not in spec:return None
 a,b=spec.split("-",1)
 try:
  if a=="": n=int(b); return (max(0,size-n),size-1) if n>0 else None
  start=int(a); end=int(b) if b!="" else size-1
 except ValueError:return None
 if start<0 or start>=size or end<start:return None
 return start,min(end,size-1)
def iter_file(path:Path,start:int,end:int,chunk:int=1<<20)->Iterator[bytes]:
 with open(path,"rb") as f:
  f.seek(start); left=end-start+1
  while left>0:
   data=f.read(min(chunk,left))
   if not data:break
   left-=len(data); yield data
