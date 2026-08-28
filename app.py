from __future__ import annotations

import io
import html
import json
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image

import config
from database.supabase_client import supabase_client, supabase_manager
from services.crypto_service import decrypt_password, encrypt_password
from services.exif_service import exif_service
from services.ftp_service import ftp_uploader, verify_ftp_credentials
from services.phototag_service import (
    ADOBE_CATEGORIES,
    SHUTTERSTOCK_CATEGORIES,
    get_target_buyer,
    normalize_shutter_cats,
    phototag_service,
)
from services.platform_service import PLATFORMS, file_is_complete_for_platforms
from utils.logger import get_logger

logger = get_logger("app")

st.set_page_config(
    page_title="Stock automation",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={},
)

st.markdown(
    """
<style>
#MainMenu, header, footer, .stDeployButton {display: none !important;}
:root {
    --ink: #1d1d1f;
    --muted: #6e6e73;
    --line: rgba(0, 0, 0, .08);
    --surface: rgba(255, 255, 255, .78);
    --blue: #0071e3;
    --blue-hover: #0077ed;
    --green: #16843d;
    --red: #d70015;
    --radius-lg: 28px;
    --radius-md: 18px;
    --shadow: 0 18px 55px rgba(0, 0, 0, .08);
}
html {scroll-behavior: smooth;}
body, .stApp {
    color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
}
.stApp {
    background:
        radial-gradient(circle at 12% 4%, rgba(0, 113, 227, .10), transparent 27rem),
        radial-gradient(circle at 88% 12%, rgba(175, 82, 222, .08), transparent 24rem),
        linear-gradient(180deg, #fbfbfd 0%, #f5f5f7 55%, #ffffff 100%);
}
[data-testid="stAppViewContainer"] > .main {
    background: transparent;
}
.block-container {
    max-width: 1240px;
    padding: 1.25rem 2rem 5rem !important;
}

.stock-hero {
    position: relative;
    overflow: hidden;
    min-height: 250px;
    margin: .5rem 0 1.4rem;
    padding: 3.6rem 4rem;
    border: 1px solid rgba(255,255,255,.55);
    border-radius: 34px;
    background:
        radial-gradient(circle at 84% 18%, rgba(133, 203, 255, .95), transparent 15rem),
        radial-gradient(circle at 72% 80%, rgba(116, 94, 255, .72), transparent 18rem),
        linear-gradient(135deg, #09111f 0%, #102746 48%, #075db0 100%);
    box-shadow: 0 28px 80px rgba(10, 47, 93, .20);
    isolation: isolate;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", Arial, sans-serif;
    animation: hero-in .65s cubic-bezier(.2,.8,.2,1);
}
.stock-hero::after {
    content: "";
    position: absolute;
    width: 310px;
    height: 310px;
    right: -60px;
    top: -105px;
    border-radius: 50%;
    border: 1px solid rgba(255,255,255,.25);
    box-shadow: 0 0 0 42px rgba(255,255,255,.04), 0 0 0 84px rgba(255,255,255,.025);
    z-index: -1;
}
.hero-eyebrow {
    color: #8ed1ff;
    font-size: .76rem;
    font-weight: 700;
    letter-spacing: .14em;
    text-transform: uppercase;
}
.stock-hero h1 {
    max-width: 760px;
    margin: .65rem 0 .8rem;
    color: #fff !important;
    font-size: clamp(2.5rem, 5vw, 4.85rem) !important;
    font-weight: 650 !important;
    letter-spacing: -.055em !important;
    line-height: .96 !important;
}
.stock-hero p {
    max-width: 620px;
    margin: 0;
    color: rgba(255,255,255,.72);
    font-size: 1.08rem;
    line-height: 1.55;
}
.hero-features {
    display: flex;
    flex-wrap: wrap;
    gap: .65rem;
    margin-top: 1.6rem;
}
.hero-feature {
    display: inline-flex;
    align-items: center;
    gap: .5rem;
    padding: .5rem .75rem;
    border: 1px solid rgba(255,255,255,.16);
    border-radius: 999px;
    background: rgba(255,255,255,.09);
    color: rgba(255,255,255,.86);
    font-size: .78rem;
    font-weight: 560;
    backdrop-filter: blur(14px);
}
.hero-feature::before {
    content: "";
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #76d6ff;
    box-shadow: 0 0 12px rgba(118,214,255,.9);
}
@keyframes hero-in {from {transform: translateY(12px)} to {transform: none}}

h1, h2, h3 {
    color: var(--ink) !important;
    letter-spacing: -.035em !important;
}
h1 {font-weight: 650 !important;}
h2 {font-size: clamp(1.8rem, 3vw, 2.7rem) !important; font-weight: 650 !important;}
h3 {font-weight: 620 !important;}
p, label {color: #424245;}
[data-testid="stCaptionContainer"] {color: #5f6368; font-size: .9rem; font-weight: 480; line-height: 1.5;}
[data-testid="stWidgetLabel"] p {
    color: #2c2c2e !important;
    font-size: .92rem !important;
    font-weight: 650 !important;
    letter-spacing: -.01em;
}

[data-baseweb="tab-list"] {
    position: sticky;
    top: 12px;
    z-index: 20;
    width: fit-content;
    margin: 0 auto 2rem;
    padding: 5px !important;
    gap: 3px !important;
    border: 1px solid rgba(0,0,0,.07);
    border-radius: 999px;
    background: rgba(255,255,255,.76);
    box-shadow: 0 8px 30px rgba(0,0,0,.08);
    backdrop-filter: saturate(180%) blur(24px);
    -webkit-backdrop-filter: saturate(180%) blur(24px);
}
[data-baseweb="tab"] {
    height: 40px !important;
    padding: 0 1.15rem !important;
    border-radius: 999px !important;
    color: var(--muted) !important;
    font-size: .88rem !important;
    font-weight: 560 !important;
}
[data-baseweb="tab"][aria-selected="true"] {
    color: var(--ink) !important;
    background: #fff !important;
    box-shadow: 0 2px 10px rgba(0,0,0,.09);
}
[data-baseweb="tab-highlight"] {display: none;}

[data-testid="stForm"], [data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid rgba(0,0,0,.07) !important;
    border-radius: var(--radius-lg) !important;
    background: var(--surface) !important;
    box-shadow: var(--shadow);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
}
[data-testid="stVerticalBlockBorderWrapper"] > div {padding: 1.25rem !important;}

.stTextInput input, .stTextArea textarea {
    min-height: 46px;
    border: 1px solid rgba(0,0,0,.11) !important;
    border-radius: 14px !important;
    background: linear-gradient(180deg, #ffffff 0%, #fafafd 100%) !important;
    color: var(--ink) !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,.9), 0 1px 3px rgba(0,0,0,.04);
    transition: border-color .2s ease, box-shadow .2s ease, background .2s ease;
}
.stTextArea textarea {
    min-height: 132px !important;
    padding: 1rem 1.05rem !important;
    font-size: 1rem !important;
    line-height: 1.48 !important;
}
.stTextInput input:focus, .stTextArea textarea:focus,
[data-baseweb="select"]:focus-within {
    border-color: var(--blue) !important;
    background: #fff !important;
    box-shadow: 0 0 0 1px var(--blue), 0 0 0 5px rgba(0,113,227,.09), 0 12px 34px rgba(0,113,227,.08) !important;
}
[data-baseweb="select"] {
    min-height: 50px;
    border: 1px solid rgba(0,0,0,.11) !important;
    border-radius: 14px !important;
    background: #fff !important;
    box-shadow: 0 1px 2px rgba(0,0,0,.035);
}
[data-baseweb="select"] > div {
    border: 0 !important;
    background: transparent !important;
}
[data-baseweb="tag"] {
    border: 1px solid rgba(0,0,0,.055) !important;
    border-radius: 8px !important;
    background: rgba(245,245,247,.94) !important;
    color: #424245 !important;
    box-shadow: 0 1px 2px rgba(0,0,0,.025);
}
[data-baseweb="tag"] * {color: inherit !important; font-size: .8rem !important; font-weight: 560 !important;}

.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {
    min-height: 50px;
    padding: .7rem 1.35rem !important;
    border: 1px solid #d2d2d7 !important;
    border-radius: 14px !important;
    background: #fff !important;
    color: #1d1d1f !important;
    font-size: .98rem !important;
    font-weight: 650 !important;
    letter-spacing: -.01em;
    box-shadow: 0 2px 5px rgba(0,0,0,.06);
    transition: transform .18s ease, box-shadow .18s ease, background .18s ease !important;
}
.stButton > button *, .stDownloadButton > button *,
[data-testid="stFormSubmitButton"] > button * {
    color: inherit !important;
    font: inherit !important;
    line-height: 1.2 !important;
}
.stButton > button:hover, .stDownloadButton > button:hover,
[data-testid="stFormSubmitButton"] > button:hover {
    border-color: #b8b8bd !important;
    background: #f9f9fb !important;
    color: #1d1d1f !important;
    box-shadow: 0 5px 14px rgba(0,0,0,.09);
    transform: translateY(-1px);
}
.stButton > button:active, .stDownloadButton > button:active {transform: scale(.985);}
.stButton > button[kind="primary"], button[data-testid="stBaseButton-primary"] {
    min-height: 54px;
    border-color: #0071e3 !important;
    border-radius: 14px !important;
    background: linear-gradient(180deg, #0a84ff 0%, #0071e3 100%) !important;
    color: #fff !important;
    font-size: 1rem !important;
    font-weight: 700 !important;
    box-shadow: 0 8px 20px rgba(0,113,227,.24), inset 0 1px 0 rgba(255,255,255,.2);
}
.stButton > button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover {
    border-color: #0068d1 !important;
    background: linear-gradient(180deg, #198cff 0%, #0675e8 100%) !important;
    color: #fff !important;
    box-shadow: 0 11px 25px rgba(0,113,227,.3), inset 0 1px 0 rgba(255,255,255,.22);
}
.stButton > button[kind="primary"] *, button[data-testid="stBaseButton-primary"] * {color: #fff !important;}
button:disabled {opacity: .42 !important; box-shadow: none !important; transform: none !important;}

[data-testid="stMetric"] {
    min-height: 120px;
    padding: 1.25rem 1.4rem;
    border: 1px solid rgba(0,0,0,.06);
    border-radius: var(--radius-md);
    background: rgba(255,255,255,.84);
    box-shadow: 0 10px 35px rgba(0,0,0,.055);
}
[data-testid="stMetricLabel"] {color: var(--muted); font-weight: 550;}
[data-testid="stMetricValue"] {color: var(--ink); font-size: 2.25rem; font-weight: 650; letter-spacing: -.05em;}

[data-testid="stAlert"] {
    border: 1px solid rgba(0,113,227,.12) !important;
    border-radius: 14px !important;
    box-shadow: none;
}
[data-testid="stAlert"] p {
    color: inherit !important;
    font-size: .92rem !important;
    line-height: 1.45 !important;
}
[data-testid="stStatusWidget"] {
    overflow: hidden;
    border: 1px solid rgba(0,0,0,.07) !important;
    border-radius: var(--radius-md) !important;
    background: rgba(255,255,255,.85) !important;
    box-shadow: var(--shadow);
}
.stProgress > div {
    height: 12px !important;
    padding: 2px;
    overflow: hidden;
    border: 1px solid rgba(29,29,31,.08);
    border-radius: 999px;
    background: rgba(29,29,31,.07) !important;
    box-shadow: inset 0 1px 3px rgba(0,0,0,.08), 0 1px 0 rgba(255,255,255,.9);
}
.stProgress > div > div {
    position: relative;
    height: 6px !important;
    overflow: hidden;
    border-radius: 999px;
    background: linear-gradient(90deg, #36d1dc 0%, #5b8cff 38%, #a855f7 68%, #ff6b9d 100%) !important;
    background: linear-gradient(90deg in oklab, #36d1dc 0%, #5b8cff 38%, #a855f7 68%, #ff6b9d 100%) !important;
    background-size: 220% 100% !important;
    box-shadow: 0 0 14px rgba(91,140,255,.42);
    animation: progress-flow 2.8s cubic-bezier(.45,0,.2,1) infinite;
}
.stProgress > div > div::after {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(105deg, transparent 20%, rgba(255,255,255,.82) 48%, transparent 72%);
    transform: translateX(-110%);
    animation: progress-glint 1.9s ease-in-out infinite;
}
@keyframes progress-flow {
    0%, 100% {background-position: 0% 50%; filter: saturate(.95);}
    50% {background-position: 100% 50%; filter: saturate(1.16);}
}
@keyframes progress-glint {
    0% {transform: translateX(-110%); opacity: 0;}
    30% {opacity: .9;}
    72%, 100% {transform: translateX(110%); opacity: 0;}
}

[data-testid="stImage"] img {
    border-radius: 18px !important;
    box-shadow: 0 16px 40px rgba(0,0,0,.13);
}
[data-testid="stDataFrame"] {
    overflow: hidden;
    border: 1px solid rgba(0,0,0,.07);
    border-radius: var(--radius-md);
    background: #fff;
    box-shadow: 0 12px 38px rgba(0,0,0,.06);
}
hr {border-color: var(--line) !important;}
code {border-radius: 8px; background: rgba(0,0,0,.045) !important; color: #424245 !important;}

.folder-context {
    display: flex;
    align-items: center;
    gap: .5rem;
    margin: -.1rem 0 1rem;
    color: var(--muted);
    font-size: .9rem;
}
.folder-path {
    display: inline-block;
    max-width: 100%;
    padding: .3rem .55rem;
    overflow: hidden;
    border: 1px solid rgba(0,113,227,.11);
    border-radius: 8px;
    background: rgba(0,113,227,.055);
    color: #24577f;
    font-family: "SFMono-Regular", Consolas, monospace;
    font-size: .82rem;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.field-counter {
    margin: .28rem .15rem .8rem;
    color: #86868b;
    font-size: .78rem;
    font-weight: 560;
    text-align: right;
}
.field-counter.is-valid {color: #248a3d;}
.field-counter.is-warning {color: #b25000;}
[data-baseweb="select"]:has(input[aria-label="Cuvinte cheie"]) {
    min-height: 96px;
    align-items: flex-start;
    padding: .55rem .4rem;
    border-color: rgba(0,0,0,.09) !important;
    background: linear-gradient(180deg, #fff 0%, #fafafd 100%) !important;
    box-shadow: inset 0 1px 0 #fff, 0 1px 3px rgba(0,0,0,.035);
}
[data-baseweb="select"]:has(input[aria-label="Cuvinte cheie"]) [data-baseweb="tag"] {
    margin: 3px !important;
    padding: 4px 8px !important;
}

.portal-notice {
    position: relative;
    margin: .9rem 0 1.35rem;
    padding: 1rem 1.1rem 1rem 1.2rem;
    overflow: hidden;
    border: 1px solid rgba(88,86,214,.14);
    border-radius: 15px;
    background: linear-gradient(135deg, rgba(88,86,214,.08), rgba(90,200,250,.06));
    color: #29293a;
    font-size: .92rem;
    font-weight: 520;
    line-height: 1.5;
}
.portal-notice::before {
    content: "";
    position: absolute;
    inset: 0 auto 0 0;
    width: 3px;
    background: linear-gradient(#5856d6, #5ac8fa);
}
.portal-notice strong {color: #1d1d1f; font-weight: 680;}

.result-row {
    display: flex;
    align-items: center;
    gap: .8rem;
    min-height: 58px;
    margin: .45rem 0;
    padding: .8rem 1rem;
    border: 1px solid rgba(0,0,0,.07);
    border-radius: 14px;
    background: rgba(255,255,255,.82);
    color: #1d1d1f;
    font-size: .93rem;
    font-weight: 610;
    box-shadow: 0 4px 15px rgba(0,0,0,.035);
}
.result-row::before {
    content: "";
    width: 10px;
    height: 10px;
    flex: 0 0 10px;
    border-radius: 50%;
}
.result-row.success::before {background: #30a46c; box-shadow: 0 0 0 5px rgba(48,164,108,.11);}
.result-row.error::before {background: #e5484d; box-shadow: 0 0 0 5px rgba(229,72,77,.10);}
.result-row .result-name {overflow: hidden; text-overflow: ellipsis; white-space: nowrap;}
.result-row .result-state {margin-left: auto; color: #248a3d; font-size: .78rem; font-weight: 700; text-transform: uppercase; letter-spacing: .06em;}
.result-row.error .result-state {color: #c41c24;}
.result-row.error .result-state {
    max-width: 58%;
    overflow: hidden;
    text-align: right;
    text-overflow: ellipsis;
    text-transform: none;
    letter-spacing: 0;
    white-space: nowrap;
}

[data-testid="stCheckbox"] label p {
    color: #2c2c2e !important;
    font-size: .92rem !important;
    font-weight: 600 !important;
}

.workflow-steps {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 0;
    margin: .55rem 0 2rem;
    padding: .9rem 1rem;
    border: 1px solid rgba(0,0,0,.065);
    border-radius: 15px;
    background: rgba(255,255,255,.64);
}
.workflow-step {
    position: relative;
    color: #86868b;
    font-size: .72rem;
    font-weight: 620;
    text-align: center;
}
.workflow-step::before {
    content: "";
    position: relative;
    z-index: 2;
    display: block;
    width: 8px;
    height: 8px;
    margin: 0 auto .45rem;
    border: 2px solid #c7c7cc;
    border-radius: 50%;
    background: #fff;
}
.workflow-step:not(:first-child)::after {
    content: "";
    position: absolute;
    top: 4px;
    right: 50%;
    width: 100%;
    height: 1px;
    background: #dcdce0;
}
.workflow-step.done {color: #3a3a3c;}
.workflow-step.done::before {border-color: #8e8e93; background: #8e8e93;}
.workflow-step.active {color: #1d1d1f; font-weight: 720;}
.workflow-step.active::before {
    border-color: #7c5cff;
    background: #fff;
    box-shadow: 0 0 0 5px rgba(124,92,255,.11), 0 0 18px rgba(124,92,255,.28);
}

.shutter-box {
    margin: .35rem 0 .8rem;
    padding: .9rem 1rem .35rem;
    border: 1px solid rgba(0,113,227,.14);
    border-radius: 16px;
    background: linear-gradient(135deg, rgba(0,113,227,.07), rgba(90,200,250,.035));
}
.shutter-box [data-baseweb="tag"] {background: #dceeff !important;}

@media (max-width: 640px) {
    .block-container {padding: .75rem 1rem 3rem !important;}
    .stock-hero {min-height: 220px; padding: 2.4rem 1.5rem; border-radius: 24px;}
    .stock-hero h1 {font-size: 2.55rem !important;}
    .stock-hero p {font-size: .98rem;}
    .hero-features {gap: .45rem; margin-top: 1.2rem;}
    .hero-feature {font-size: .72rem;}
    [data-baseweb="tab-list"] {top: 7px; width: 100%; overflow-x: auto; justify-content: flex-start;}
    [data-baseweb="tab"] {padding: 0 .8rem !important; white-space: nowrap;}
    [data-testid="stHorizontalBlock"] {gap: .8rem !important;}
    [data-testid="stMetric"] {min-height: 98px;}
    .workflow-steps {padding: .75rem .35rem;}
    .workflow-step {font-size: .62rem;}
}

@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {animation-duration: .01ms !important; transition-duration: .01ms !important;}
}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
    <section class="stock-hero">
        <div class="hero-eyebrow">Intelligent stock workflow</div>
        <h1>From image to market. Beautifully automated.</h1>
        <p>Metadata intelligence, human review and multi-platform delivery in one focused workspace.</p>
        <div class="hero-features">
            <span class="hero-feature">AI metadata</span>
            <span class="hero-feature">Human review</span>
            <span class="hero-feature">Multi-platform delivery</span>
        </div>
    </section>
    """,
    unsafe_allow_html=True,
)


def get_directory_path() -> str:
    try:
        script = """
        tell application "System Events"
            activate
            set folderPath to choose folder with prompt "Alege folderul cu fotografii:"
            POSIX path of folderPath
        end tell
        """
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""
    except Exception as e:
        logger.error(f"Eroare la dialogul de selectare folder: {e}")
        return ""


def list_original_images(folder: Path) -> list[Path]:
    images = []
    for path in sorted(folder.iterdir()):
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        if path.name == THUMB_DIR_NAME:
            continue
        if "_Thumbnail" in path.stem:
            continue
        if path.suffix.lower() in {".jpg", ".jpeg"}:
            images.append(path)
    return images


THUMB_DIR_NAME = ".thumbnails_temp"


SECURE_CONFIG_PATH = Path("config.json")


def run_ftp_credential_test(service_type: str):
    if service_type == "adobe":
        username = (config.FTP_ADOBE_USER or "").strip()
        stored_password = config.FTP_ADOBE_PASS or ""
        missing_msg = "Lipsesc userul sau parola Adobe."
    else:
        username = (config.FTP_SHUTTER_USER or "").strip()
        stored_password = config.FTP_SHUTTER_PASS or ""
        missing_msg = "Lipsesc userul sau parola Shutterstock."

    if not username or not stored_password:
        st.session_state.ftp_test_status[service_type] = {
            "tested": True,
            "ok": False,
            "message": missing_msg,
        }
        st.error(missing_msg)
        return

    password = decrypt_password(stored_password)
    if not password:
        message = "Nu s-a putut decripta parola salvată."
        st.session_state.ftp_test_status[service_type] = {
            "tested": True,
            "ok": False,
            "message": message,
        }
        st.error(message)
        return

    ok, message = verify_ftp_credentials(service_type, username, password)
    status_label = "🟢 Conexiune reușită" if ok else "🔴 Credențiale invalide"
    st.session_state.ftp_test_status[service_type] = {
        "tested": True,
        "ok": ok,
        "message": message,
    }
    if service_type == "adobe":
        st.session_state.adobe_status = status_label
    else:
        st.session_state.shutter_status = status_label
    if ok:
        st.success(message)
    else:
        st.error(message)


def render_ftp_test_status(service_type: str, label: str):
    status = st.session_state.ftp_test_status.get(service_type, {})
    key = "adobe_status" if service_type == "adobe" else "shutter_status"
    label_state = st.session_state.get(key, "netestat")
    if not status.get("tested"):
        st.caption(f"{label}: netestat")
    elif status.get("ok"):
        st.success(f"{label}: {label_state}")
    else:
        st.error(f"{label}: {label_state}")


def save_encrypted_passwords(adobe_password: str, shutter_password: str):
    payload = {}
    if SECURE_CONFIG_PATH.exists():
        try:
            payload = json.loads(SECURE_CONFIG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
    if adobe_password:
        payload["adobe_ftp_password"] = encrypt_password(adobe_password)
        config.save_to_env("FTP_ADOBE_PASS", payload["adobe_ftp_password"])
    if shutter_password:
        payload["shutter_ftp_password"] = encrypt_password(shutter_password)
        config.save_to_env("FTP_SHUTTER_PASS", payload["shutter_ftp_password"])
    SECURE_CONFIG_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def default_file_state(
    title="",
    description="",
    keywords="",
    adobe_cat="",
    shutter_cat="",
    shutter_cats=None,
    has_copy_space=False,
    camera_angle="",
    target_buyer="",
):
    cats = normalize_shutter_cats(shutter_cats or shutter_cat)
    return {
        "title": title,
        "description": description or title,
        "keywords": keywords,
        "adobe_cat": adobe_cat or ADOBE_CATEGORIES[0],
        "shutter_cats": cats,
        "shutter_cat": ", ".join(cats),
        "has_copy_space": bool(has_copy_space),
        "camera_angle": camera_angle or "",
        "target_buyer": target_buyer or "",
        "exif_done": False,
        "ftp_adobe_done": False,
        "ftp_shutter_done": False,
        "error_msg": None,
    }


def selected_platforms() -> set[str]:
    return set(st.session_state.get("selected_platforms", PLATFORMS))


def file_is_complete(meta: dict) -> bool:
    return file_is_complete_for_platforms(meta, selected_platforms())


def thumbnails_dir(folder: Path) -> Path:
    path = folder / THUMB_DIR_NAME
    os.makedirs(path, exist_ok=True)
    return path


def thumbnail_path_for(image_path: Path) -> Path:
    folder = Path(st.session_state.base_dir) if st.session_state.get("base_dir") else image_path.parent
    return thumbnails_dir(folder) / f"{image_path.stem}_Thumbnail.jpg"


def create_thumbnail(image_path: Path) -> Path:
    thumb_path = thumbnail_path_for(image_path)
    with Image.open(image_path) as img:
        preview = img.copy()
        preview.thumbnail((1024, 1024))
        if preview.mode in {"RGBA", "P"}:
            preview = preview.convert("RGB")
        preview.save(thumb_path, "JPEG", quality=90)
        preview.close()
    return thumb_path


def cleanup_thumbnails(folder: Path) -> int:
    temp_dir = folder / THUMB_DIR_NAME
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
        return 1
    return 0


def process_single_file(
    folder: Path,
    img_name: str,
    meta: dict,
    upload_shutterstock: bool = True,
    platforms: set[str] | None = None,
) -> dict:
    updated = dict(meta)
    errors = []
    original = folder / img_name
    platforms = platforms if platforms is not None else set(PLATFORMS)

    if not updated.get("exif_done"):
        try:
            if not original.exists():
                raise FileNotFoundError(f"Fișierul original lipsește: {original}")
            ok = exif_service.write_metadata(
                original,
                updated.get("title", ""),
                updated.get("description", "") or updated.get("title", ""),
                updated.get("keywords", ""),
                adobe_cat=updated.get("adobe_cat", ""),
            )
            if not ok:
                raise RuntimeError("ExifTool a returnat eșec.")
            updated["exif_done"] = True
        except Exception as e:
            errors.append(f"EXIF: {e}")
            updated["exif_done"] = False

    if updated.get("exif_done"):
        futures = {}
        with ThreadPoolExecutor(max_workers=2) as executor:
            if "adobe" in platforms and not updated.get("ftp_adobe_done"):
                futures["adobe"] = executor.submit(ftp_uploader.upload_adobe, original)
            if "shutterstock" in platforms and upload_shutterstock and not updated.get("ftp_shutter_done"):
                futures["shutter"] = executor.submit(ftp_uploader.upload_shutter, original)
            for target, future in futures.items():
                try:
                    result = future.result()
                    if isinstance(result, tuple):
                        ok, detail = result
                    else:
                        ok, detail = bool(result), ""
                    if target == "adobe":
                        updated["ftp_adobe_done"] = ok
                        if not ok:
                            errors.append(f"Adobe: upload eșuat ({detail})" if detail else "Adobe: upload eșuat")
                    else:
                        updated["ftp_shutter_done"] = ok
                        if not ok:
                            errors.append(
                                f"Shutterstock: upload eșuat ({detail})" if detail else "Shutterstock: upload eșuat"
                            )
                except Exception as e:
                    errors.append(f"{target}: {e}")

    updated["error_msg"] = "; ".join(errors) if errors else None
    return updated


def reset_wizard():
    folder = Path(st.session_state.base_dir) if st.session_state.get("base_dir") else None
    if folder:
        cleanup_thumbnails(folder)
    st.session_state.step = 0
    st.session_state.base_dir = ""
    st.session_state.metadata = {}
    st.session_state.custom_prompt = ""
    st.session_state.execution_results = {}
    st.session_state.csv_uploaded = False
    st.session_state.selected_platforms = list(PLATFORMS)


def init_state():
    if "step" not in st.session_state:
        st.session_state.step = 0
    if "base_dir" not in st.session_state:
        st.session_state.base_dir = ""
    if "metadata" not in st.session_state:
        st.session_state.metadata = {}
    if "custom_prompt" not in st.session_state:
        st.session_state.custom_prompt = ""
    if "execution_results" not in st.session_state:
        st.session_state.execution_results = {}
    if "selected_platforms" not in st.session_state:
        st.session_state.selected_platforms = list(PLATFORMS)
    if "category_usage" not in st.session_state:
        st.session_state.category_usage = {"adobe": {}, "shutter": {}}
    if "ftp_test_status" not in st.session_state:
        st.session_state.ftp_test_status = {
            "adobe": {"tested": False, "ok": False, "message": ""},
            "shutterstock": {"tested": False, "ok": False, "message": ""},
        }
    if "adobe_status" not in st.session_state:
        st.session_state.adobe_status = "netestat"
    if "shutter_status" not in st.session_state:
        st.session_state.shutter_status = "netestat"


init_state()

with st.sidebar:
    with st.expander("⚙️ Secure Settings"):
        st.caption("Salvează parolele criptat, apoi testează conexiunile.")
        with st.form("secure_passwords_form"):
            adobe_secret = st.text_input("Parolă Adobe FTP", type="password")
            shutter_secret = st.text_input("Parolă Shutterstock FTPS", type="password")
            if st.form_submit_button("Salvează parole criptate"):
                save_encrypted_passwords(adobe_secret, shutter_secret)
                st.success("Parolele au fost criptate în config.json.")
        if st.button("🔌 Test Conexiune Adobe", key="test_adobe"):
            run_ftp_credential_test("adobe")
        if st.button("🔌 Test Conexiune Shutterstock", key="test_shutter"):
            run_ftp_credential_test("shutterstock")
        render_ftp_test_status("adobe", "Adobe")
        render_ftp_test_status("shutterstock", "Shutterstock")

tab_process, tab_history, tab_settings = st.tabs(
    ["Procesare", "Istoric și export", "Setări"]
)

with tab_settings:
    st.header("Setări")
    st.caption("Valorile se salvează local în fișierul .env.")

    with st.form("settings_form"):
        col1, col2 = st.columns(2)
        with col1:
            s_url = st.text_input("Supabase URL", value=config.SUPABASE_URL)
            pt_key = st.text_input("PhotoTag API key", value=config.PHOTOTAG_API_KEY, type="password")
            p_dir = st.text_input("Cale director poze", value=config.PHOTOS_BASE_DIR)
        with col2:
            s_key = st.text_input("Supabase key", value=config.SUPABASE_KEY, type="password")

        if st.form_submit_button("Salvează setările"):
            config.save_to_env("SUPABASE_URL", s_url)
            config.save_to_env("SUPABASE_KEY", s_key)
            config.save_to_env("PHOTOTAG_API_KEY", pt_key)
            config.save_to_env("PHOTOS_BASE_DIR", p_dir)
            supabase_manager.reset_client()
            st.success("Setările au fost salvate.")
            st.rerun()

    st.subheader("⚙️ Setări credențiale FTP")
    col_adobe_card, col_shutter_card = st.columns(2)
    with col_adobe_card:
        with st.container(border=True):
            st.subheader("🟧 Adobe Stock")
            st.markdown(f"Protocol: SFTP/FTP PASV | Host: `{config.FTP_ADOBE_HOST or 'nesetat'}`")
            adobe_user = st.text_input(
                "Username Adobe",
                value=config.FTP_ADOBE_USER,
                key="adobe_user_input",
            )
            adobe_pass = st.text_input(
                "Password",
                type="password",
                key="adobe_pass_input",
            )
            col_save_adobe, col_test_adobe = st.columns(2)
            with col_save_adobe:
                if st.button("💾 Salvează Adobe", key="save_adobe"):
                    config.save_to_env("FTP_ADOBE_USER", adobe_user)
                    if adobe_pass:
                        save_encrypted_passwords(adobe_pass, "")
                    st.success("Adobe salvat.")
            with col_test_adobe:
                if st.button("🔌 Test Conexiune Adobe", key="test_adobe_btn"):
                    run_ftp_credential_test("adobe")
            st.markdown(f"Status: **{st.session_state.get('adobe_status', 'Netestat')}**")

    with col_shutter_card:
        with st.container(border=True):
            st.subheader("🟦 Shutterstock FTPS")
            st.markdown("Protocol: FTP-SSL (Explicit AUTH TLS) | Port: 21")
            shutter_user = st.text_input(
                "Username / Email",
                value=config.FTP_SHUTTER_USER or "damian@mad.ro",
                key="shutter_user_input",
            )
            shutter_pass = st.text_input(
                "Password",
                type="password",
                key="shutter_pass_input",
            )
            col_save_shutter, col_test_shutter = st.columns(2)
            with col_save_shutter:
                if st.button("💾 Salvează Shutterstock", key="save_shutter"):
                    config.save_to_env("FTP_SHUTTER_USER", shutter_user)
                    if shutter_pass:
                        save_encrypted_passwords("", shutter_pass)
                    st.success("Shutterstock salvat.")
            with col_test_shutter:
                if st.button("🔌 Test Conexiune Shutter", key="test_shutter_btn"):
                    run_ftp_credential_test("shutterstock")
            st.markdown(f"Status: **{st.session_state.get('shutter_status', 'Netestat')}**")

    col_status_1, col_status_2 = st.columns(2)
    with col_status_1:
        if config.SUPABASE_URL and config.SUPABASE_KEY:
            if supabase_manager.client:
                st.success("Client Supabase: inițializat")
            else:
                st.error("Client Supabase: eșuat")
        else:
            st.warning("Supabase neconfigurat.")
    with col_status_2:
        if config.PHOTOTAG_API_KEY:
            st.success("PhotoTag API key: prezent")
        else:
            st.warning("PhotoTag API key lipsă.")

with tab_history:
    st.header("Istoric și export")
    st.caption("Datele vin din tabela uploads din Supabase.")
    confirm_clear = st.checkbox("Confirm ștergerea definitivă a istoricului")
    if st.button("🗑️ Șterge Istoricul complet", type="secondary", disabled=not confirm_clear):
        if supabase_client.clear_history():
            st.success("Istoricul a fost șters cu succes!")
            st.rerun()
        else:
            st.error(f"Istoricul nu a putut fi șters: {supabase_client.last_error}")

    if not supabase_manager.client:
        st.info("Supabase nu este configurat.")
    else:
        try:
            date_istoric = supabase_client.fetch_history()
            if supabase_client.last_error:
                st.error(f"Istoricul nu a putut fi încărcat: {supabase_client.last_error}")
            elif not date_istoric:
                st.info("Nu există nicio imagine în istoric încă.")
            else:
                df = pd.DataFrame(date_istoric)

                def status_icon(value):
                    if str(value).lower() == "skipped":
                        return "➖"
                    if value is True or str(value).lower() in {"done", "success", "true"}:
                        return "✅"
                    return "❌"

                if "adobe_status" in df.columns:
                    df["adobe_status"] = df["adobe_status"].map(status_icon)
                if "shutter_status" in df.columns:
                    df["shutter_status"] = df["shutter_status"].map(status_icon)
                total = len(df)
                complete = int(df.get("ftp_done", pd.Series(dtype=bool)).fillna(False).astype(bool).sum())
                col_total, col_complete, col_failed = st.columns(3)
                col_total.metric("Fișiere", total)
                col_complete.metric("Finalizate", complete)
                col_failed.metric("Incomplete", total - complete)

                query = st.text_input("Filtrează după numele fișierului")
                visible_df = df
                if query and "filename" in df.columns:
                    visible_df = df[df["filename"].astype(str).str.contains(query, case=False, na=False)]
                preferred_columns = [
                    "filename", "phototag_status", "adobe_status", "shutter_status",
                    "api_done", "exif_done", "ftp_done", "updated_at",
                ]
                visible_columns = [column for column in preferred_columns if column in visible_df.columns]
                st.dataframe(visible_df[visible_columns], width="stretch", hide_index=True)
                csv_bytes = visible_df.to_csv(index=False).encode("utf-8")
                excel_buffer = io.BytesIO()
                visible_df.to_excel(excel_buffer, index=False, engine="openpyxl")
                col_csv, col_xlsx = st.columns(2)
                with col_csv:
                    st.download_button(
                        "Descarcă CSV",
                        csv_bytes,
                        "istoric.csv",
                        "text/csv",
                    )
                with col_xlsx:
                    st.download_button(
                        "Descarcă Excel",
                        excel_buffer.getvalue(),
                        "istoric.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
        except Exception as e:
            logger.error(f"Eroare la încărcarea istoricului: {e}")
            message = str(e)
            if "Could not find the table" in message or "PGRST205" in message:
                st.error("Tabela `uploads` nu există în Supabase.")
                st.caption("Rulează SQL-ul de mai jos în Supabase → SQL Editor, apoi reîncarcă pagina.")
                st.code(
                    """create table public.uploads (
    id uuid default gen_random_uuid() primary key,
    folder_path text not null,
    filename text not null,
    phototag_status text default 'pending',
    adobe_status text default 'pending',
    shutter_status text default 'pending',
    api_done boolean default false,
    exif_done boolean default false,
    ftp_done boolean default false,
    updated_at timestamp with time zone default timezone('utc'::text, now()) not null,
    unique (folder_path, filename)
);

alter table public.uploads enable row level security;

create policy "uploads_all" on public.uploads
    for all
    using (true)
    with check (true);""",
                    language="sql",
                )
            else:
                st.error(f"Nu s-au putut încărca datele din Supabase: {message}")

with tab_process:
    st.header("Procesare")
    step_labels = ["Destinații", "Context", "Validare", "Execuție", "Confirmare"]
    step_items = []
    for index, label in enumerate(step_labels):
        state = "done" if index < st.session_state.step else "active" if index == st.session_state.step else ""
        step_items.append(f'<div class="workflow-step {state}">{label}</div>')
    st.markdown(f'<div class="workflow-steps">{"".join(step_items)}</div>', unsafe_allow_html=True)

    if st.session_state.step == 0:
        st.subheader("Pasul 0: Destinații și folder")
        platform_labels = {key: value["label"] for key, value in PLATFORMS.items()}
        selected_labels = st.multiselect(
            "Platforme pentru acest batch",
            options=list(platform_labels.values()),
            default=[platform_labels[key] for key in st.session_state.selected_platforms if key in platform_labels],
            help="Selecția controlează upload-ul, retry-ul și statusul din Istoric.",
        )
        st.session_state.selected_platforms = [
            key for key, label in platform_labels.items() if label in selected_labels
        ]
        if st.button("Selectează folderul", type="primary", width="stretch"):
            if not st.session_state.selected_platforms:
                st.warning("Selectează cel puțin o platformă pentru batch.")
            else:
                path = get_directory_path()
                if path:
                    st.session_state.base_dir = path
                    st.session_state.metadata = {}
                    st.session_state.execution_results = {}
                    st.session_state.step = 1
                    st.rerun()
                else:
                    st.warning("Nu a fost selectat niciun folder.")

    elif st.session_state.step == 1:
        folder = Path(st.session_state.base_dir)
        images = list_original_images(folder)
        st.subheader("Pasul 1: Context AI și thumbnails")
        st.markdown(
            f'<div class="folder-context">Folder selectat <span class="folder-path" title="{html.escape(str(folder))}">'
            f'{html.escape(str(folder))}</span></div>',
            unsafe_allow_html=True,
        )
        st.metric("Imagini detectate", len(images))
        st.session_state.custom_prompt = st.text_area(
            "Context suplimentar pentru batch (opțional)",
            value=st.session_state.custom_prompt,
            help="Adaugă detalii despre locație, stil sau subiect pentru a ajuta AI-ul.",
        )
        st.info("Poți adăuga locația, stilul, subiectul sau intenția comercială. Contextul este trimis împreună cu thumbnail-ul.")

        col_back, col_run = st.columns([1, 2])
        with col_back:
            if st.button("Înapoi", width="stretch"):
                reset_wizard()
                st.rerun()
        with col_run:
            if st.button("Generează metadatele", type="primary", width="stretch"):
                if not images:
                    st.warning("Folderul nu conține imagini .jpg sau .jpeg.")
                else:
                    generated = {}
                    failed = []
                    progress = st.progress(0)
                    status = st.status("Se generează thumbnails și metadate...", expanded=True)
                    for idx, image_path in enumerate(images):
                        status.write(f"Procesez {image_path.name} ({idx + 1}/{len(images)})")
                        try:
                            thumb_path = create_thumbnail(image_path)
                        except Exception as e:
                            logger.error(f"Eroare thumbnail pentru {image_path.name}: {e}")
                            failed.append(f"{image_path.name}: nu s-a putut crea thumbnail-ul")
                            progress.progress((idx + 1) / len(images))
                            continue

                        result = phototag_service.generate_metadata(
                            thumb_path,
                            custom_prompt=st.session_state.custom_prompt,
                            image_index=idx,
                            master_brief=st.session_state.custom_prompt or "",
                        )
                        original_name = image_path.name
                        if result.get("success"):
                            generated[original_name] = default_file_state(
                                title=result.get("title", ""),
                                description=result.get("description", ""),
                                keywords=result.get("keywords", ""),
                                adobe_cat=result.get("adobe_cat", ""),
                                shutter_cats=result.get("shutter_cats") or result.get("shutter_cat", ""),
                                has_copy_space=result.get("has_copy_space", False),
                                camera_angle=result.get("camera_angle") or "eye-level",
                                target_buyer=result.get("target_buyer") or get_target_buyer(idx),
                            )
                            st.session_state["metadata"][original_name] = generated[original_name]
                            st.session_state[f"title_{original_name}"] = result.get("title", "")
                            st.session_state[f"kw_{original_name}"] = result.get("keywords", "")
                            supabase_manager.upsert_file_status(
                                str(folder),
                                original_name,
                                {"api_done": True},
                            )
                            if not result.get("title") and not result.get("keywords"):
                                st.warning(f"{original_name}: API-ul a reușit, dar nu a trimis titlu sau cuvinte cheie.")
                        else:
                            error_text = result.get("error", "eroare necunoscută")
                            failed.append(f"{original_name}: {error_text}")
                            st.error(f"{original_name}: {error_text}")
                        progress.progress((idx + 1) / len(images))

                    if generated:
                        st.session_state["metadata"] = generated
                        st.session_state.step = 2
                        if failed:
                            st.warning("Unele imagini nu au putut fi procesate. Continuăm cu cele reușite.")
                            for item in failed:
                                st.caption(item)
                        st.rerun()
                    else:
                        status.update(label="Generarea a eșuat", state="error")
                        st.error("Nu s-au putut genera metadate pentru nicio imagine.")
                        for item in failed:
                            st.caption(item)

    elif st.session_state.step == 2:
        folder = Path(st.session_state.base_dir)
        st.subheader("Pasul 2: Validare umană și editare")
        st.caption("Verifică titlul și cuvintele cheie înainte de scrierea EXIF.")

        if not st.session_state.metadata:
            st.warning("Nu există metadate de validat.")
            if st.button("Reia de la pasul 1"):
                st.session_state.step = 1
                st.rerun()
        else:
            for file_index, (nume_original, meta) in enumerate(st.session_state["metadata"].items()):
                original = folder / nume_original
                thumb = thumbnail_path_for(original)
                title_key = f"title_{nume_original}"
                tags_key = f"tags_{nume_original}"
                saved_title = meta.get("title", "") or ""
                saved_keywords = [
                    item.strip()
                    for item in str(meta.get("keywords", "")).split(",")
                    if item.strip()
                ]
                if title_key not in st.session_state:
                    st.session_state[title_key] = saved_title
                elif not st.session_state[title_key] and saved_title:
                    st.session_state[title_key] = saved_title
                if tags_key not in st.session_state:
                    st.session_state[tags_key] = saved_keywords
                elif not st.session_state[tags_key] and saved_keywords:
                    st.session_state[tags_key] = saved_keywords

                with st.container(border=True):
                    col_img, col_form = st.columns([1, 3])
                    with col_img:
                        preview = thumb if thumb.exists() else original
                        if preview.exists():
                            st.image(str(preview), caption=nume_original, use_container_width=True)
                        else:
                            st.caption(f"Thumbnail indisponibil: {nume_original}")
                    with col_form:
                        title = st.text_area(
                            "Titlu",
                            key=title_key,
                            max_chars=200,
                            height=110,
                        )
                        title_length = len(title or "")
                        st.markdown(
                            f'<div class="field-counter">{title_length} / 200 caractere</div>',
                            unsafe_allow_html=True,
                        )
                        file_meta = st.session_state["metadata"][nume_original]
                        if not file_meta.get("target_buyer"):
                            file_meta["target_buyer"] = get_target_buyer(file_index)
                        if not file_meta.get("camera_angle"):
                            file_meta["camera_angle"] = "eye-level"
                        st.caption(
                            f"🎯 Buyer: {file_meta['target_buyer']} | 📐 Angle: {file_meta['camera_angle']}"
                        )
                        if file_meta.get("has_copy_space"):
                            st.caption("🟢 Ad-Ready: Copy Space")

                        current_tags = st.session_state.get(tags_key, saved_keywords) or []
                        keywords_list = st.multiselect(
                            "Cuvinte cheie",
                            options=current_tags,
                            key=tags_key,
                            accept_new_options=True,
                            max_selections=50,
                            placeholder="Tastează și apasă Enter",
                        ) or []
                        keyword_count = len(keywords_list)
                        counter_class = "is-valid" if keyword_count <= 50 else "is-warning"
                        st.markdown(
                            f'<div class="field-counter {counter_class}">{keyword_count} / 50 cuvinte cheie</div>',
                            unsafe_allow_html=True,
                        )
                        keywords = ", ".join(keywords_list)
                        adobe_cat = meta.get("adobe_cat") or ADOBE_CATEGORIES[0]
                        if "adobe" in selected_platforms():
                            adobe_index = ADOBE_CATEGORIES.index(adobe_cat) if adobe_cat in ADOBE_CATEGORIES else 0
                            adobe_cat = st.selectbox(
                                "Categorie Adobe",
                                ADOBE_CATEGORIES,
                                index=adobe_index,
                                key=f"adobe_cat_{nume_original}",
                            )
                        shutter_cats = normalize_shutter_cats(
                            meta.get("shutter_cats") or meta.get("shutter_cat")
                        )
                        if "shutterstock" in selected_platforms():
                            st.markdown('<div class="shutter-box">', unsafe_allow_html=True)
                            selected_shutter_cats = st.multiselect(
                                "Categorii Shutterstock (exact 2)",
                                SHUTTERSTOCK_CATEGORIES,
                                default=shutter_cats,
                                max_selections=2,
                                key=f"shutter_cats_{nume_original}",
                            )
                            if len(selected_shutter_cats) != 2:
                                st.caption("Alege exact 2 categorii Shutterstock.")
                            else:
                                shutter_cats = selected_shutter_cats
                            st.markdown("</div>", unsafe_allow_html=True)
                        st.session_state["metadata"][nume_original]["title"] = title
                        st.session_state["metadata"][nume_original]["description"] = title
                        st.session_state["metadata"][nume_original]["keywords"] = keywords
                        st.session_state["metadata"][nume_original]["adobe_cat"] = adobe_cat
                        st.session_state["metadata"][nume_original]["shutter_cats"] = shutter_cats
                        st.session_state["metadata"][nume_original]["shutter_cat"] = ", ".join(shutter_cats)

            col_back, col_next = st.columns([1, 2])
            with col_back:
                if st.button("Înapoi la context"):
                    st.session_state.step = 1
                    st.rerun()
            with col_next:
                if st.button("✅ Confirmă batch-ul (Scrie EXIF & Urcă FTP)", type="primary"):
                    st.session_state.step = 3
                    st.rerun()

    elif st.session_state.step == 3:
        folder = Path(st.session_state.base_dir)
        st.subheader("Pasul 3: Execuție")
        st.caption("Se procesează doar pașii încă nerezolvați, cu upload paralel.")

        pending = {
            name: meta
            for name, meta in st.session_state.metadata.items()
            if not file_is_complete(meta)
        }
        progress = st.progress(0)
        with st.spinner("Se scriu metadatele și se uploadează pe FTP. Te rugăm să aștepți..."):
            status = st.status("Se scriu metadatele și se urcă fișierele...", expanded=True)
            if pending:
                completed = 0
                with ThreadPoolExecutor(max_workers=3) as executor:
                    futures = {
                        executor.submit(
                            process_single_file,
                            folder,
                            name,
                            meta,
                            False,
                            selected_platforms(),
                        ): name
                        for name, meta in pending.items()
                    }
                    for future in as_completed(futures):
                        img_name = futures[future]
                        try:
                            updated = future.result()
                        except Exception as e:
                            updated = dict(st.session_state.metadata[img_name])
                            updated["error_msg"] = str(e)
                        st.session_state.metadata[img_name] = updated
                        status.write(f"{img_name}: {updated.get('error_msg') or 'ok'}")
                        completed += 1
                        progress.progress(completed / max(len(pending), 1))

            csv_ok = False
            shutter_images_ready = "shutterstock" in selected_platforms() and all(
                meta.get("exif_done")
                for meta in st.session_state.metadata.values()
            )
            if shutter_images_ready:
                batch_items = [
                    {
                        "image_path": folder / filename,
                        "description": meta.get("description") or meta.get("title") or "",
                        "keywords": meta.get("keywords") or [],
                        "categories": meta.get("shutter_cats") or meta.get("shutter_cat") or [],
                    }
                    for filename, meta in st.session_state.metadata.items()
                ]
                csv_ok, csv_detail = ftp_uploader.upload_batch_with_csv(
                    batch_items,
                    folder,
                    upload_images=True,
                )
                for meta in st.session_state.metadata.values():
                    meta["ftp_shutter_done"] = csv_ok
                    if not csv_ok:
                        current_error = meta.get("error_msg")
                        shutter_error = f"Shutterstock batch: {csv_detail}"
                        meta["error_msg"] = f"{current_error}; {shutter_error}" if current_error else shutter_error
                status.write(
                    f"Shutterstock batch: {'imagini urcate; CSV pregătit pentru portal' if csv_ok else f'upload eșuat ({csv_detail})'}"
                )
            elif "shutterstock" in selected_platforms():
                status.write("Shutterstock batch: amânat până când metadatele sunt scrise în toate imaginile")
            else:
                csv_ok = True
                status.write("Shutterstock: omis pentru acest batch")
            st.session_state.csv_uploaded = csv_ok
            status.update(label="Execuția s-a încheiat", state="complete")

        st.session_state.step = 4
        st.rerun()

    elif st.session_state.step == 4:
        folder = Path(st.session_state.base_dir)
        st.subheader("Pasul 4: Confirmare și cleanup")
        st.info("Verifică statusul fiecărui fișier. Reîncearcă doar ce a eșuat, apoi confirmă cleanup-ul.")

        csv_path = folder / "shutterstock_upload.csv"
        if "shutterstock" in selected_platforms() and csv_path.exists():
            st.markdown(
                """
                <div class="portal-notice">
                    <strong>Pas final Shutterstock.</strong> Platforma nu aplică metadata CSV prin FTPS.
                    Importă fișierul în Contributor Portal pentru cele două categorii.
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.download_button(
                "Descarcă CSV Shutterstock",
                data=csv_path.read_bytes(),
                file_name=csv_path.name,
                mime="text/csv",
            )

        failed_names = [
            name
            for name, meta in st.session_state.metadata.items()
            if not file_is_complete(meta)
        ]
        select_all = st.checkbox("Selectează toate erorile", key="select_all_errors")
        if select_all:
            for img_name in failed_names:
                st.session_state[f"chk_{img_name}"] = True

        selected_for_retry = []
        for img_name, meta in st.session_state.metadata.items():
            success = file_is_complete(meta)
            col_status, col_check = st.columns([4, 1])
            with col_status:
                if success:
                    st.markdown(
                        f'<div class="result-row success"><span class="result-name">{html.escape(img_name)}</span>'
                        '<span class="result-state">Finalizat</span></div>',
                        unsafe_allow_html=True,
                    )
                else:
                    error_text = meta.get("error_msg") or "incomplet"
                    st.markdown(
                        f'<div class="result-row error"><span class="result-name">{html.escape(img_name)}</span>'
                        f'<span class="result-state">{html.escape(str(error_text))}</span></div>',
                        unsafe_allow_html=True,
                    )
            with col_check:
                if not success:
                    checked = st.checkbox("Selectează pentru reîncercare", key=f"chk_{img_name}")
                    if checked:
                        selected_for_retry.append(img_name)

        if st.button("🔄 Reîncearcă selectate"):
            targets = selected_for_retry
            if not targets:
                st.warning("Nu ai selectat niciun fișier cu erori.")
            else:
                with st.spinner("Se reîncearcă fișierele selectate..."):
                    for img_name in targets:
                        meta = st.session_state.metadata[img_name]
                        if file_is_complete(meta):
                            continue
                        st.session_state.metadata[img_name] = process_single_file(
                            folder,
                            img_name,
                            meta,
                            False,
                            selected_platforms(),
                        )
                    if "shutterstock" in selected_platforms() and all(
                        meta.get("exif_done")
                        for meta in st.session_state.metadata.values()
                    ):
                        batch_items = [
                            {
                                "image_path": folder / filename,
                                "description": meta.get("description") or meta.get("title") or "",
                                "keywords": meta.get("keywords") or [],
                                "categories": meta.get("shutter_cats") or meta.get("shutter_cat") or [],
                            }
                            for filename, meta in st.session_state.metadata.items()
                        ]
                        csv_ok, csv_detail = ftp_uploader.upload_batch_with_csv(
                            batch_items,
                            folder,
                            upload_images=True,
                        )
                        for meta in st.session_state.metadata.values():
                            meta["ftp_shutter_done"] = csv_ok
                        st.session_state.csv_uploaded = csv_ok
                        if not csv_ok:
                            st.error(f"CSV Shutterstock nu s-a putut urca: {csv_detail}")
                st.rerun()

        if st.button("✅ Confirm submiterea (Cleanup)", type="primary"):
            lista_dictionare = []
            for img_name, meta in st.session_state.metadata.items():
                lista_dictionare.append({
                    "folder_path": str(folder),
                    "filename": img_name,
                    "adobe_status": bool(meta.get("ftp_adobe_done")),
                    "shutter_status": bool(meta.get("ftp_shutter_done")),
                    "selected_platforms": list(selected_platforms()),
                    "metadata": {
                        "title": meta.get("title", ""),
                        "keywords": meta.get("keywords", ""),
                        "adobe_cat": meta.get("adobe_cat", ""),
                        "shutter_cat": meta.get("shutter_cat", ""),
                    },
                    "error_msg": meta.get("error_msg"),
                    "exif_done": bool(meta.get("exif_done")),
                })
            if lista_dictionare:
                ok = supabase_client.log_batch(lista_dictionare)
                if not ok:
                    st.error(f"Istoricul nu a putut fi salvat: {supabase_client.last_error}")
                    st.stop()
            cleanup_thumbnails(folder)
            csv_path = folder / "shutterstock_upload.csv"
            if csv_path.exists():
                try:
                    os.remove(csv_path)
                except OSError as e:
                    logger.error(f"Nu s-a putut șterge CSV-ul Shutterstock: {e}")
            st.success("Submiterea a fost confirmată. Folderul temporar a fost șters.")
            reset_wizard()
            st.rerun()
