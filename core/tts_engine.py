# core/tts_engine.py
import asyncio
from pydoc import text
import edge_tts
import os
import pygame
import threading
import queue
import uuid

# create a queue to hold completed sentences for speaking
tts_queue = queue.Queue()

def _tts_worker():
    while True:
        sentence = tts_queue.get()  # wait for the next text to speak
        if sentence is None:  # sentinel value to shut down the worker
            break
        # strip out tool calls from the text
        if "TOOL:" in sentence:
            sentence = sentence.split("TOOL:")[0].strip()

        if not sentence:
            tts_queue.task_done()
            continue  # skip empty sentences

        # Generate a unique filename for the audio
        audio_file = f"tts_{uuid.uuid4().hex}.mp3"

        async def generate_and_save():
            communicate = edge_tts.Communicate(sentence, "en-GB-RyanNeural")
            await communicate.save(audio_file)

        asyncio.run(generate_and_save())

        # play the audio blockingly in this worker thread
        pygame.mixer.init()
        pygame.mixer.music.load(audio_file)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)

        # unload the audio and clean up the file
        pygame.mixer.music.unload()
        if os.path.exists(audio_file):
            os.remove(audio_file)

        tts_queue.task_done()

# start the TTS worker thread
threading.Thread(target=_tts_worker, daemon=True).start()

def stream_speak(sentence: str):
    tts_queue.put(sentence)

async def _speak_async(text: str, voice: str = "en-GB-RyanNeural"):
    if not text.strip():
        return  # skip empty text
    
    # Generate speech using edge-tts
    audio_file = "output.mp3"
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(audio_file)

    print(f"[Debug] Generated TTS audio saved to {audio_file} for text: {text[:50]}...")

    # Play the generated speech using pygame
    pygame.mixer.init()
    pygame.mixer.music.load(audio_file)
    pygame.mixer.music.play()

    # Wait until the speech has finished playing
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)

    # Clean up the generated audio file
    pygame.mixer.quit()
    if os.path.exists(audio_file):
        os.remove(audio_file)

def speak(text: str):
    """Synchronous wrapper for the async TTS function."""
    asyncio.run(_speak_async(text))