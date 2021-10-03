"""Module to fetch and graph adoption of Python releases.
"""

import calendar
import sqlite3
import sys
from datetime import datetime, timedelta, date
from collections import defaultdict

from pypinfo.fields import PythonVersion
from pypinfo.core import build_query, create_client, create_config, parse_query_result
from pypinfo.db import get_credentials
import matplotlib.pyplot as plt


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
    for year_in_the_past in 1, 0:
        year = today.year - year_in_the_past
        for month in range(1, 13):
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


def plot_main():
    db = DB()
    by_version = defaultdict(dict)
    for row in db.fetch_python_version():
        by_version[row["python_version"]][row["start_date"]] = row["download_count"]
    for version, data_points in by_version.items():
        plt.plot(data_points.keys(), data_points.values(), label=version)
    plt.xlabel("month")
    plt.ylabel("pypi downloads")
    plt.legend()
    plt.savefig("python-versions.png")


if __name__ == "__main__":
    if "--fetch" in sys.argv:
        fetch_main()
    plot_main()