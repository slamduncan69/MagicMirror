import os
import pygame
import subprocess
import RPi.GPIO as GPIO
import time

os.environ["SDL_VIDEO_WINDOW_POS"] = "0,0"
os.environ["SDL_VIDEO_CENTERED"] = "1"
os.environ["SDL_VIDEO_FULLSCREEN_HEAD"] = "0"

# List of video files (update these paths as needed)
VIDEO_FILES = [
    "/home/wiz/video1.mp4",
    "/home/wiz/video2.mp4",
    "/home/wiz/video3.mp4"
]

# Track which video to play next
video_index = 0

# GPIO setup
BUTTON_PIN = 26 #Sets the GPIO input for the switch
GPIO.setmode(GPIO.BCM) #Broadcom numbering system
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP) #turns on internal pull-up resistor

pygame.init()

pygame.mouse.set_visible(False)

infoObject = pygame.display.Info()
WIDTH, HEIGHT = infoObject.current_w, infoObject.current_h

screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.NOFRAME | pygame.FULLSCREEN)
screen.fill((0, 0, 0))
pygame.display.update()

def wait_for_button_press():
    """Waits for a button press and debounces it."""
    while True:
        if GPIO.input(BUTTON_PIN) == GPIO.LOW:  # Button pressed
            time.sleep(0.2)  # Debounce delay
            while GPIO.input(BUTTON_PIN) == GPIO.LOW:  # Wait for release
                time.sleep(0.01)
            return  # Exit when button is released

running = True
while running:
    wait_for_button_press()  

    video_to_play = VIDEO_FILES[video_index]

    subprocess.run(["cvlc", "--fullscreen", "--play-and-exit", "--no-video-title-show", video_to_play])

    # Move to the next video in sequence (loop back to the first after the last)
    video_index = (video_index + 1) % len(VIDEO_FILES)

    # Reset to black screen
    screen.fill((0, 0, 0))
    pygame.display.update()

GPIO.cleanup()
pygame.quit()
