# MagicMirror
This is a short python script that allows the user to use the RPi GPIO to trigger successive video plays using VLC. This was designed for a fantasy/game store as an interactive prop. The prop is a one-way mirror with a monitor placed behind it and an A3144 hall effect sensor connected to the RPi GPIO in order to detect magnetic inputs and trigger the videos.

It can play any number of videos on a rotation, and is currently set to use GPIO26 (BCM) as a trigger and is currently set to play 3 videos called "video1.mp4", "video2.mp4", and "video3.mp4". Since the script uses VLC to play the videos, it can play almost any format of video, but you will need to change the extension in the python script if using something other than mp4. As is, you can simply put 3 videos with these video names directly into your home directory (assign it to the correct path in the script, current user for my purposes was "wiz", not "pi").

I am currently using a raspberry pi 2b to run this script. It runs best in GUI mode, as it uses X11 to generate the black frame. If you are running in headless, make sure to start an X11 context manually before running the script.

The only dependencies are pygame, RPi.GPIO, and VLC.
