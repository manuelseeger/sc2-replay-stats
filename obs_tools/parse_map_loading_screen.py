import pytesseract
import cv2
from bs4 import BeautifulSoup
import requests
import numpy
from Levenshtein import distance as levenstein
import threading
import os
from os.path import split, splitext, join
from time import sleep, time
import re
from datetime import datetime
from blinker import signal
from config import config
import logging
from obs_tools.sc2client import sc2client

log = logging.getLogger(f"{config.name}.{__name__}")

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
)
cvflags = None

# portrait size
W, H = 105, 105


def get_right_portrait(image):
    x, y = 2235, 560
    return image[y : y + H, x : x + W]


def get_left_portrait(image):
    x, y = 221, 560
    return image[y : y + H, x : x + W]


def save_portrait(portrait, new_name):
    path, _ = split(config.screenshot)
    portrait_name = splitext(new_name)[0] + "_portrait.png"
    cv2.imwrite(join(path, "portraits", portrait_name), portrait)


def is_student(player_name: str) -> bool:
    return player_name.strip().lower() == config.student.name.lower()


def parse_map_loading_screen(filename):
    image = cv2.imread(filename, flags=cvflags)

    if type(image) is not numpy.ndarray:
        return None

    x, y, w, h = 940, 900, 670, 100
    ROI = image[y : y + h, x : x + w]
    mapname = pytesseract.image_to_string(ROI, lang="eng")
    x, y, w, h = 333, 587, 276, 40
    ROI = image[y : y + h, x : x + w]
    player_left = pytesseract.image_to_string(ROI, lang="eng")
    x, y, w, h = 1953, 587, 276, 40
    ROI = image[y : y + h, x : x + w]
    player_right = pytesseract.image_to_string(ROI, lang="eng")

    opponent_portrait = None
    if is_student(player_left):
        opponent_portrait = get_right_portrait(image)
    if is_student(player_right):
        opponent_portrait = get_left_portrait(image)

    return (
        mapname.strip().lower(),
        player_left.strip(),
        player_right.strip(),
        opponent_portrait,
    )


def clean_map_name(map, ladder_maps):
    map = map.strip().lower()
    if map not in ladder_maps:
        for ladder_map in ladder_maps:
            if levenstein(map, ladder_map) < 5:
                map = ladder_map
                break
    return map


def get_map_stats(map):
    with requests.Session() as s:
        url = f"{config.student.sc2replaystats_map_url}/{config.season}/{config.student.race[0]}"
        r = s.get(url)
        soup = BeautifulSoup(r.content, "html.parser")

        h2s = soup("h2")

        for h2 in h2s:
            if h2.string.lower() == map:
                for sibling in h2.parent.next_siblings:
                    if sibling.name == "table":
                        return sibling


barcode = "BARCODE"

cleanf = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
clean_clan = re.compile(r"<(.+)>\s+(.*)")


def split_clan_tag(name):
    result = clean_clan.search(name)
    if result is not None:
        return result.group(1), result.group(2)
    else:
        return None, name


def rename_file(filename, new_name):
    path, _ = os.path.split(filename)
    os.rename(filename, os.path.join(path, new_name))


def wait_for_file(file_path: str, timeout: int = 3, delay: float = 0.1) -> bool:
    """Wait for a file to be fully written before reading it"""
    start_time = time()
    prev_mtime = 0

    while time() - start_time < timeout:
        current_mtime = os.path.getmtime(file_path)
        if current_mtime != prev_mtime:
            prev_mtime = current_mtime
        else:
            # No changes in the last iteration, assume the file is fully written
            return True
        sleep(delay)
    return False


class LoadingScreenScanner(threading.Thread):
    def __init__(self, name):
        super().__init__()
        self.name = name
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()

    def run(self):
        self.scan_loading_screen()

    def scan_loading_screen(self):
        log.debug("Starting loading screen scanner")
        loading_screen = signal("loading_screen")
        while True:
            if self.stopped():
                log.debug("Stopping loading screen scanner")
                break
            if os.path.exists(config.screenshot):
                log.info("map loading screen detected")
                sleep(0.3)

                if wait_for_file(config.screenshot):
                    parse = parse_map_loading_screen(config.screenshot)
                else:
                    log.error("File not readable")
                    continue
                map, player1, player2, opponent_portrait = parse

                map = clean_map_name(map, config.ladder_maps)

                if len(player1) == 0:
                    player1 = barcode
                if len(player2) == 0:
                    player2 = barcode

                clan1, player1 = split_clan_tag(player1)
                clan2, player2 = split_clan_tag(player2)
                log.info(f"Found: {map}, {player1}, {player2}")

                now = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
                new_name = f"{map} - {cleanf.sub('', player1)} vs {cleanf.sub('', player2)} {now}.png"
                new_name = re.sub(r"[^\w_. -]", "_", new_name)

                if player1.lower() == config.student.name.lower():
                    opponent = player2
                elif player2.lower() == config.student.name.lower():
                    opponent = player1
                else:
                    log.info(f"not {config.student}, I'll keep looking")
                    os.remove(config.screenshot)
                    continue

                if opponent == barcode:
                    log.info("Barcode detected, trying to get exact barcode")
                    gameinfo = sc2client.wait_for_gameinfo()
                    opponent = sc2client.get_opponent_name(gameinfo)
                    log.info(f"Barcode resolved to {opponent}")

                rename_file(config.screenshot, new_name)
                save_portrait(opponent_portrait, new_name)

                loading_screen.send(
                    self,
                    map=map,
                    student=config.student,
                    opponent=opponent,
                    new_name=new_name,
                )
