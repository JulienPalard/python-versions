"""Module to fetch and graph adoption of Python releases.
"""

import calendar
import sqlite3
import sys
from datetime import datetime, timedelta, date
from collections import defaultdict
from itertools import cycle, count

import pandas as pd
from pypinfo.fields import PythonVersion
from pypinfo.core import build_query, create_client, create_config, parse_query_result
from pypinfo.db import get_credentials
import matplotlib.pyplot as plt
from matplotlib.dates import date2num
from scipy.interpolate import make_interp_spline
import numpy as np


class DB:
    def __init__(self):
        self.connection = sqlite3.connect(
            "python-versions.sqlite",
            isolation_level=None,
            detect_types=sqlite3.PARSE_COLNAMES,
        )
        self.connection.row_factory = sqlite3.Row
        self.migrate()

    def migrate(self):
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS python_version (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "start_date" TEXT NOT NULL,
    "end_date" TEXT NOT NULL,
    "python_version" TEXT NULL,
    "download_count" INT NOT NULL);"""
        )

    def store_python_version(
        self, start_date, end_date, python_version, download_count
    ):
        self.connection.execute(
            "INSERT INTO python_version (start_date, end_date, python_version, download_count) VALUES (?, ?, ?, ?)",
            (start_date, end_date, python_version, download_count),
        )

    def have_data_for_dates(self, start_date, end_date) -> bool:
        return (
            self.connection.execute(
                "SELECT COUNT(1) FROM python_version WHERE start_date = ? AND end_date = ?",
                (start_date, end_date),
            ).fetchone()[0]
            > 0
        )

    def fetch_python_version(self):
        return self.connection.execute(
            """
  SELECT start_date as "start_date [date]",
         end_date as "end_date [date]",
         python_version,
         download_count
    FROM python_version
ORDER BY start_date"""
        ).fetchall()


def query_python_versions(start_date: str, end_date: str) -> list[tuple[str, int]]:
    built_query = build_query(
        "",
        [PythonVersion],
        start_date=start_date,
        end_date=end_date,
    )

    with create_client(get_credentials()) as client:
        query_job = client.query(built_query, job_config=create_config())
        query_rows = query_job.result(timeout=120)
        return [tuple(row) for row in query_rows]


def fetch_main():
    db = DB()
    today = date.today()
    for year_in_the_past in count():
        if year_in_the_past < 2017:
            # There's no data before 2017.
            return
        year = today.year - year_in_the_past
        for month in reversed(range(1, 13)):
            start_date = date(year, month, 1)
            end_date = start_date.replace(
                day=calendar.monthrange(year, month)[1]
            ) + timedelta(days=1)
            if end_date > today:
                continue
            if db.have_data_for_dates(start_date, end_date):
                continue
            print(f"Querying BigTable in [{start_date}; {end_date}]")
            results = query_python_versions(str(start_date), str(end_date))
            for python_version, download_count in results:
                db.store_python_version(
                    start_date, end_date, python_version, download_count
                )


def mean_date(a: datetime, b: datetime) -> datetime:
    return a + (b - a) / 2


def plot_main():
    db = DB()
    by_version = defaultdict(lambda: [[], []])
    versions = db.fetch_python_version()
    biggest_value = max(version["download_count"] for version in versions)
    for row in versions:
        if row["download_count"] > biggest_value / 20:
            by_version[row["python_version"]][0].append(
                mean_date(row["start_date"], row["end_date"])
            )
            by_version[row["python_version"]][1].append(row["download_count"])
    plt.style.use("tableau-colorblind10")
    plt.figure(figsize=(10, 10 * 2 / 3))
    fmt = iter(cycle(["-", "--", ":", "-."]))
    for version, (x, y) in by_version.items():
        if version is None:
            continue
        if len(x) <= 2:
            plt.plot(x, y, label=version)
            continue
        smooth_x = np.linspace(date2num(min(x)), date2num(max(x)), 200)
        spline = make_interp_spline([date2num(d) for d in x], y, k=2)
        smooth_y = spline(smooth_x)
        plt.plot_date(smooth_x, smooth_y, label=version, fmt=next(fmt))
    plt.xlabel("Date")
    plt.ylabel("PyPI downloads")
    plt.legend()
    plt.savefig("python-versions.png")


HIDE = {"1.17", "2.4", "2.5", "2.6", "3.2", "3.3", "3.4"}


def plot_pct():
    def by_version(version_string):
        try:
            minor, major = version_string.split(".")
            return float(minor), float(major)
        except ValueError:
            return 0, 0

    def by_versions(version_strings):
        return version_strings.map(by_version)

    db = DB()
    versions = pd.DataFrame(
        db.fetch_python_version(),
        columns=["start_date", "end_date", "python_version", "download_count"],
        dtype="str",
    )
    versions["download_count"] = pd.to_numeric(versions["download_count"])
    versions["python_version"].fillna("Other", inplace=True)
    versions = versions.merge(
        versions.groupby("start_date").agg(monthly_downloads=("download_count", "sum")),
        on="start_date",
    )
    versions["pct"] = 100 * versions.download_count / versions.monthly_downloads
    versions["date"] = pd.to_datetime(versions.start_date) + timedelta(days=14)
    versions.set_index(["python_version", "date"], inplace=True)
    to_plot = versions.pct.unstack(0, fill_value=0)
    to_plot.sort_values(by="python_version", axis=1, inplace=True, key=by_versions)
    for version in to_plot:
        if version in HIDE:
            to_plot["Other"] += to_plot[version]
            del to_plot[version]
    plt.style.use("tableau-colorblind10")
    to_plot.plot.area(stacked=True, figsize=(10, 10 * 2 / 3))
    plt.savefig("python-versions-pct.png")


if __name__ == "__main__":
    if "--fetch" in sys.argv:
        fetch_main()
    plot_pct()
    plot_main()
