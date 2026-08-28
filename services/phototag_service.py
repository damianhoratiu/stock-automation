from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests
import streamlit as st

import config
from services.trend_service import get_live_trends
from utils.logger import get_logger

logger = get_logger("phototag_service")
LIVE_TRENDS = get_live_trends()


def get_buyer_config(image_index: int) -> dict:
    configs = [
        {"role": "Advertising (Concepts, mood, psychological hooks, ad utility)", "temp": 0.85},
        {"role": "Editorial (Cultural heritage, authenticity, documentary)", "temp": 0.80},
        {"role": "Design/UX (Layout, color theory, textures, negative space)", "temp": 0.60},
        {"role": "Retail (Literal specs, macro details, material precision)", "temp": 0.35},
    ]
    return configs[int(image_index or 0) % 4]


def get_target_buyer(image_index: int) -> str:
    return get_buyer_config(image_index)["role"]


BUYER_PERSONAS = [
    get_target_buyer(0),
    get_target_buyer(1),
    get_target_buyer(2),
    get_target_buyer(3),
]
VIBES = BUYER_PERSONAS


def build_custom_context(image_index=0, custom_prompt=None, master_brief="") -> str:
    buyer = get_buyer_config(image_index)
    target_buyer = buyer["role"]
    brief = (master_brief or custom_prompt or "").strip()
    brief_text = brief if brief else "N/A (Rely purely on visual context)"
    return (
        f"ROLE: Elite Stock Art Director.\n"
        f"TARGET BUYER: {target_buyer}\n"
        f"MASTER BRIEF: {brief_text}\n\n"
        "CRITICAL DIRECTIVE: You MUST filter the visual analysis through the MASTER BRIEF and adapt it exclusively for the TARGET BUYER. Ignore generic captioning instincts.\n\n"
        "OUTPUT JSON SCHEMA RULES:\n"
        "1. \"persona_internal_monologue\": (String, max 2 sentences) Reason aloud how the MASTER BRIEF and visuals align with the TARGET BUYER'S needs. Write this first to anchor your context.\n"
        "2. \"title\": (String, EXACTLY 185-199 chars).\n"
        "   - [NEGATIVE CONSTRAINT]: If Advertising/Design, DO NOT list physical items. Describe the utility, mood, or geometry.\n"
        "   - [NEGATIVE CONSTRAINT]: If Retail, DO NOT use emotional metaphors. Focus strictly on literal details.\n"
        "3. \"keywords\": (String, exactly 50 comma-separated). ALL keywords MUST be SINGLE WORDS only. FORBIDDEN to use N-grams, multi-word phrases, or spaces within a keyword.\n"
        "4. \"adobe_cat\": (String) Choose one Adobe category.\n"
        "5. \"shutter_cats\": (Array of EXACTLY 2 strings) Choose two Shutterstock categories.\n"
        "6. \"has_copy_space\": (Boolean) True if clean negative space exists.\n"
        "7. \"camera_angle\": (String) E.g., Top-down, Eye-level, Macro.\n"
        "8. \"target_buyer\": (String) Return the buyer name.\n"
        'EXPECTED JSON FORMAT: {"persona_internal_monologue": "...", "title": "...", "keywords": "...", '
        '"adobe_cat": "...", "shutter_cats": ["Nature", "Travel"], "has_copy_space": false, '
        f'"camera_angle": "...", "target_buyer": "{target_buyer}"}}'
    )

# Liste oficiale la nivel de modul (importabile din app.py)
ADOBE_CATEGORIES = [
    "Animals",
    "Buildings and Architecture",
    "Business",
    "Drinks",
    "The Environment",
    "States of Mind",
    "Food",
    "Graphic Resources",
    "Hobbies and Leisure",
    "Industry",
    "Landscapes",
    "Lifestyle",
    "People",
    "Plants and Flowers",
    "Culture and Religion",
    "Science",
    "Social Issues",
    "Sports",
    "Technology",
    "Transport",
    "Travel",
]

SHUTTERSTOCK_CATEGORIES = [
    "Abstract",
    "Animals/Wildlife",
    "The Arts",
    "Backgrounds/Textures",
    "Beauty/Fashion",
    "Buildings/Landmarks",
    "Business/Finance",
    "Celebrities",
    "Education",
    "Food and Drink",
    "Healthcare/Medical",
    "Holidays",
    "Industrial",
    "Interiors",
    "Lifestyle",
    "Miscellaneous",
    "Nature",
    "Objects",
    "Parks/Outdoor",
    "People",
    "Religion",
    "Science",
    "Signs/Symbols",
    "Sports/Recreation",
    "Technology",
    "Transportation",
    "Travel",
    "Vintage",
]


def normalize_shutter_cats(raw, fallback=None) -> list[str]:
    values = []
    if isinstance(raw, str):
        values = [item.strip() for item in raw.split(",") if item.strip()]
    elif isinstance(raw, (list, tuple)):
        values = [str(item).strip() for item in raw if str(item).strip()]
    cleaned = []
    for item in values:
        if item in SHUTTERSTOCK_CATEGORIES and item not in cleaned:
            cleaned.append(item)
    fallback = fallback or []
    for item in fallback:
        if item in SHUTTERSTOCK_CATEGORIES and item not in cleaned:
            cleaned.append(item)
    for item in SHUTTERSTOCK_CATEGORIES:
        if len(cleaned) >= 2:
            break
        if item not in cleaned:
            cleaned.append(item)
    return cleaned[:2]


ADOBE_KEYWORDS = {
    "Animals": {"animal", "dog", "cat", "bird", "wildlife", "pet", "horse", "fish"},
    "Buildings and Architecture": {"building", "architecture", "house", "bridge", "landmark", "urban"},
    "Business": {"business", "office", "meeting", "corporate", "finance", "work"},
    "Drinks": {"drink", "coffee", "tea", "wine", "beer", "cocktail", "juice"},
    "The Environment": {"environment", "climate", "recycle", "earth", "sustainability"},
    "States of Mind": {"emotion", "mood", "happy", "sad", "mind", "feeling"},
    "Food": {"food", "meal", "restaurant", "kitchen", "cooking", "fruit", "dessert"},
    "Graphic Resources": {"texture", "pattern", "background", "abstract", "graphic"},
    "Hobbies and Leisure": {"hobby", "leisure", "game", "music", "fun"},
    "Industry": {"industry", "factory", "industrial", "construction", "warehouse"},
    "Landscapes": {"landscape", "mountain", "valley", "horizon", "vista"},
    "Lifestyle": {"lifestyle", "home", "daily", "living", "interior"},
    "People": {"people", "person", "man", "woman", "child", "portrait", "family"},
    "Plants and Flowers": {"plant", "flower", "leaf", "garden", "bloom"},
    "Culture and Religion": {"religion", "church", "temple", "culture", "faith"},
    "Science": {"science", "lab", "research", "microscope", "chemistry"},
    "Social Issues": {"community", "protest", "equality", "society", "charity"},
    "Sports": {"sport", "fitness", "running", "football", "athlete", "gym"},
    "Technology": {"technology", "computer", "phone", "digital", "robot", "ai"},
    "Transport": {"car", "train", "plane", "bike", "boat", "vehicle", "traffic"},
    "Travel": {"travel", "tourism", "vacation", "destination", "passport"},
}

SHUTTER_KEYWORDS = {
    "Abstract": {"abstract", "pattern", "geometric", "shape", "minimal"},
    "Animals/Wildlife": {"animal", "wildlife", "dog", "cat", "bird", "pet"},
    "The Arts": {"art", "paint", "music", "sculpture", "creative"},
    "Backgrounds/Textures": {"background", "texture", "wallpaper", "surface"},
    "Beauty/Fashion": {"beauty", "fashion", "makeup", "model", "style"},
    "Buildings/Landmarks": {"building", "landmark", "architecture", "city", "monument"},
    "Business/Finance": {"business", "office", "finance", "corporate", "money"},
    "Celebrities": {"celebrity", "famous", "star", "red carpet"},
    "Education": {"education", "school", "student", "teacher", "classroom"},
    "Food and Drink": {"food", "drink", "meal", "coffee", "kitchen", "restaurant"},
    "Healthcare/Medical": {"health", "medical", "doctor", "hospital", "medicine"},
    "Holidays": {"holiday", "christmas", "easter", "celebration", "festival"},
    "Industrial": {"industrial", "factory", "industry", "warehouse"},
    "Interiors": {"interior", "room", "furniture", "home decor"},
    "Lifestyle": {"lifestyle", "living", "daily", "home"},
    "Miscellaneous": set(),
    "Nature": {"nature", "forest", "tree", "river", "lake", "ocean", "sunset"},
    "Objects": {"object", "product", "item", "isolated", "studio"},
    "Parks/Outdoor": {"park", "outdoor", "trail", "camp", "picnic"},
    "People": {"people", "person", "man", "woman", "child", "portrait"},
    "Religion": {"religion", "church", "temple", "faith", "prayer"},
    "Science": {"science", "lab", "research", "microscope"},
    "Signs/Symbols": {"sign", "symbol", "icon", "logo"},
    "Sports/Recreation": {"sport", "fitness", "running", "athlete", "recreation"},
    "Technology": {"technology", "computer", "phone", "digital", "software"},
    "Transportation": {"car", "train", "plane", "bike", "boat", "transport"},
    "Travel": {"travel", "tourism", "vacation", "destination"},
    "Vintage": {"vintage", "retro", "old", "antique"},
}


def _tokens(text: str) -> set[str]:
    cleaned = re.sub(r"[^a-z0-9\s/]+", " ", (text or "").lower())
    return set(cleaned.split())


def _score_categories(text: str, mapping: dict[str, set[str]], all_categories: list[str]) -> list[str]:
    tokens = _tokens(text)
    scored = []
    for category in all_categories:
        terms = mapping.get(category, set())
        score = sum(1 for term in terms if term in tokens or term in text.lower())
        scored.append((score, category))
    scored.sort(key=lambda item: item[0], reverse=True)
    best_score = scored[0][0]
    if best_score <= 0:
        return all_categories[:]
    return [category for score, category in scored if score == best_score]


def _least_used(candidates: list[str], usage_key: str) -> str:
    if "category_usage" not in st.session_state:
        st.session_state.category_usage = {"adobe": {}, "shutter": {}}
    usage = st.session_state.category_usage.setdefault(usage_key, {})
    chosen = min(candidates, key=lambda name: usage.get(name, 0))
    usage[chosen] = usage.get(chosen, 0) + 1
    return chosen


def choose_categories(title: str, keywords: str) -> dict:
    haystack = f"{title} {keywords}"
    adobe_candidates = _score_categories(haystack, ADOBE_KEYWORDS, ADOBE_CATEGORIES)
    shutter_candidates = _score_categories(haystack, SHUTTER_KEYWORDS, SHUTTERSTOCK_CATEGORIES)
    first = _least_used(shutter_candidates, "shutter")
    remaining = [item for item in shutter_candidates if item != first] or [
        item for item in SHUTTERSTOCK_CATEGORIES if item != first
    ]
    second = _least_used(remaining, "shutter")
    return {
        "adobe_cat": _least_used(adobe_candidates, "adobe"),
        "shutter_cats": [first, second],
    }


class PhotoTagService:
    def generate_metadata(self, image_path, custom_prompt=None, image_index=0, master_brief: str = ""):
        if not config.PHOTOTAG_API_KEY:
            return {"success": False, "error": "PhotoTag API key este lipsă."}

        if not image_path.exists():
            return {"success": False, "error": "Thumbnail-ul nu există pe disc."}

        headers = {
            "Authorization": f"Bearer {config.PHOTOTAG_API_KEY}"
        }

        data = {
            "addMetadata": "false",
            "saveFile": "false",
            "language": "en",
            "maxKeywords": 50,
            "maxTitleCharacters": 199,
        }

        buyer = get_buyer_config(image_index)
        target_buyer = buyer["role"]
        current_temp = buyer["temp"]
        data["customContext"] = build_custom_context(
            image_index,
            custom_prompt=custom_prompt,
            master_brief=master_brief,
        )
        data["temperature"] = current_temp

        try:
            logger.info(
                f"Se trimite {image_path.name} către PhotoTag.AI... buyer={target_buyer} temp={current_temp}"
            )
            safe_headers = {
                key: "Bearer ***" if key.lower() == "authorization" else value
                for key, value in headers.items()
            }
            logger.info(
                "PhotoTag request url=%s headers=%s data=%s file=%s",
                config.PHOTOTAG_API_URL,
                safe_headers,
                data,
                {"name": image_path.name, "content_type": "image/jpeg"},
            )
            with open(image_path, "rb") as img_file:
                files = {"file": (image_path.name, img_file, "image/jpeg")}
                time.sleep(1.5)
                response = requests.post(
                    config.PHOTOTAG_API_URL,
                    headers=headers,
                    data=data,
                    files=files,
                    timeout=35,
                )

            if response.status_code == 200:
                try:
                    result_json = response.json()
                except requests.exceptions.JSONDecodeError:
                    return {"success": False, "error": "Răspunsul PhotoTag nu conține JSON valid."}

                payload = result_json.get("data", result_json)
                if not isinstance(payload, dict):
                    payload = result_json if isinstance(result_json, dict) else {}

                if isinstance(payload.get("title"), str) and payload["title"].lstrip().startswith("{"):
                    try:
                        nested = json.loads(payload["title"])
                        if isinstance(nested, dict):
                            payload = {**payload, **nested}
                    except json.JSONDecodeError:
                        pass
                for blob_key in ("description", "caption", "raw", "json"):
                    blob = payload.get(blob_key)
                    if isinstance(blob, str) and "{" in blob and "camera_angle" in blob:
                        try:
                            nested = json.loads(blob[blob.find("{"):blob.rfind("}") + 1])
                            if isinstance(nested, dict):
                                payload = {**payload, **nested}
                        except json.JSONDecodeError:
                            pass

                title = (
                    payload.get("title")
                    or payload.get("Title")
                    or payload.get("iptcTitle")
                    or ""
                )
                description = (
                    payload.get("description")
                    or payload.get("caption")
                    or payload.get("Caption")
                    or ""
                )
                keywords = (
                    payload.get("keywords")
                    or payload.get("Keywords")
                    or payload.get("tags")
                    or []
                )
                if isinstance(keywords, list):
                    keywords = ", ".join(str(keyword) for keyword in keywords if keyword)
                else:
                    keywords = str(keywords or "")

                categories = choose_categories(str(title), keywords)
                adobe_cat = payload.get("adobe_cat") or categories["adobe_cat"]
                if adobe_cat not in ADOBE_CATEGORIES:
                    adobe_cat = categories["adobe_cat"]
                shutter_cats = normalize_shutter_cats(
                    payload.get("shutter_cats") or payload.get("shutter_cat"),
                    fallback=categories["shutter_cats"],
                )
                has_copy_space = payload.get("has_copy_space", payload.get("copy_space"))
                if isinstance(has_copy_space, str):
                    has_copy_space = has_copy_space.strip().lower() in {"true", "1", "yes"}
                camera_angle = (
                    payload.get("camera_angle")
                    or payload.get("angle")
                    or payload.get("cameraAngle")
                    or "eye-level"
                )
                parsed_buyer = payload.get("target_buyer") or payload.get("buyer") or target_buyer
                monologue = str(
                    payload.get("persona_internal_monologue")
                    or payload.get("internal_monologue")
                    or ""
                ).strip()
                if monologue:
                    logger.info(f"persona_internal_monologue [{target_buyer}]: {monologue}")
                return {
                    "success": True,
                    "title": str(title)[:200],
                    "description": str(description),
                    "keywords": keywords,
                    "adobe_cat": adobe_cat,
                    "shutter_cats": shutter_cats,
                    "shutter_cat": ", ".join(shutter_cats),
                    "has_copy_space": bool(has_copy_space),
                    "camera_angle": str(camera_angle).strip() or "eye-level",
                    "target_buyer": str(parsed_buyer).strip() or target_buyer,
                    "persona_internal_monologue": monologue,
                    "vibe": target_buyer,
                    "error": None,
                }

            error_msg = f"Upstream error: {response.status_code} - {response.text}"
            logger.error("PhotoTag upstream response [%s]: %s", response.status_code, response.text)
            return {"success": False, "error": error_msg}

        except requests.exceptions.Timeout:
            return {"success": False, "error": "Cererea PhotoTag a depășit timpul de așteptare."}
        except requests.exceptions.RequestException as e:
            response_text = e.response.text if e.response is not None else ""
            detail = f"{e} - {response_text}" if response_text else str(e)
            logger.error("Phototag Service Error: %s", detail)
            return {"success": False, "error": detail}
        except OSError as e:
            logger.error(f"Eroare la procesarea imaginii {image_path.name}: {e}")
            return {"success": False, "error": str(e)}


phototag_service = PhotoTagService()
