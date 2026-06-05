# core/tts_engine.py
import asyncio
import edge_tts
import os
import pygame

async def _speak_async(text: str, voice: str = "en-GB-RyanNeural"):
    if not text.strip():
        return  # skip empty text
    
    # Generate speech using edge-tts
    audio_file = "output.mp3"
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(audio_file)

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