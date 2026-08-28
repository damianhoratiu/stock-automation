import csv
import re
from pathlib import Path

SHUTTERSTOCK_CATEGORIES = [
    "Abstract",
    "Animals/Wildlife",
    "The Arts",
    "Backgrounds/Textures",
    "Beauty/Fashion",
    "Buildings/Landmarks",
    "Business/Finance",
    "Education",
    "Food and Drink",
    "Healthcare/Medical",
    "Holidays",
    "Industrial",
    "Interiors",
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
    "Vintage",
]

CATEGORY_KEYWORDS = {
    "Food and Drink": {
        "food", "drink", "meal", "restaurant", "kitchen", "cooking", "chef",
        "coffee", "tea", "wine", "beer", "breakfast", "lunch", "dinner",
        "fruit", "vegetable", "dessert", "bakery", "cuisine", "ingredient",
        "recipe", "plate", "tableware", "culinary",
    },
    "People": {
        "people", "person", "man", "woman", "child", "portrait", "family",
        "crowd", "human", "face", "model", "couple", "baby", "girl", "boy",
    },
    "Nature": {
        "nature", "landscape", "forest", "tree", "mountain", "river", "lake",
        "sea", "ocean", "sky", "sunset", "flower", "plant", "wildlife",
        "outdoor", "field", "garden",
    },
    "Business/Finance": {
        "business", "office", "finance", "meeting", "corporate", "work",
        "laptop", "handshake", "team", "startup", "money", "graph",
    },
    "Abstract": {
        "abstract", "pattern", "texture", "geometric", "background",
        "gradient", "shape", "minimal",
    },
    "Objects": {
        "object", "product", "still life", "item", "tool", "gadget",
        "isolated", "studio",
    },
    "Animals/Wildlife": {
        "animal", "dog", "cat", "bird", "wildlife", "pet", "horse", "fish",
    },
    "Technology": {
        "technology", "computer", "phone", "digital", "software", "circuit",
        "robot", "ai",
    },
    "Buildings/Landmarks": {
        "building", "architecture", "city", "landmark", "street", "urban",
        "house", "bridge",
    },
    "Transportation": {
        "car", "train", "plane", "bike", "boat", "transport", "traffic",
        "vehicle",
    },
    "Sports/Recreation": {
        "sport", "fitness", "running", "football", "soccer", "gym", "athlete",
    },
    "Healthcare/Medical": {
        "health", "medical", "doctor", "hospital", "medicine", "clinic",
    },
}


def get_shutterstock_category(keywords: str) -> str:
    text = re.sub(r"[^a-z0-9\s/]+", " ", (keywords or "").lower())
    tokens = set(text.split())
    scores = {}
    for category, terms in CATEGORY_KEYWORDS.items():
        scores[category] = sum(1 for term in terms if term in tokens or term in text)
    best = max(scores, key=scores.get)
    if scores[best] > 0:
        return best
    return "Objects"


def write_shutterstock_csv(folder: Path, metadata: dict) -> Path:
    csv_path = folder / "shutterstock_metadata.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "Filename",
            "Description",
            "Keywords",
            "Categories",
            "Editorial",
            "Mature content",
            "illustration",
        ])
        for filename, meta in metadata.items():
            description = (meta.get("description") or meta.get("title") or "").strip()
            keywords = (meta.get("keywords") or "").strip()
            cats = meta.get("shutter_cats")
            if isinstance(cats, str):
                cats = [item.strip() for item in cats.split(",") if item.strip()]
            if not cats:
                fallback = (meta.get("shutter_cat") or get_shutterstock_category(keywords)).strip()
                cats = [item.strip() for item in fallback.split(",") if item.strip()]
            category = ",".join(cats[:2])
            writer.writerow([
                filename,
                description,
                keywords,
                category,
                "no",
                "no",
                "no",
            ])
    return csv_path
