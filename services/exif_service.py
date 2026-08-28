import json
import subprocess
from pathlib import Path

from utils.logger import get_logger

logger = get_logger("exif_service")


def sanitize_keywords(keywords) -> list[str]:
    if isinstance(keywords, str):
        raw = [item.strip() for item in keywords.split(",")]
    elif isinstance(keywords, (list, tuple, set)):
        raw = [str(item).strip() for item in keywords]
    else:
        raw = []

    cleaned = []
    for item in raw:
        value = " ".join(item.lower().split())
        if value:
            cleaned.append(value)
    unique = list(dict.fromkeys(cleaned))
    return unique[:50]


class ExifService:
    @staticmethod
    def read_keyword_fields(image_path: Path) -> dict:
        result = subprocess.run(
            [
                "exiftool", "-j", "-struct", "-XMP:Subject",
                "-IPTC:Keywords", "-EXIF:XPKeywords", str(image_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)[0]
        return {
            "iptc": data.get("Keywords") or [],
            "xmp": data.get("Subject") or [],
            "exif": data.get("XPKeywords") or [],
        }

    @staticmethod
    def write_metadata(image_path: Path, title: str, description: str, keywords: str, adobe_cat: str = "") -> bool:
        if not image_path.exists():
            logger.error(f"Image path does not exist for EXIF writing: {image_path}")
            return False

        keyword_list = sanitize_keywords(keywords)
        safe_title = (title or "").strip()
        safe_description = (description or title or "").strip()

        clear_cmd = [
            "exiftool",
            "-overwrite_original",
            "-P",
            "-XMP:Subject=",
            "-IPTC:Keywords=",
            "-EXIF:XPKeywords=",
            str(image_path),
        ]
        cmd = [
            "exiftool",
            "-overwrite_original",
            "-P",
            f"-XMP:Title={safe_title}",
            f"-XMP:Description={safe_description}",
        ]
        for keyword in keyword_list:
            cmd.append(f"-IPTC:Keywords+={keyword}")
        if adobe_cat:
            full_cat = adobe_cat.strip()
            cmd.extend([
                f"-XMP-photoshop:Category={full_cat}",
                f"-IPTC:SupplementalCategories={full_cat}",
            ])
        cmd.append(str(image_path))

        try:
            logger.info(f"Writing IPTC/XMP metadata to {image_path.name}")
            subprocess.run(
                clear_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            fields = ExifService.read_keyword_fields(image_path)
            iptc_keywords = fields["iptc"] if isinstance(fields["iptc"], list) else [fields["iptc"]]
            if iptc_keywords != keyword_list or fields["xmp"] or fields["exif"]:
                logger.error(
                    "Keyword verification failed for %s: IPTC=%s XMP=%s EXIF=%s",
                    image_path.name,
                    len(iptc_keywords),
                    fields["xmp"],
                    fields["exif"],
                )
                return False
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"ExifTool failed for {image_path.name}: {e.stderr}")
            return False
        except FileNotFoundError:
            logger.error("ExifTool is not installed or not found in system PATH.")
            return False
        except Exception as e:
            logger.error(f"Unexpected error writing IPTC/XMP for {image_path.name}: {e}")
            return False


exif_service = ExifService()
