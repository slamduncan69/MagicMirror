import os
import glob
import re
import random
import logging
from collections import deque
import pygame
import subprocess
import time

# Log to a file next to this script so the kiosk can be debugged without a
# visible terminal (the prop must stay black). Read /home/wiz/magicmirror.log
# after a run to see what happened.
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "magicmirror.log")
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

# Use the real GPIO button on a Raspberry Pi; fall back to keyboard control
# (spacebar) when the Pi library isn't available, so the mirror can be tested
# on a regular PC. The same script runs unchanged in both places.
try:
    import RPi.GPIO as GPIO
    ON_PI = True
except (ImportError, RuntimeError) as exc:
    GPIO = None
    ON_PI = False
    logging.warning("RPi.GPIO unavailable (%s) -> keyboard mode", exc)

os.environ["SDL_VIDEO_WINDOW_POS"] = "0,0"
os.environ["SDL_VIDEO_CENTERED"] = "1"
os.environ["SDL_VIDEO_FULLSCREEN_HEAD"] = "0"

# Folder containing the wizard answer clips (all *.mp4 inside are used).
# Defaults to a "wizardclips_mp4" folder sitting next to this script.
VIDEO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wizardclips_mp4")

# How many of the most-recently-shown ANSWERS to keep out of the random draw.
# The clips are 20 Magic 8-Ball answers x 3 wizards; we avoid repeating the
# same answer (regardless of which wizard delivers it) for this many draws.
# Bigger = repeats feel rarer but the sequence feels more like a fixed cycle.
RECENT_ANSWERS_TO_EXCLUDE = 7

BUTTON_PIN = 26  # GPIO input for the magnetic switch

# Force audio out the 3.5mm analog jack instead of HDMI. On this Pi the analog
# ALSA card is named "Headphones"; set to None to use the system default.
AUDIO_ALSA_DEVICE = "plughw:CARD=Headphones"

# Analog jack is quiet by default; set its hardware volume on startup (range
# tops out at +4dB). Applied every boot via amixer (needs no root). Set to None
# to leave the volume alone.
AUDIO_VOLUME = "0dB"


def canonical_answer(path):
    """Reduce a clip filename to a canonical answer key so the three wizards'
    versions of the same answer group together despite spelling/case
    differences (e.g. 'consentrate' vs 'concentrate', 'cant predict that now'
    vs 'cannot predict now', and files missing a closing parenthesis)."""
    base = os.path.splitext(os.path.basename(path))[0]
    m = re.search(r'\((.*?)\)?$', base)           # text inside parens; tolerate missing ')'
    text = m.group(1) if m else base
    t = text.lower()
    t = re.sub(r'[^a-z0-9 ]', ' ', t)             # drop commas/punctuation
    t = re.sub(r'\b(the|that)\b', ' ', t)         # filler words that vary between wizards
    t = t.replace('consentrate', 'concentr').replace('concentrate', 'concentr')
    t = t.replace('decitedly', 'decid').replace('decidedly', 'decid')
    t = re.sub(r'\bcant\b', 'cannot', t)
    t = t.replace('definatly', 'definit').replace('definitely', 'definit')
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def pick_video(video_files, clip_answers, recent_answers):
    """Randomly pick a clip whose answer wasn't among the recently shown ones."""
    candidates = [c for c in video_files if clip_answers[c] not in recent_answers]
    if not candidates:  # safety net if the exclusion list ever covers everything
        candidates = video_files
    choice = random.choice(candidates)
    recent_answers.append(clip_answers[choice])
    return choice


def wait_for_trigger():
    """Block until the user asks for an answer.

    Returns "draw" to play a clip, or "quit" to exit.
    On the Pi this watches the GPIO button; on a PC it watches the keyboard
    (SPACE/ENTER = draw, ESC/Q or closing the window = quit).

    Logs every change of the button pin's state so we can tell, from the log
    alone, whether the magnet is actually reaching the reed switch."""
    last_state = GPIO.input(BUTTON_PIN) if ON_PI else None
    while True:
        # Keep the window responsive and catch quit/keys in both modes.
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    return "quit"
                if not ON_PI and event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    return "draw"

        if ON_PI:
            state = GPIO.input(BUTTON_PIN)
            if state != last_state:
                logging.info("button pin %d changed: %s -> %s (LOW=%s means pressed)",
                             BUTTON_PIN, last_state, state, GPIO.LOW)
                last_state = state
            if state == GPIO.LOW:  # magnet present / switch closed
                time.sleep(0.2)  # Debounce delay
                while GPIO.input(BUTTON_PIN) == GPIO.LOW:  # Wait for release
                    time.sleep(0.01)
                last_state = GPIO.input(BUTTON_PIN)
                return "draw"

        time.sleep(0.01)


def main():
    logging.info("=== MagicMirror starting (ON_PI=%s) ===", ON_PI)

    # Discover clips and map each to its canonical answer.
    video_files = sorted(glob.glob(os.path.join(VIDEO_DIR, "*.mp4")))
    logging.info("Found %d clip(s) in %s", len(video_files), VIDEO_DIR)
    if not video_files:
        logging.error("No .mp4 clips found in %s -- exiting", VIDEO_DIR)
        raise SystemExit("No .mp4 clips found in {}".format(VIDEO_DIR))
    clip_answers = {clip: canonical_answer(clip) for clip in video_files}
    recent_answers = deque(maxlen=RECENT_ANSWERS_TO_EXCLUDE)

    # Set the analog jack's hardware volume on the Pi (it defaults low). Runs as
    # the session user, no root needed, and re-applies on every boot.
    if ON_PI and AUDIO_VOLUME:
        r = subprocess.run(["amixer", "-c", "Headphones", "sset", "PCM", AUDIO_VOLUME],
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        logging.info("Set jack volume to %s (amixer rc=%s %s)",
                     AUDIO_VOLUME, r.returncode, r.stderr.decode(errors="ignore").strip())

    # GPIO setup (Pi only)
    if ON_PI:
        GPIO.setmode(GPIO.BCM)  # Broadcom numbering system
        GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # internal pull-up
        logging.info("GPIO ready. Pin %d resting state=%s (expect HIGH=%s at rest)",
                     BUTTON_PIN, GPIO.input(BUTTON_PIN), GPIO.HIGH)

    pygame.init()
    pygame.mouse.set_visible(False)

    info = pygame.display.Info()
    width, height = info.current_w, info.current_h

    # Fullscreen on the mirror; a smaller window on a PC so it's easy to test/quit.
    if ON_PI:
        screen = pygame.display.set_mode((width, height), pygame.NOFRAME | pygame.FULLSCREEN)
        pygame.mouse.set_visible(False)                 # keep the cursor hidden on the mirror
        pygame.mouse.set_pos((width - 1, height - 1))   # and park it in the corner as a fallback
    else:
        pygame.mouse.set_visible(True)
        pygame.display.set_caption("MagicMirror (PC test) - press SPACE to ask, ESC to quit")
        screen = pygame.display.set_mode((640, 360))
    screen.fill((0, 0, 0))
    pygame.display.update()
    logging.info("Display ready (%dx%d). Waiting for input...", width, height)

    while True:
        if wait_for_trigger() == "quit":
            logging.info("Quit requested -- exiting")
            break

        video_to_play = pick_video(video_files, clip_answers, recent_answers)
        logging.info("Playing: %s", os.path.basename(video_to_play))
        cmd = ["cvlc", "--fullscreen", "--play-and-exit", "--no-video-title-show"]
        if ON_PI and AUDIO_ALSA_DEVICE:
            cmd += ["--aout=alsa", "--alsa-audio-device=" + AUDIO_ALSA_DEVICE]
        cmd.append(video_to_play)
        subprocess.run(cmd)

        # Reset to black screen
        screen.fill((0, 0, 0))
        pygame.display.update()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        logging.exception("Fatal error -- crashing")
        raise
    finally:
        if ON_PI and GPIO is not None:
            GPIO.cleanup()
        pygame.quit()
