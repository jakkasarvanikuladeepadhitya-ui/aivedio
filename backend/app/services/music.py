"""Royalty-free background music generated locally with FFmpeg (soft ambient pad). No downloads, no copyright issues."""
import subprocess
from pathlib import Path
def ambient(out:Path,seconds:float)->Path:
 d=f"{seconds+2:.2f}"; cmd=["ffmpeg","-y"]
 for f in (110.0,164.81,220.0,277.18): cmd += ["-f","lavfi","-i",f"sine=frequency={f}:duration={d}"]
 cmd += ["-filter_complex","[0][1][2][3]amix=inputs=4:normalize=0,volume=0.6,tremolo=f=0.15:d=0.5,lowpass=f=900,aecho=0.8:0.7:500:0.3,aformat=channel_layouts=stereo[m]","-map","[m]",str(out)]
 r=subprocess.run(cmd,capture_output=True,text=True)
 if r.returncode: raise RuntimeError(f"Music generation failed: {r.stderr[-200:]}")
 return out
