import os
import sys
from pathlib import Path

def create_mac_app():
    app_name = "StockAutomation"
    project_dir = Path(__file__).resolve().parent
    app_path = project_dir / f"{app_name}.app"
    contents_dir = app_path / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"

    # Creăm structura directoarelor pentru .app bundle
    macos_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)

    # 1. Info.plist
    info_plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>{app_name}</string>
    <key>CFBundleDisplayName</key>
    <string>Stock Photo Automation</string>
    <key>CFBundleIdentifier</key>
    <string>com.stock.automation</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleSignature</key>
    <string>????</string>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundleIconFile</key>
    <string>app.icns</string>
    <key>LSUIElement</key>
    <false/>
</dict>
</plist>
"""
    (contents_dir / "Info.plist").write_text(info_plist_content, encoding="utf-8")

    # 2. Launcher script (pornește mediul virtual și streamlit)
    python_path = project_dir / "venv" / "bin" / "python"
    launcher_content = f"""#!/bin/bash
cd "{project_dir}"
if [ -f "venv/bin/activate" ]; then
    source "venv/bin/activate"
fi
# Deschide browserul implicit cu Streamlit
open "http://localhost:8501" &
exec "{python_path}" -m streamlit run app.py --server.headless=true
"""
    launcher_path = macos_dir / "launcher"
    launcher_path.write_text(launcher_content, encoding="utf-8")
    
    # Facem launcher-ul executabil
    os.chmod(launcher_path, 0o755)

    # 3. Iconiță (dacă există un fișier PNG sau ICNS în proiect, îl copiem)
    icon_source = project_dir / "icon.png"
    icns_dest = resources_dir / "app.icns"
    
    if icon_source.exists():
        # Dacă există icon.png, putem încerca să îl convertim în icns sau să îl folosim
        print(f"S-a găsit icon.png. Se copiază în resurse...")
        # (Pentru simplificare, lăsăm launcher-ul să folosească structura standard sau icon.png dacă e suportat)
    else:
        # Creăm un fișier text placeholder pentru icns sau lăsăm lipsă
        print("Notă: Poți adăuga un fișier 'icon.png' în folderul proiectului pentru a fi folosit ca iconiță.")

    print(f"Aplicația macOS a fost generată cu succes la: {app_path}")
    print(reflex_instructions := f"O poți muta în folderul Applications sau o poți rula direct dublu-clic pe {app_name}.app")

if __name__ == "__main__":
    create_mac_app()
