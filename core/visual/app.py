"""Wilfrid — application locale (chat + voix + sphère, sans autorité).

UN SEUL runtime Wilfrid persistant : chaque message/voix traverse le
même Core (dialogue, mémoire, knowledge, outils gouvernés). Aucune
approbation exposée ici (ni bouton ni route) : les autorisations
restent REPL/opérateur. Voix : PCM 16 kHz reçu (décodé côté client),
STT local, réponse Pierre en WAV. Aucun secret, aucune donnée
personnelle stockée par l'app.
"""

from __future__ import annotations

import base64
import io
import json
import wave
from typing import Any, Dict, Tuple

from core.visual.hook import VisualHook

PAGE_CHAT = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wilfrid</title>
<style>body{font-family:sans-serif;max-width:640px;margin:auto;padding:8px;
background:#0a0a18;color:#dfe6ff}img{width:128px}#log{border:1px solid #335;
min-height:200px;padding:8px;margin:8px 0}#etat{color:#8fb8ff}</style>
</head><body>
<h1>◉ Wilfrid <span id="etat">…</span></h1>
<img id="sphere" src="/png" alt="Wilfrid">
<div id="log"></div>
<input id="msg" size="40" placeholder="Écris à Wilfrid…">
<button onclick="send()">Envoyer</button>
<button id="mic" onclick="talk()">🎤 Parler</button>
<script>
async function refresh(){
 const r=await fetch('/snapshot');const s=await r.json();
 document.getElementById('etat').textContent=s.etat+' ('+s.fraicheur+')';
 document.getElementById('sphere').src='/png?tick='+Date.now();
}
setInterval(refresh,2000);refresh();
async function send(){
 const t=document.getElementById('msg').value;if(!t)return;
 const r=await fetch('/api/chat',{method:'POST',headers:
 {'Content-Type':'application/json'},body:JSON.stringify({text:t})});
 const j=await r.json();
 log('Moi: '+t);log('Wilfrid: '+j.answer);
 document.getElementById('msg').value='';
}
function log(t){const d=document.getElementById('log');
 d.innerHTML+='<p>'+t.replace(/</g,'&lt;')+'</p>';}
async function talk(){
 const b=document.getElementById('mic');b.textContent='🔴 Écoute…';
 const stream=await navigator.mediaDevices.getUserMedia({audio:true});
 const rec=new MediaRecorder(stream);const chunks=[];
 rec.ondataavailable=e=>chunks.push(e.data);
 rec.start();await new Promise(r=>setTimeout(r,4000));rec.stop();
 await new Promise(r=>rec.onstop=r);stream.getTracks().forEach(t=>t.stop());
 b.textContent='🎤 Parler';
 const buf=await new Blob(chunks).arrayBuffer();
 const ctx=new (window.AudioContext||window.webkitAudioContext)();
 const decoded=await ctx.decodeAudioData(buf);
 const rate=16000;
 const off=new OfflineAudioContext(1,decoded.duration*rate,rate);
 const src=off.createBufferSource();src.buffer=decoded;src.connect(off.destination);
 src.start();const out=await off.startRendering();
 const pcm=out.getChannelData(0);const raw=new Int16Array(pcm.length);
 for(let i=0;i<pcm.length;i++)raw[i]=Math.max(-32768,Math.min(32767,pcm[i]*32767));
 const b64=btoa(String.fromCharCode(...new Uint8Array(raw.buffer)));
 const r=await fetch('/api/voice',{method:'POST',headers:
 {'Content-Type':'application/json'},body:JSON.stringify({pcm_b64:b64})});
 const j=await r.json();
 log('Moi (voix): '+j.text);log('Wilfrid: '+j.answer);
 const aw=new Audio('data:audio/wav;base64,'+j.audio_b64);aw.play();
}
</script></body></html>
"""


class WilfridApp:
    """Application : UN runtime, chat/voix/visuel branchés dessus."""

    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime
        self.hook = VisualHook()
        try:
            self.hook.refresh(runtime)
        except Exception:
            pass

    def handle(self, path: str, body: bytes = b""
               ) -> Tuple[int, bytes, str]:
        """Route une requête (GET/POST déjà distingués par l'appelant)."""
        if path == "/" or path == "/chat":
            return 200, PAGE_CHAT.encode("utf-8"), \
                "text/html; charset=utf-8"
        if path == "/snapshot":
            data = self.hook.snapshot()
            public = {"etat": data.get("etat", "INCONNU"),
                      "mode": data.get("mode", ""),
                      "horodatage": data.get("horodatage", 0.0),
                      "raison": data.get("raison", "")}
            return 200, json.dumps(public,
                                   ensure_ascii=False).encode("utf-8"), \
                "application/json"
        if path == "/png":
            try:
                return 200, self.hook.png(), "image/png"
            except Exception:
                return 500, b"rendu-impossible", "text/plain"
        if path == "/page":
            from core.visual.page import page_html
            data = self.hook.snapshot()
            public = {"etat": data.get("etat", "INCONNU"),
                      "horodatage": data.get("horodatage", 0.0),
                      "raison": data.get("raison", "")}
            return 200, page_html(public).encode("utf-8"), \
                "text/html; charset=utf-8"
        if path == "/api/chat":
            return self._chat(body)
        if path == "/api/voice":
            return self._voice(body)
        return 404, b"inconnu", "text/plain"

    def _chat(self, body: bytes) -> Tuple[int, bytes, str]:
        try:
            data = json.loads(body.decode("utf-8") or "{}")
        except ValueError:
            return 400, b"json-invalide", "text/plain"
        text = data.get("text", "") if isinstance(data, dict) else ""
        if not isinstance(text, str) or not text.strip() \
                or len(text) > 2000:
            return 400, b"texte-invalide", "text/plain"
        try:
            done, result = self.runtime.run_turn(text.strip())
        except Exception:
            return 500, b"erreur-moteur", "text/plain"
        if not done:
            return 500, b"tour-impossible", "text/plain"
        try:
            self.hook.refresh(self.runtime)
        except Exception:
            pass
        answer = result.response.text \
            if result.response is not None and isinstance(
                result.response.text, str) else str(result.detail)
        payload = {"answer": answer, "kind": str(result.kind),
                   "request_id": str(getattr(result, "request_id", ""))}
        return 200, json.dumps(payload,
                               ensure_ascii=False).encode("utf-8"), \
            "application/json"

    def _voice(self, body: bytes) -> Tuple[int, bytes, str]:
        try:
            data = json.loads(body.decode("utf-8") or "{}")
        except ValueError:
            return 400, b"json-invalide", "text/plain"
        raw = (data.get("pcm_b64", "") if isinstance(data, dict) else "")
        try:
            pcm = base64.b64decode(raw, validate=True)
        except Exception:
            return 400, b"pcm-invalide", "text/plain"
        if not pcm or len(pcm) > 1048576 or len(pcm) % 2:
            return 400, b"pcm-invalide", "text/plain"
        try:
            from core.voice.stt_local import stt_fn_for
            text, _conf = stt_fn_for()(pcm)
        except Exception:
            return 502, b"stt-indisponible", "text/plain"
        if not text.strip():
            return 200, json.dumps(
                {"text": "", "answer": "Je n'ai rien entendu.",
                 "audio_b64": ""}, ensure_ascii=False).encode("utf-8"), \
                "application/json"
        try:
            done, result = self.runtime.run_turn(text.strip())
        except Exception:
            return 500, b"erreur-moteur", "text/plain"
        if not done:
            return 500, b"tour-impossible", "text/plain"
        answer = result.response.text \
            if result.response is not None and isinstance(
                result.response.text, str) else str(result.detail)
        try:
            self.hook.refresh(self.runtime)
        except Exception:
            pass
        try:
            from core.voice.voice_router import speak_validated
            status, audio, _rep = speak_validated(answer)
            if status != "OK" or not audio:
                raise RuntimeError("tts:" + status)
            encoded = base64.b64encode(bytes(audio)).decode("ascii")
        except Exception:
            encoded = ""
        payload = {"text": text.strip(), "answer": answer,
                   "kind": str(result.kind), "audio_b64": encoded}
        return 200, json.dumps(payload,
                               ensure_ascii=False).encode("utf-8"), \
            "application/json"

    def describe(self) -> Dict[str, Any]:
        """Contrat app (sans effet)."""
        return {"runtime": "unique-persistant",
                "routes": ["/", "/api/chat", "/api/voice",
                           "/snapshot", "/png", "/page"],
                "approbations": "non-exposees",
                "network": "localhost-uniquement", "authority": False}
