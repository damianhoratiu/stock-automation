# Stock automation

Streamlit app that generates microstock metadata (PhotoTag.AI), writes IPTC/XMP with ExifTool, and uploads images to Adobe Stock (SFTP) and Shutterstock (FTPS). Optional Supabase logging for upload history.

## Setup

1. Install [ExifTool](https://exiftool.org/) (required for metadata writing).

2. Create a virtualenv and install Python dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and fill in PhotoTag, FTP, and (optional) Supabase credentials. FTP passwords can also be saved encrypted from the app Settings tab.

4. Run the app:

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501). Choose platforms (Adobe / Shutterstock), pick a folder of `.jpg` / `.jpeg` files, generate metadata, review, then write EXIF and upload.
