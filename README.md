# woy - Wasted On Youtube

[![License](https://img.shields.io/pypi/l/woy.svg?color=green)](https://github.com/brisvag/woy/raw/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/woy.svg?color=green)](https://pypi.org/project/woy)
[![Python Version](https://img.shields.io/pypi/pyversions/woy.svg?color=green)](https://python.org)

[![asciicast](https://asciinema.org/a/A8QR33m8LjbkkrD20a6c1ox8B.svg)](https://asciinema.org/a/A8QR33m8LjbkkrD20a6c1ox8B)

Wanna know how badly addicted you are to youtube? Woy will tell you how much of your time you wasted watching videos, with several stats (and plots!) about channels, tags, weekly watchtime, and so on.

It works by scraping your youtube watch history (obtained with [Google Takeout](https://takeout.google.com/)) and complementing with extra info about the videos (obtained with the [Youtube API](https://developers.google.com/youtube/v3)).

## Setup

First, ask google for your data: click on your avatar on the top right of youtube, then `Your data in Youtube`, then `More` under `Your Youtube dashboard`, and finally `Download Youtube Data`. In the next page, make sure to click on "multiple formats" and change the "history" dropdown from HTML to JSON. Do whatever you prefer for the next steps, and you should soon receive your data via the chosen method. The history file will be located at `Takeout/YouTube and YouTube Music/history/watch-history.json` inside the extracted directory.

In order to use the youtube API you'll need your own API key (or alternative, ask for a friend's 😉). To do so, I recommend following [the official guide](https://developers.google.com/youtube/v3/getting-started) up to point `3.`; you can skip setting up OAuth authentication, as it won't be needed.

Once you have your Takeout and your API key, you're ready to go! Install woy with pip (or your preferred method, I suggest [uv](https://docs.astral.sh/uv/)):

```
pip install woy
```

## Usage

To scrape your history and download the additional info, run (this is only needed once!):

```
woy fetch <PATH_TO_TAKEOUT_HISTORY_JSON> <API_KEY>
```

> [!WARNING]
> By default your API will have a quota of 10k requests per day. This should be plenty for this purpose, as woy tries to be smart about it and batch requests, but you won't be able to use the same API key many times in the same day. That should be ok though, since you only need to do this once! Anyway, you'll get a confirmation prompt telling you how much api quota this run will use.

This will create a file called `youtube_watch_history.csv` in the current directory with all the history data. Feel free to peruse it and a analyse it however you like!

To generate a summary, prepare to cringe and run:
```
woy process
```

> [!TIP]
> Video titles and channel names are clickable links!

There are many options! Run `woy process -h` to see all the available options to customize the summary.

For example, to include only the data starting from 2020, and exclude videos categorized as "Music", run:

```
woy process --exclude-categories "Music" -f 2020-01-01
```

## Caveats

Youtube Takeout unfortunately does not include playback information, such as exact minutes watched and playback speed. This means that every time a video is watched "a bit", it's counted as a full watch. As a result, watch times are always overestimated, resulting for example in days where the watchtime is longer than 24h. As far as I know, there's no way around it.

You can partly offset this by passing the `-a` (`--adjust-watch-time`) option, which will cut down the duration of a video if another video was started before it could have ended at a normal pace. So, if you started a 2 hour video at 12:00 and another one at 13:00, it will assume that only 1 hour was spent on the first video. Depending on your watching habits, this might cut down dramatically the watch time.
