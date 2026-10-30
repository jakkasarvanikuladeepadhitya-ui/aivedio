#!/usr/bin/env python3
"""REAL end-to-end test against a running Reelwright (local or Render). Standard library only (+ ffprobe on PATH).

    python tools/real_e2e.py https://your-app.onrender.com
    python tools/real_e2e.py http://localhost:8000 --duration 3 --aspect 9:16

It generates a small video with the server's configured provider, downloads it, verifies it with FFprobe, checks that
HTTP Range playback works, and prints  VIDEO GENERATION WORKING  ONLY if every step passed AND the provider was real AI.
If something fails it tells you which layer failed.
"""
import argparse, json, shutil, subprocess, sys, time, urllib.error, urllib.request

PROMPT = ("A cinematic Bengal tiger walking slowly through a misty rainforest at sunrise, realistic fur movement, "
          "smooth tracking camera, natural wildlife documentary style, no text.")
LAYER = {"provider_unavailable": "Provider", "provider_paused": "Provider", "api_changed": "Gradio API",
         "invalid_parameters": "Gradio API", "queue_timeout": "GPU queue", "quota_exhausted": "Quota",
         "auth_failure": "Provider", "generation_failure": "Provider", "invalid_output": "Provider",
         "no_provider": "Provider", "render_failure": "FFmpeg", "invalid_request": "Backend", "internal": "Backend"}


def req(url, data=None, headers=None, timeout=60):
    r = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                               headers={"Content-Type": "application/json", **(headers or {})})
    return urllib.request.urlopen(r, timeout=timeout)


def fail(layer, msg):
    print(f"\nFAILED at layer: {layer}\n  {msg}\n\nNOT working yet (this is not a success).")
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--duration", type=int, default=5)
    ap.add_argument("--aspect", default="16:9")
    ap.add_argument("--quality", default="turbo")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--out", default="reelwright_test.mp4")
    a = ap.parse_args()
    base = a.base.rstrip("/")
    if not shutil.which("ffprobe"):
        fail("Test machine", "ffprobe not found on this computer (install ffmpeg)")

    try:
        h = json.load(req(f"{base}/api/health"))
    except Exception as e:
        fail("Deployment", f"{base}/api/health not reachable: {e}")
    print("1. backend healthy:", h.get("backend"), "| ffmpeg:", h.get("ffmpeg"), "| ffprobe:", h.get("ffprobe"),
          "| provider configured:", h.get("provider_configured"))
    if not (h.get("ffmpeg") and h.get("ffprobe")):
        fail("Backend", "FFmpeg/FFprobe missing on the server")
    pr = json.load(req(f"{base}/api/providers"))
    for p in pr["providers"]:
        print(f"   provider {p['name']}: {p['status']} {p['message']} (real_ai={p['real_ai']})")
    if not pr["providers"]:
        fail("Provider", "no provider configured: " + json.dumps(pr.get("not_configured")))

    try:
        jid = json.load(req(f"{base}/api/generate", {"prompt": PROMPT, "duration": a.duration, "aspect_ratio": a.aspect,
                                                      "quality": a.quality, "narration": False, "music": False,
                                                      "subtitles": False}))["job_id"]
    except urllib.error.HTTPError as e:
        fail("Backend", f"/api/generate returned {e.code}: {e.read()[:200]}")
    print("2. backend accepted job", jid)

    t0, last = time.time(), None
    while True:
        j = json.load(req(f"{base}/api/jobs/{jid}"))
        line = f"{j['status']:<10} {j['progress']:>3}%  scene {j.get('current_scene')}/{j.get('total_scenes')}  {j.get('provider_status') or j['message']}"
        if line != last:
            print("  ", line)
            last = line
        if j["status"] == "done":
            break
        if j["status"] == "failed":
            fail(LAYER.get(j.get("error_category"), "Backend"), f"[{j.get('error_category')}] {j.get('error')}")
        if time.time() - t0 > a.timeout:
            fail("GPU queue", f"no result after {a.timeout}s")
        time.sleep(3)
    print("3. job done; provider(s):", j.get("provider_used"), "| real_ai:", j.get("real_ai"))
    if j.get("real_ai") is not True:
        fail("Provider", "the video was NOT produced by a real AI provider (placeholder engine). Not counting it.")

    url = base + j["download_url"]
    with req(url, timeout=300) as r:
        data = r.read()
    open(a.out, "wb").write(data)
    print(f"4. downloaded {len(data)} bytes -> {a.out}")
    try:
        r2 = urllib.request.urlopen(urllib.request.Request(url, headers={"Range": "bytes=0-99"}), timeout=60)
        ranged = (r2.status, len(r2.read()))
    except Exception as e:
        fail("Backend", f"Range request failed: {e}")
    if ranged != (206, 100):
        fail("Backend", f"browser-style Range playback not supported (got {ranged})")
    print("5. HTTP Range (browser playback/seek) OK")

    p = subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", a.out], capture_output=True, text=True)
    if p.returncode:
        fail("FFmpeg", "ffprobe cannot read the downloaded file: " + p.stderr[-200:])
    info = json.loads(p.stdout)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    dur = float(info["format"]["duration"])
    if not v or v["codec_name"] != "h264" or v["pix_fmt"] != "yuv420p" or dur <= 0:
        fail("FFmpeg", f"final video is not H.264/yuv420p with a duration: {v} {dur}")
    print(f"6. ffprobe OK: {v['codec_name']} {v['pix_fmt']} {v['width']}x{v['height']} {dur:.1f}s")
    try:
        req(f"{base}{j['download_url']}?inline=false", timeout=60).read(10)
        req(f"{base}/api/jobs/{jid}/poster", timeout=60).read(10)
    except Exception as e:
        fail("Backend", f"download/poster endpoint: {e}")
    print("7. download + poster endpoints OK")
    print(f"\nVIDEO GENERATION WORKING  ({time.time() - t0:.0f}s, provider: {j.get('provider_used')})")
    print("Last manual step: open the saved file or the site in a browser and press play.")


if __name__ == "__main__":
    main()
