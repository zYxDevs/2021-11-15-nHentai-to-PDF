# Copyright (c) 2023 구FS, all rights reserved. Subject to the MIT licence in `licence.md`.
import inspect
import dataclasses
from KFSfstr  import KFSfstr
from KFSmedia import KFSmedia
import json
import logging
import os
import PIL.Image
import random
import re
import requests
import time
import typing


@dataclasses.dataclass
class Hentai:
    """
    represents an individual hentai
    """

    galleries: typing.ClassVar[list[dict]]=[]   # list of already downloaded galleries


    def __init__(self, nhentai_ID: int, cookies: dict[str, str], headers: dict[str, str]):
        """
        Constructs hentai object. Downloads data from the nhentai API.

        Arguments:
        - nhentai_ID: the hentai from nhentai.net found here: https://nhentai.net/g/{hentai_ID}
        - cookies: cookies to send with the request to bypass bot protection
        - headers: user agent to send with the request to bypass bot protection

        Raises:
        - requests.HTTPError: Downloading gallery from \"{NHENTAI_GALLERY_API_URL}/{self.ID}\" failed multiple times.
        - ValueError: Hentai with ID \"{self.ID}\" does not exist.
        """

        self._fails: list[int]      # list of how many times individual page has failed to be downloaded or converted to PDF
        self._gallery: dict         # gallery from nhentai API, saved to extract data for download later
        self._give_up: bool=False   # give this hentai up? after failing to download or convert numerous times
        self.ID: int                # nhentai ID
        self.page_amount: int       # number of pages
        self.title: str             # title (unchanged)


        logging.debug("Creating hentai object...")
        self.ID=nhentai_ID
        self._gallery=self._get_gallery(self.ID, cookies, headers)
        self.page_amount=int(self._gallery["num_pages"])
        self.title=self._gallery["title"]["pretty"]
        self._fails=[0 for _ in range(self.page_amount)]    # initialise with amount of pages number of zeros
        logging.debug("Created hentai object.")
        logging.debug(self.__repr__())

        return
    

    def __str__(self) -> str:
        return f"{self.ID}: \"{self.title}\""
    

    @classmethod
    def _get_gallery(cls, nhentai_ID: int, cookies: dict[str, str], headers: dict[str, str]) -> dict:
        """
        Tries to load nhentai API gallery from class variable first, if unsuccessful from file, if unsuccesful again downloads from nhentai API.

        Arguments:
        - nhentai_ID: the hentai from nhentai.net found here: https://nhentai.net/g/{hentai_ID}
        - cookies: cookies to send with the request to bypass bot protection
        - headers: user agent to send with the request to bypass bot protection

        Returns:
        - gallery: gallery from nhentai API

        Raises:
        - requests.HTTPError: Downloading gallery from \"{NHENTAI_GALLERY_API_URL}/{self.ID}\" failed multiple times.
        - ValueError: Hentai with ID \"{self.ID}\" does not exist.
        """

        gallery: dict                                                   # gallery to return
        GALLERY_FILEPATH: str="./config/galleries.json"
        gallery_page: requests.Response
        NHENTAI_GALLERY_API_URL: str="https://nhentai.net/api/gallery"  # URL to nhentai API


        logging.info(f"Loading gallery {nhentai_ID}...")
        if len(cls.galleries) > 0:                                                                    # if class variable initialised: try to load from class variable
            gallery=next((gallery for gallery in cls.galleries if gallery["id"]==nhentai_ID), {})   # try to find gallery with same ID
            if gallery!={}:                                                                         # if gallery found: return
                logging.info(f"\rLoaded gallery {nhentai_ID}.")
                return gallery

        if os.path.isfile(GALLERY_FILEPATH)==True:                                                  # if galleries file exists: try to load from file
            with open(GALLERY_FILEPATH, "rt") as galleries_file:
                try:
                    cls.galleries=json.loads(galleries_file.read())                                 # load already downloaded galleries, overwrite class variable
                except ValueError as e:                                                             # if file is corrupted:
                    logging.critical(f"Parsing galleries from \"{GALLERY_FILEPATH}\" failed with {KFSfstr.full_class_name(e)}. Check your \"{GALLERY_FILEPATH}\" for errors.")
                    raise RuntimeError(f"Error in {Hentai._get_gallery.__name__}{inspect.signature(Hentai._get_gallery)}: Parsing galleries from \"{GALLERY_FILEPATH}\" failed with {KFSfstr.full_class_name(e)}. Check your \"{GALLERY_FILEPATH}\" for errors.") from e
            gallery=next((gallery for gallery in cls.galleries if str(gallery["id"])==str(nhentai_ID)), {}) # try to find gallery with same ID
            if gallery!={}:                                                                                 # if gallery found: return
                logging.info(f"\rLoaded gallery {nhentai_ID} from \"{GALLERY_FILEPATH}\".")
                return gallery


        attempt_no: int=1
        while True:
            try:
                gallery_page=requests.get(f"{NHENTAI_GALLERY_API_URL}/{nhentai_ID}", cookies=cookies, headers=headers, timeout=10)
            except (requests.exceptions.ConnectionError, requests.Timeout): # if connection error: try again
                time.sleep(1)
                if attempt_no<3:                                            # try 3 times
                    continue
                else:                                                       # if failed 3 times: give up
                    raise
            if gallery_page.status_code==403:                               # if status code 403 (forbidden): probably cookies and headers not set correctly
                logging.critical(f"Downloading gallery {nhentai_ID} from \"{NHENTAI_GALLERY_API_URL}/{nhentai_ID}\" resulted in status code {gallery_page.status_code}. Have you set \"cookies.json\" and \"headers.json\" correctly?")
                raise requests.HTTPError(f"Error in {Hentai._get_gallery.__name__}{inspect.signature(Hentai._get_gallery)}: Downloading gallery {nhentai_ID} from \"{NHENTAI_GALLERY_API_URL}/{nhentai_ID}\" resulted in status code {gallery_page.status_code}. Have you set \"cookies.json\" and \"headers.json\" correctly?", response=gallery_page)
            if gallery_page.status_code==404:                               # if status code 404 (not found): hentai does not exist (anymore?)
                logging.error(f"Hentai with ID \"{nhentai_ID}\" does not exist.")
                raise ValueError(f"Error in {Hentai._get_gallery.__name__}{inspect.signature(Hentai._get_gallery)}: Hentai with ID \"{nhentai_ID}\" does not exist.")
            if not gallery_page.ok:                                      # if status code not ok: try again
                time.sleep(1)
                if attempt_no<3:                                            # try 3 times
                    continue
                else:                                                       # if failed 3 times: give up
                    raise

            gallery=json.loads(gallery_page.text)
            if str(gallery["id"]) in [str(gallery["id"]) for gallery in cls.galleries]: # if gallery already downloaded but adding to class variable requested: something went wrong
                logging.critical(f"Gallery {nhentai_ID} has been requested to be added to galleries even though it would result in a duplicate entry.")
                raise RuntimeError(f"Error in {Hentai._get_gallery.__name__}{inspect.signature(Hentai._get_gallery)}: Gallery {nhentai_ID} has been requested to be added to galleries even though it would result in a duplicate entry.")
            cls.galleries.append(gallery)
            break
        logging.info(f"\rDownloaded gallery {nhentai_ID} from \"{NHENTAI_GALLERY_API_URL}/{nhentai_ID}\".")

        cls.galleries=sorted(cls.galleries, key=lambda gallery: int(gallery["id"])) # sort galleries by ID
        logging.info(f"Saving galleries in \"{GALLERY_FILEPATH}\"...")
        with open(GALLERY_FILEPATH, "wt") as galleries_file:
            galleries_file.write(json.dumps(cls.galleries, indent=4))               # write galleries to file
        logging.info(f"\rSaved galleries in \"{GALLERY_FILEPATH}\".")

        return gallery
    

    def _increment_fails(self, image_list: list[str]) -> None:
        """
        Takes list of filepaths that could not be downloaded or converted and increments appropiate failure counter.
        """

        PATTERNS: list[str]=[
            r"^((?P<page_no>[0-9]+)\.[a-z]+)$",         # page URL pattern
            r"^([0-9]+-(?P<page_no>[0-9]+)\.[a-z]+)$",  # image filepath pattern
        ]
        re_match: re.Match|None


        for image in image_list:                                                    # for each image:
            for pattern in PATTERNS:                                            # with each pattern:
                re_match=re.search(pattern, image.split("/")[-1])                       # try to parse page number, use only filename not path
                if re_match!=None:                                          # if page number could be parsed:
                    self._fails[int(re_match.groupdict()["page_no"])-1]+=1              # increment appropiate fails counter
                    if self._fails[int(re_match.groupdict()["page_no"]) - 1] >= 10:         # if any counter 10 or above:
                        self._give_up=True                                              # give hentai up
                    break
            else:                                                                       # if page number can't be parsed:
                logging.critical(f"Incrementing fails counter of \"{image}\" failed.")  # don't know which counter to increment, critical error because should not happen
                raise RuntimeError(f"Error in {self._increment_fails.__name__}{inspect.signature(self._increment_fails)}: Incrementing fails counter of \"{image}\" failed.")

        return
    

    def download(self, dest_path: str) -> bytes:
        """
        Downloads the hentai, saves it at f"./{DEST_PATH}{self.ID} {self.title}.pdf", and also returns it in case needed.

        Returns:
        - PDF: finished PDF

        Raises:
        - FileExistsError: File \"{PDF_filepath}\" already exists.
        - Hentai.DownloadError:
            - \"{PDF_filepath}\" already exists as directory.
            - Can't generate page URL for {self} page {i+1}, because media type \"{page['t']}\" is unknown.
            - Tried to download and convert hentai \"{self}\" several times, but failed.
        """

        images_filepath: list[str]=[]                       # where to cache downloaded images
        MEDIA_TYPES: dict[str, str]={                       # parsed image type to file extension
            "g": ".gif",
            "j": ".jpg",
            "p": ".png",
        }
        pages_URL: list[str]=[]                             # URL to individual pages to download
        PDF: bytes                                          # finished PDF
        PDF_filepath: str                                   # where to save downloaded result, ID title pdf, but title maximum 140 characters and without illegal filename characters
        TIMEOUT=100                                         # timeout for downloading images
        TITLE_CHARACTERS_FORBIDDEN: str="\\/:*?\"<>|\t\n"   # in title forbidden characters


        for i, page in enumerate(self._gallery["images"]["pages"]):
            if page["t"] not in MEDIA_TYPES.keys(): # if media type unknown:
                logging.error(f"Can't generate page URL for {self} page {i+1}, because media type \"{page['t']}\" is unknown.")
                raise KFSmedia.DownloadError(f"Error in {self.download.__name__}{inspect.signature(self.download)}: Can't generate page URL for {self} page {i+1}, because media type \"{page['t']}\" is unknown.")

            pages_URL.append(f"https://i{random.choice(['', '2', '3', '5', '7'])}.nhentai.net/galleries/{self._gallery['media_id']}/{i+1}{MEDIA_TYPES[page['t']]}") # URL, use random image server instance to distribute load
            images_filepath.append(f"{dest_path}{self.ID}/{self.ID}-{i+1}{MEDIA_TYPES[page['t']]}")                                                                 # media filepath, but usually image filepath

        PDF_filepath=self.title
        for c in TITLE_CHARACTERS_FORBIDDEN:                                                    # remove forbidden characters for filenames
            PDF_filepath=PDF_filepath.replace(c, "")
        PDF_filepath=PDF_filepath[:140]                                                         # limit title length to 140 characters
        PDF_filepath=f"{dest_path}{self.ID} {PDF_filepath}.pdf"
        if os.path.isfile(PDF_filepath)==True:                                                  # if PDF already exists: skip download
            logging.info(f"File \"{PDF_filepath}\" already exists. Skipped download.")
            self.PDF_filepath=PDF_filepath                                                      # save PDF filepath
            raise FileExistsError(f"File \"{PDF_filepath}\" already exists. Skipped download.") # raise exception to skip upload in main
        if os.path.isdir(PDF_filepath)==True:                                                   # if PDF already exists as directory: skip download, append to failures
            logging.error(f"\"{PDF_filepath}\" already exists as directory. Skipped download.")
            raise KFSmedia.DownloadError(f"Error in {self.download.__name__}{inspect.signature(self.download)}: \"{PDF_filepath}\" already exists as directory. Skipped download.")


        while self._give_up==False:                                                     # while not giving up: try to download and convert
            try:
                KFSmedia.download_medias(pages_URL, images_filepath, timeout=TIMEOUT)   # download images # type:ignore
            except KFSmedia.DownloadError as e:
                self._increment_fails(e.args[0])                                        # increment fails, may trigger giving up
                continue
                
            try:
                PDF=KFSmedia.convert_images_to_PDF(images_filepath, PDF_filepath)   # convert images to PDF
            except KFSmedia.ConversionError as e:
                self._increment_fails(e.args[0])                                    # increment fails, may trigger giving up
                continue
            else:                                                                   # if conversion successful:
                self.PDF_filepath=PDF_filepath                                      # save PDF filepath
                break                                                               # break out
        else:                                                                       # if giving up:
            logging.error(f"Tried to download and convert hentai \"{self}\" several times, but failed. Giving up.")
            raise KFSmedia.DownloadError(f"Error in {self.download.__name__}{inspect.signature(self.download)}: Tried to download and convert hentai \"{self}\" several times, but failed. Giving up.")

    
        if os.path.isdir(f"{dest_path}{self.ID}") and len(os.listdir(f"{dest_path}{self.ID}"))==0:  # if cache folder still exists and is empty:
            try:
                os.rmdir(f"{dest_path}{self.ID}")                                                   # try to clean up
            except PermissionError:                                                                 # may fail if another process is still using directory like dropbox
                pass                                                                                # don't warn because will be retried in main

        return PDF