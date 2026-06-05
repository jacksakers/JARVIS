import asyncio
import edge_tts
import os
import pygame

async def speak(text):
    # Generate speech using edge-tts
    communicate = edge_tts.Communicate(text, "en-GB-RyanNeural")
    await communicate.save("output.mp3")

    # Play the generated speech using pygame
    pygame.mixer.init()
    pygame.mixer.music.load("output.mp3")
    pygame.mixer.music.play()

    # Wait until the speech has finished playing
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)

    # Clean up the generated audio file
    pygame.mixer.quit()
    os.remove("output.mp3")

asyncio.run(speak("Good morning. All systems are online and the lights are on!"))