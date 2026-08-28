from __future__ import annotations

import csv
import os

from services.exif_service import sanitize_keywords


def generate_shutterstock_csv(
    items_data: list[dict],
    output_path: str = "shutterstock_upload.csv",
) -> str:
    """Generate a Shutterstock companion CSV for a batch of uploaded files."""
    fieldnames = [
        "Filename",
        "Description",
        "Keywords",
        "Categories",
        "Editorial",
        "Mature content",
        "illustration",
    ]

    with open(output_path, mode="w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()

        for item in items_data:
            keywords = sanitize_keywords(item.get("keywords", []))

            categories = item.get("categories", [])
            if isinstance(categories, str):
                categories = categories.split(",")
            categories = [
                str(category).strip()
                for category in categories
                if str(category).strip()
            ][:2]

            writer.writerow({
                "Filename": os.path.basename(str(item.get("filename", ""))),
                "Description": item.get("description", ""),
                "Keywords": ", ".join(keywords),
                "Categories": ",".join(categories),
                "Editorial": "no",
                "Mature content": "no",
                "illustration": "no",
            })

    return output_path
