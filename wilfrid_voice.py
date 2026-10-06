from dotenv import load_dotenv
import os
import numpy as np
import sounddevice as sd
from elevenlabs.client import ElevenLabs

load_dotenv()

VOICE_ID = "bIHbv24MWmeRgasZH58o"
MODEL_ID = "eleven_multilingual_v2"
OUTPUT_FORMAT = "pcm_16000"
SAMPLE_RATE = 16000


def speak(text: str) -> None:
    text = text.strip()
    if not text:
        return

    api_key = os.environ["ELEVENLABS_API_KEY"]
    client = ElevenLabs(api_key=api_key)

    audio = client.text_to_speech.convert(
        voice_id=VOICE_ID,
        text=text,
        model_id=MODEL_ID,
        output_format=OUTPUT_FORMAT,
    )

    raw = b"".join(audio) if not isinstance(audio, (bytes, bytearray)) else audio
    samples = np.frombuffer(raw, dtype=np.int16)

    sd.play(samples, SAMPLE_RATE)
    sd.wait()


if __name__ == "__main__":
    speak("Bonjour. Je suis Wilfrid. Ma voix est maintenant active.")
