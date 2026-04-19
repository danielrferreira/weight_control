#!/usr/bin/env python3
"""Delete a single date's entry from the weight tracker CSV on Google Drive."""
import argparse
import io
import sys
import tomllib
from pathlib import Path

import pandas as pd
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

FILE_ID = "1P3JHnDkMMWf_xeGBaTHdEcAoYzTMIvU4"
SECRETS_PATH = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"


def get_drive_service():
    with open(SECRETS_PATH, "rb") as f:
        secrets = tomllib.load(f)
    creds = Credentials.from_service_account_info(
        secrets["google_drive"],
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    return build("drive", "v3", credentials=creds)


def download_csv(service) -> pd.DataFrame:
    request = service.files().get_media(fileId=FILE_ID)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    fh.seek(0)
    return pd.read_csv(fh)


def upload_csv(service, df: pd.DataFrame) -> None:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    media = MediaIoBaseUpload(io.BytesIO(buf.getvalue().encode()), mimetype="text/csv")
    service.files().update(fileId=FILE_ID, media_body=media).execute()


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete a single date from the weight CSV on Drive.")
    parser.add_argument("date", help="Date to delete, YYYY-MM-DD")
    args = parser.parse_args()

    try:
        target = pd.to_datetime(args.date).date()
    except Exception:
        print(f"Invalid date '{args.date}'. Use YYYY-MM-DD.", file=sys.stderr)
        return 2

    service = get_drive_service()
    df = download_csv(service)
    df["date"] = pd.to_datetime(df["date"]).dt.date

    match = df[df["date"] == target]
    if match.empty:
        print(f"No entry for {target}. Nothing to delete.")
        return 1

    print(f"Entry for {target}:")
    print(match.to_string(index=False))
    reply = input("\nDelete this entry? [y/N] ").strip().lower()
    if reply != "y":
        print("Cancelled.")
        return 0

    new_df = df[df["date"] != target]
    upload_csv(service, new_df)
    print(f"Deleted entry for {target}. ({len(df)} \u2192 {len(new_df)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
