"""Fast mode: one AI image per scene, then animated with a pan/zoom in FFmpeg."""
import gc,threading
from pathlib import Path
from .. import config
SIZES={"16:9":(640,384),"9:16":(384,640),"1:1":(512,512)}; _pipe=None; _gpu=threading.Lock()
def _need_cuda():
 try: import torch
 except ImportError: raise RuntimeError("PyTorch is not installed. Run scripts/setup_wsl.sh")
 if not torch.cuda.is_available(): raise RuntimeError("No CUDA GPU visible. Run nvidia-smi in WSL, or set VIDEO_PROVIDER=mock.")
 return torch
def _load():
 global _pipe
 if _pipe is None:
  torch=_need_cuda(); from diffusers import AutoPipelineForText2Image as P
  try: pipe=P.from_pretrained(config.IMAGE_MODEL_ID,torch_dtype=torch.float16,variant="fp16")
  except Exception: pipe=P.from_pretrained(config.IMAGE_MODEL_ID,torch_dtype=torch.float16)
  pipe.set_progress_bar_config(disable=True); _pipe=pipe.to("cuda")
 return _pipe
def generate(prompt:str,aspect:str,out_png:Path)->Path:
 torch=_need_cuda()
 with _gpu:return _generate(torch,prompt,aspect,out_png)
def _generate(torch,prompt,aspect,out_png):
 pipe=_load(); w,h=SIZES.get(aspect,SIZES["16:9"]); gen=torch.Generator("cuda").manual_seed(int(config.SEED)) if config.SEED.isdigit() else None
 img=pipe(prompt=prompt[:300],num_inference_steps=config.IMAGE_STEPS,guidance_scale=0.0,width=w,height=h,generator=gen).images[0]; img.save(out_png); return out_png
def release():
 global _pipe
 _pipe=None; gc.collect()
 try:
  import torch
  if torch.cuda.is_available():torch.cuda.empty_cache()
 except ImportError:pass
