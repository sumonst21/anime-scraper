import re
import os
import json
import sys

import cfscrape
import demjson
import jsbeautifier

from bs4 import BeautifulSoup as bs

WATCHANIME = "watchanime.me"
ANIMELAND = "animeland.tv"


def identify_website(url):
    watchanime = re.compile(r"^(http:\/\/|https:\/\/)*([a-z0-9][a-z0-9\-]*\.)*(watchanime)\.me(\/.*)?$")
    animeland = re.compile(r"^(http:\/\/|https:\/\/)*([a-z0-9][a-z0-9\-]*\.)*(animeland)\.tv(\/.*)?$")

    if watchanime.match(url):
        return WATCHANIME

    if animeland.match(url):
        return ANIMELAND

    return False


def _get_webpages(episodes_dict, start, end):
    webpages = []

    if start > 0 and end > 0:
        for i in range(start, end + 1):
            try:
                webpages.append(episodes_dict["Episode " + str(i)])
            except:
                print("No Episode " + str(i))
    else:
        keys = list(episodes_dict.keys())

        if re.match(r"^Episode \d+$", keys[0]):
            keys.sort(key = lambda episode: episode.split()[1])

        for episode in keys:
            webpages.append(episodes_dict[episode])

    return webpages


def _is_episode_missing(ep):
    if ep not in [os.path.splitext(f)[0] for f in os.listdir()]:
        return True
    return False


def _scrape_episodes(url, start, end, find_missing):
    if not (url[:7] == "http://" or url[:8] == "https://"):
        url = "http://" + url

    page_url = url
    START_EPISODE = start
    END_EPISODE = end
    episodes_dict = {}
    repisodes_dict = {}
    webpages = []
    failed_episodes = []
    hash_map = {}

    scraper = cfscrape.create_scraper()

    if identify_website(url) == ANIMELAND:
        # Animeland
        QUALITY = ["360p", "720p"][1]   # Select quality
        website_base_url = "http://www.animeland.tv/"
        source = scraper.get(page_url).content
        soup = bs(source, "html.parser")

        # Fetch the list of episodes
        for script in soup.find_all("script"):
            match = re.search(r'\$\("#load"\)\.load\(\'(.+)\'\)', str(script))
            if match:
                soup = bs(scraper.get(website_base_url + match.group(1)[1:]).content, "html.parser")
                for a in soup.find_all("a", {"class": "play"}):
                    ep = a.getText()
                    if find_missing:
                        if _is_episode_missing(ep):
                            episodes_dict[ep] = website_base_url + a["href"][1:]
                        continue
                    episodes_dict[ep] = website_base_url + a["href"][1:]

        webpages = _get_webpages(episodes_dict, START_EPISODE, END_EPISODE)

        # Reverse episodes_dict
        for key in episodes_dict.keys():
            repisodes_dict[episodes_dict[key]] = key

        downloads = []

        for url in webpages:
            episode = repisodes_dict[url]
            try:
                source = scraper.get(url).content
                soup = bs(source, "html.parser")
                iframe = soup.find("iframe", {"id": "video"})
                vid_url = iframe["src"]
                if vid_url[0] == "/":
                    vid_url = website_base_url + vid_url[1:]
                iframe_response = scraper.get(vid_url)
                iframe_source = iframe_response.content
                iframe_soup = bs(iframe_source, "html.parser")
                failed = False
                # The website has 3 kinds of DOM structures for their videos
                try:
                    # Method 1
                    video = iframe_soup.find("video", {"id": "my-video"})
                    sources = video.find_all("source")
                    method = 1
                except:
                    try:
                        # Method 2
                        parent_div = iframe_soup.find("div", {"id": "videop"})
                        script = str(parent_div.script).replace("\n", "")
                        json_string = "{" + re.search(r"\bsources:.*\]", script).group(0) + "}"
                        sources = demjson.decode(json_string)
                        sources = sources["sources"]
                        method = 2
                    except:
                        try:
                            # Method 3
                            sources = [{"file": iframe_soup.find("div", {"id": "vid"}).source["src"], "label": QUALITY}]  # Sorry for lying :(
                            method = 3
                        except:
                            #print(sys.exc_info())
                            print("Failed to get " + episode)
                            failed = True
                if not failed:
                    for src in sources:
                        if src["label"] == QUALITY:
                            if method == 1:
                                download_url = src["src"]
                            elif method == 2:
                                download_url = src["file"]
                            else:
                                download_url = src["file"]
                            downloads.append(download_url)
                            print(episode + ":", download_url, end="\n\n")
                            hash_map[download_url] = episode
            except:
                #print(sys.exc_info())
                failed = True

            if failed:
                failed_episodes.append(episode)
    else:
        # Watchanime
        QUALITIES = ["360", "480", "720"]
        QUALITY = QUALITIES[1]  # Select preferred quality
        website_base_url = "http://watchanime.me/"
        sp = bs(scraper.get(page_url).content, "html.parser")
        eps_div = sp.find("div", {"id": "episodes_1-0"})

        for a in eps_div.find_all("a"):
            #print(a.getText())
            ep = "Episode " + re.search(r"Ep\. (\d+(\.\d+)?) \[.+\]", a.getText()).group(1)
            if find_missing:
                if _is_episode_missing(ep):
                    episodes_dict[ep] = a["href"].strip()
                continue
            episodes_dict[ep] = a["href"].strip()

        webpages = _get_webpages(episodes_dict, START_EPISODE, END_EPISODE)

        # Reverse episodes_dict
        for key in episodes_dict.keys():
            repisodes_dict[episodes_dict[key]] = key

        downloads = []
        for url in webpages:
            try:
                episode = repisodes_dict[url]
                source = scraper.get(url).content
                soup = bs(source, "html.parser")

                mp4up_iframe = soup.find("p", {"id": "alternative_2"}).iframe
                mp4up_iframe_source = scraper.get(mp4up_iframe["src"]).content
                mp4up_soup = bs(mp4up_iframe_source, "html.parser")
                mp4up_js = jsbeautifier.beautify(mp4up_soup.body.find("script", {"type": "text/javascript"}).text)
                with open("js.txt", "w") as f:
                    f.write(mp4up_js)

                download_url = re.search(r'src:"(.+\.mp4")', mp4up_js).group(1).replace('"', "")

                if download_url:
                    print(episode + ": " + download_url, end="\n\n")
                    downloads.append(download_url)
                    hash_map[download_url] = episode
            except:
                failed_episodes.append(episode)
                print("Failed to get", episode)

    return hash_map, failed_episodes

def get_episodes_dictionary(url, start=0, end=0, find_missing=False):
    """
    Returns a dictionary with episode download URLs mapped to their named and a list of episodes that couldn't be fetched.
        start: Episode to start fetching from
        end: Episode to stop fetching at
    """
    if start < 0 or end < 0:
        raise Exception("Invalid argument(s) for start and/or end")
    if identify_website(url):
        return _scrape_episodes(url, start, end, find_missing)
    else:
        raise Exception("Given URL not supported")
