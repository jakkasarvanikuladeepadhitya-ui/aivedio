"""Check a Hugging Face Space: python -m app.tools.inspect_space owner/space"""
import json,sys
from .. import config
from ..services import hf_space
from ..services.errors import ProviderError
def main(spaces):
 ok_any=False
 for sp in spaces:
  p=hf_space.HFSpaceProvider(sp);print(f"\n=== {sp} ===");h=p.health();print(f"runtime: {p.stage or '?'}  usable now: {h.ok}  {h.message}")
  if not h.ok: continue
  try: info=p.inspect()
  except ProviderError as e: print(f"  -> INCOMPATIBLE [{e.category.value}]: {e}");continue
  for c in info["candidates"]:
   if c["compatible"]: ok_any=True;print(f"  endpoint {c['endpoint']}: COMPATIBLE\n    parameters sent: {json.dumps(c['kwargs'])}")
   else: print(f"  endpoint {c['endpoint']}: incompatible: {c['reason']}")
 if not config.HF_TOKEN: print("\nNote: HF_TOKEN is not set. Anonymous calls get a very small free GPU quota.")
 print("\nResult:","at least one compatible Space" if ok_any else "NO compatible Space found");return 0 if ok_any else 1
if __name__=="__main__":
 if len(sys.argv)<2: sys.exit("usage: python -m app.tools.inspect_space owner/space [owner/space2 ...]")
 sys.exit(main(sys.argv[1:]))
