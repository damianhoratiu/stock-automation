PLATFORMS = {
    "adobe": {"label": "Adobe Stock", "status_key": "ftp_adobe_done"},
    "shutterstock": {"label": "Shutterstock", "status_key": "ftp_shutter_done"},
}


def file_is_complete_for_platforms(meta: dict, platforms: set[str]) -> bool:
    return bool(meta.get("exif_done")) and all(
        meta.get(PLATFORMS[platform]["status_key"])
        for platform in platforms
    )
