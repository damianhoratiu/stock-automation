from __future__ import annotations

import os
from pathlib import Path
import config
from utils.logger import get_logger

logger = get_logger("folder_scanner")

class FolderScanner:
    @property
    def base_dir(self) -> Path:
        try:
            import streamlit as st
            if "base_dir" in st.session_state and st.session_state["base_dir"]:
                return Path(st.session_state["base_dir"])
        except Exception:
            pass
        return Path(config.PHOTOS_BASE_DIR)

    def list_folders(self) -> list[str]:
        """Listează toate directoarele din folderul de bază, ignorând cele care încep cu '.'."""
        b_dir = self.base_dir
        if not b_dir.exists() or not b_dir.is_dir():
            logger.warning(f"Base directory {b_dir} does not exist.")
            return []
        
        try:
            return [
                str(entry.relative_to(b_dir))
                for entry in b_dir.iterdir()
                if entry.is_dir() and not entry.name.startswith(".")
            ]
        except Exception as e:
            logger.error(f"Error listing folders: {e}")
            return []

    def get_context(self, folder_path: str) -> str:
        """Citește conținutul fișierului context.txt din folderul specificat, dacă există."""
        full_path = self.base_dir / folder_path / "context.txt"
        if full_path.exists() and full_path.is_file():
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception as e:
                logger.error(f"Error reading context.txt in {folder_path}: {e}")
        return ""

    def get_images(self, folder_path: str) -> list[str]:
        """Returnează lista fișierelor imagini (.jpg, .jpeg) din folder, ignorând fișierele ce încep cu '.'."""
        full_path = self.base_dir / folder_path
        if not full_path.exists() or not full_path.is_dir():
            return []
        
        valid_extensions = {".jpg", ".jpeg"}
        try:
            return [
                entry.name
                for entry in full_path.iterdir()
                if entry.is_file() 
                and not entry.name.startswith(".")
                and entry.suffix.lower() in valid_extensions
            ]
        except Exception as e:
            logger.error(f"Error scanning images in {folder_path}: {e}")
            return []

folder_scanner = FolderScanner()
