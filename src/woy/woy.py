#!/usr/bin/env python3

import csv
import json
import math
from pathlib import Path

import click


def get_video_categories(client, country):
    """Get mapping of category IDs to names in the given country from the youtube api."""
    request = client.videoCategories().list(
        part="snippet",
        hl="en",
        regionCode=country,
    )
    response = request.execute()
    return {it["id"]: it["snippet"]["title"] for it in response["items"]}


def get_video_data(client, video_ids):
    """Get metadata of a list of videos from the youtube api."""
    import pandas as pd
    from rich import print

    request = client.videos().list(
        part="contentDetails,snippet,statistics",
        id=",".join(video_ids),
    )
    response = request.execute()

    for it in response["items"]:
        vid = it["id"]
        try:
            duration = it["contentDetails"]["duration"]
            channel = it["snippet"]["channelTitle"]
            title = it["snippet"]["title"]
            category = it["snippet"]["categoryId"]
            views = it["statistics"].get("viewCount", pd.NA)
            tags = ",".join(it["snippet"].get("tags", []))
        except Exception:
            print(f"Something went wrong with video {vid}, skipping.")
            continue
        yield vid, duration, channel, title, category, views, tags


def get_id_chunks(ids):
    """Split a list of IDs in sublists of length 50 (max ids per request)."""
    chunks = []
    for i in range(math.ceil(len(ids) / 50)):
        chunks.append(ids[i * 50 : (i + 1) * 50])
    return chunks


def yt_link(id, text):
    """Clickable link in rich.print from video id and link text."""
    return f"[link=https://youtube.com/watch?v={id}]{text}[/link]"


@click.group(
    name="woy",
    context_settings={"help_option_names": ["-h", "--help"], "show_default": True},
)
def woy():
    """Wasted on youtube.

    First run fetch to download and prepare the data, then run process to summarize it.
    """
    pass


@woy.command()
@click.argument("takeout", type=click.Path(exists=True, resolve_path=True))
@click.argument("api-key", type=str)
@click.option(
    "-c",
    "--country-code",
    default="fr",
    help="country of residence to determine categories (they might differ between countries).",
)
def fetch(takeout, api_key, country_code):
    """Fetch the data from youtube.

    TAKEOUT: path to the takeout history json file (watch-history.json).
    API-KEY: api key obtained from youtube API v3.
    """
    import googleapiclient.discovery
    import pandas as pd
    from rich import print
    from rich.progress import track

    output = Path().resolve() / "youtube_watch_history.csv"
    with open(takeout) as f:
        history = json.load(f)

    ids = [watch["titleUrl"].partition("watch?v=")[2] if "titleUrl" in watch else pd.NA for watch in history]
    watched_on = [watch["time"] for watch in history]

    id_clean = pd.unique(pd.Series(ids)[pd.notna(ids)])
    id_chunks = get_id_chunks(id_clean)

    click.confirm(
        f"This will use up {len(id_chunks)} api quota. Continue and save the data to {output}?"
        "Don't (re)run unnecessarily!",
        abort=True,
    )

    df = pd.DataFrame(
        {"watched_on": watched_on},
        index=ids,
    )
    df.index.name = "id"
    df[["duration", "channel", "title", "category", "views", "tags"]] = pd.NA

    client = googleapiclient.discovery.build(serviceName="youtube", version="v3", developerKey=api_key)

    for ids in track(id_chunks, description="Fetching data...", disable=False):
        for vid, *columns in get_video_data(client, ids):
            df.loc[vid, ["duration", "channel", "title", "category", "views", "tags"]] = columns

    df.category = df.category.map(get_video_categories(client, country_code))

    df = df.reset_index()
    df.to_csv(output, sep="\t", quoting=csv.QUOTE_STRINGS, index=False)
    print(f"Data saved to {output}")
    print("Run `woy process` to get some stats!")


@woy.command()
@click.argument("history_csv", required=False, type=click.Path(exists=True, resolve_path=True))
@click.option("-r", "--include-rewatch", is_flag=True)
@click.option("-m", "--max-length-hours", default=5)
@click.option("-f", "--from-date", help="Use data from this date, included (YYYY-MM-DD).")
@click.option("-t", "--to-date", help="Use data up to this date, included (YYYY-MM-DD).")
@click.option(
    "--include-categories",
    help="Comma-separated list of categories. If given, include only these categories in the summary.",
)
@click.option(
    "--exclude-categories", help="Comma-separated list of categories. Exclude these categories from the summary."
)
@click.option("--include-tags", help="Comma-separated list of tags. If given, include only these tags in the summary.")
@click.option("--exclude-tags", help="Comma-separated list of tags. Exclude these tags from the summary.")
@click.option(
    "--include-channels", help="Comma-separated list of channels. If given, include only these channels in the summary."
)
@click.option("--exclude-channels", help="Comma-separated list of channels. Exclude these channels from the summary.")
def process(
    history_csv,
    include_rewatch,
    max_length_hours,
    from_date,
    to_date,
    include_categories,
    exclude_categories,
    include_tags,
    exclude_tags,
    include_channels,
    exclude_channels,
):
    """Process and summarize the data."""
    import numpy as np
    import pandas as pd
    import plotly.express as px
    from rich import print

    if history_csv is None:
        history_csv = Path().resolve() / "youtube_watch_history.csv"

    df = pd.read_csv(history_csv, sep="\t")
    df.watched_on = pd.to_datetime(df.watched_on, format="ISO8601")
    df.duration = pd.to_timedelta(df.duration)
    df.tags = df.tags.str.split(",")

    if from_date is not None:
        from_date = pd.Timestamp(from_date).date()
        df = df[df.watched_on.dt.date >= from_date]

    if to_date is not None:
        to_date = pd.Timestamp(to_date).date()
        df = df[df.watched_on.dt.date <= to_date]

    if include_categories is not None:
        df = df[df.category.isin(include_categories.split(","))]
    if exclude_categories is not None:
        df = df[~df.category.isin(exclude_categories.split(","))]

    if include_tags is not None:
        df = df[df.tags.apply(lambda x: np.any(pd.notna(x)) and any(xx in include_tags.split(",") for xx in x))]
    if exclude_tags is not None:
        df = df[~df.tags.apply(lambda x: np.any(pd.notna(x)) and any(xx in exclude_tags.split(",") for xx in x))]

    if include_channels is not None:
        df = df[df.channel.isin(include_channels.split(","))]
    if exclude_channels is not None:
        df = df[~df.channel.isin(exclude_channels.split(","))]

    raw_len = len(df)

    longest = df[["id", "title", "channel", "duration"]].sort_values("duration", ascending=False)

    valid_len = len(df)
    df = df[df.duration <= pd.Timedelta(f"PT{max_length_hours}H")]
    short_len = len(df)

    if not include_rewatch:
        df = df.drop_duplicates("id")

    n_videos = len(df.id.unique())
    first_time = df.watched_on.min()
    last_time = df.watched_on.max()
    tot_watch = df.duration.sum()
    percent_watch = tot_watch / (last_time - first_time)
    worst_weeks = (
        df.resample("W-MON", label="left", closed="left", on="watched_on").duration.sum().sort_values(ascending=False)
    )
    worst_days = df.resample("D", on="watched_on").duration.sum().sort_values(ascending=False)

    print(
        f"From {first_time.date()} to {last_time.date()} you watched {n_videos} youtube videos, "
        f"for a total duration of: {df.duration.sum()}."
    )

    print(f"This amounts to {percent_watch*100:.2f}% of your time, or {percent_watch*150:.2f}% of your time awake.")

    print(
        f"Your worst week started on {worst_weeks.index[0].date()}, "
        f"during which you watched for: {worst_weeks.iloc[0]}."
    )

    print(f"Your worst day was on {worst_days.index[0].date()}, when you watched for: {worst_days.iloc[0]}.")

    most_watched_channels = df.groupby(["channel"]).duration.sum().sort_values(ascending=False)
    print("Your most watched channels:")
    for ch, time in most_watched_channels.iloc[:10].items():
        print(f"  - {time}: [blue]{ch}[/blue]")

    category_time = df.groupby("category").duration.sum().sort_values(ascending=False)
    print("Your most watched categories were:")
    for cat, time in category_time.iloc[:10].items():
        print(f"  - {time}: [red]{cat}[/red]")

    unique, counts = np.unique(np.concatenate(df.tags.dropna().to_numpy()), return_counts=True)
    common_tags = sorted(zip(counts, unique), reverse=True)
    print("The most common tags:")
    for n, tag in common_tags[:10]:
        print(f"  - {n} times: {tag}")

    if include_rewatch:
        most_rewatched = df.groupby(["id", "title", "channel"]).size().sort_values(ascending=False)
        print("Your most rewatched videos:")
        for (vid, vid, chan), times in most_rewatched.iloc[:10].items():
            print(f"  - {times} times: [purple]{yt_link(vid, vid)}[/purple] by [blue]{chan}[/blue]")

    most_obscure = df[["id", "title", "channel", "views"]].sort_values("views", ascending=True)
    print("The most obscure videos you watched were:")
    for _, row in most_obscure.drop_duplicates("id").iloc[:10].iterrows():
        print(f"  - {row.views} views: [purple]{yt_link(row.id, row.title)}[/purple] by [blue]{row.channel}[/blue]")

    print(
        f"The longest videos you watched (excluded in other calculations if longer than {max_length_hours} hours) were:"
    )
    for _, row in longest.drop_duplicates("id").iloc[:10].iterrows():
        print(f"  - {row.duration}: [purple]{yt_link(row.id, row.title)}[/purple] by [blue]{row.channel}[/blue]")

    print(
        f"{raw_len - valid_len} videos from your history ({100 * (raw_len - valid_len) / raw_len:.2f})% "
        "could no longer be found."
    )
    print(
        f"{valid_len - short_len} videos from your history ({100 * (valid_len - short_len) / valid_len:.2f})% "
        "were excluded because too long."
    )

    df.duration = df.duration.dt.total_seconds() / 3600
    fig = px.histogram(df, x="watched_on", y="duration")
    fig.update_traces(xbins_size="M1")
    fig.update_layout(yaxis_title="hours watched")
    fig.show()


if __name__ == "__main__":
    woy()