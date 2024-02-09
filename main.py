import warnings
import musicbrainzngs
import argparse
import json

from pathlib import Path
from pprint import pprint as pprint
from rich.console import Console
from tqdm import tqdm

CONF_PATH = Path("./config")
DEFAULT_CONF = CONF_PATH.joinpath("coverart_default.json")
LIMIT = 100


def setup_api() -> None:
    """"""
    # initialize musicbrainz API
    """"""

    musicbrainzngs.set_useragent(app='coverart_download', version='0.666', contact='hshallucinations@gmail.com')
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        musicbrainzngs.set_format(fmt="json")
    musicbrainzngs.set_rate_limit(False)

    return


def load_config(conf) -> dict:
    console = Console()

    config_file = Path(conf)

    if config_file.exists():
        with open(config_file, 'r') as f:
            config = json.load(f)
            console.log(f'Loaded configuration from {config_file}')
    else:
        console.log("Something went wrong, check your config file paths")

    return config


def save_config(config, config_file):
    console = Console()
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
        console.log(f"Configuration file saved in {config_file}")

    return


def clean_name(name: str) -> str:
    bad_chars = '!"£$%&/()=?^,;:><\\\/*-'
    for c in bad_chars:
        name = str(name).replace(c, '')
    name = name.replace(' ', '_')

    return name


def i_want_to_dl_this(release, types) -> bool:
    dl_this = False
    p_type_exists = False
    s_type_exists = False
    s_type = False
    p_type = False

    if "artist-credit" in release:
        artist = True
    else:
        artist = False

    if "primary-type" in release:  # if there's a primary-type filed:
        p_type_exists = True
        if release["primary-type"] in types:  # if primary-type is one i want
            p_type = True

    if "secondary-types" in release:  # if the release has a secondary type field:
        s_type_exists = True
        for secondary_type in release["secondary-types"]:
            if secondary_type in types:  # check if every secondary type is one i want
                s_type = True
                break  # exit loop

    if s_type_exists and s_type:
        dl_this = True
    elif not s_type_exists and p_type:
        dl_this = True
    # else:


    return dl_this


def get_releases(config: dict) -> list:

    console = Console()

    # copy config dict in single variables for QOL reasons
    start = config['last_release']
    stop = start + config["max_releases"]
    release_types = config["release_types"]
    tag = config["tag"]
    dataset_path = config["dataset_path"]
    query = f'tag:"{tag}"'

    # print total releases numbers for debug reasons
    releases = musicbrainzngs.search_release_groups(query=f'tag:"{tag}"')
    num_releases = releases["count"]
    console.log(f'{tag} returned {num_releases} releases. Fetching releases from {start} to {stop}')

    # request releases from MBrainz API 100 at a time and add to releases[] list
    releases = []
    with tqdm(total=config["max_releases"], desc="Fetching releases", ncols=100) as pbar:
        for _ in range(start, stop, LIMIT):
            rel_chunk = musicbrainzngs.search_release_groups(query=query, limit=LIMIT, offset=_)
            releases.extend(rel_chunk["release-groups"])
            pbar.update(LIMIT)

    return releases


def clean_releases_list(releases: list, types: list) -> list:
    clean_releases = []
    error = False
    rel_type = 'none'

    for rel in releases:
        clean_rel = dict()

        # check if release has an "artist-credits" item
        if "artist-credit" in rel:
            artist_credit = rel["artist-credit"]
            artist = str(artist_credit[0]["name"])
        else:
            artist = 'unlisted'

        title = rel['title']

        # if "primary-type" in rel:   # if there's a primary-type filed:
        #     if rel["primary-type"] in types:    # if primary-type is one i want
        #         s_type = 'not specified'
        #         if "secondary-types" in rel:    # if the release has a secondary type field:
        #             for secondary_type in rel["secondary-types"]:
        #                 if secondary_type in types:     # check if every secondary type is one i want
        #                     s_type = secondary_type
        #                     break   # exit loop
        #         rel_type = f'{rel["primary-type"]} - {s_type}'  # save release types for bool check
        #     else:
        #         rel_type = 'unlisted'
        # else:
        #     # rel_type = 'unlisted'
        #     pass

        if i_want_to_dl_this(rel, types):

            clean_rel['artist'] = clean_name(artist)
            # clean_rel['type'] = rel_type

            title = clean_name(title)
            clean_rel['title'] = title
            rel_list = []
            releases_list = rel["releases"]
            for rl in releases_list:
                rel_list.append(rl['id'])

            clean_rel['releases'] = rel_list
            tags = []
            for t in rel["tags"]:
                tags.append(t['name'])

            clean_rel['tags'] = tags

            clean_releases.append(clean_rel)
        else:
            print(f'{artist} - {title} : refused')

    return clean_releases


def save_releases_list(releases, clean=False):

    if clean:
        with open("releases_clean.json", "w") as f:
            json.dump(releases, f, indent=2)
    elif not clean:
        with open("releases.json", "w") as f:
            json.dump(releases, f, indent=2)

    return


def main():

    console = Console()

    console.print('CoverArtDownload v0.1')

    parser = argparse.ArgumentParser()
    parser.add_argument('mode', help='scrape, dl or reset')
    parser.add_argument('-t', '--tag', type=str, help='genre tag to search', default="death metal")
    parser.add_argument('--max', type=int, default=1000, help='max results to fetch')
    parser.add_argument("--resume", action="store_true", default=False, help="resume download from last release downloaded")
    parser.add_argument("--start", type=int, default=0, help="start download from release n.")
    args = parser.parse_args()

    mode = args.mode
    resume = args.resume

    if resume:
        config = resume()
    else:
        config = load_config(DEFAULT_CONF)
        dataset_folder = config["tag"].replace(" ", "_")
        config["dataset_path"] = f'{config["dl_main_folder"]}\\{dataset_folder}'
        config["max_releases"] = args.max
        config_file = CONF_PATH.joinpath(f'{dataset_folder}.json')
        save_config(config, config_file)
        with open(CONF_PATH.joinpath('resume.json'), 'w') as f:
            json.dump(str(config_file), f, indent=2)

    setup_api()

    pprint(config)

    if mode == 'scrape':
        console.print(f'Looking for releases tagged {config["tag"]}')
        releases = get_releases(config=config)
        save_releases_list(releases)
        clean_releases = clean_releases_list(releases, config['release_types'])
        print(f'clean release listr contains {len(clean_releases)} releases')
        save_releases_list(clean_releases, clean=True)
    elif mode == 'dl':
        console.print(f'Downloading releases tagged {config["tag"]}')
    else:
        console.log('Invalid mode selected, exiting')
        raise SystemExit

    return


if __name__ == '__main__':
    main()
