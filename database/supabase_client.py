from supabase import create_client, Client
import config
from utils.logger import get_logger

logger = get_logger("supabase_client")

class SupabaseManager:
    def __init__(self):
        self._client: Client = None
        self.last_error = ""

    def reset_client(self):
        """Resetează instanța clientului pentru a forța re-conectarea cu noile setări."""
        self._client = None
        logger.info("Supabase client instance reset.")

    @property
    def client(self) -> Client:
        """Lazy loading pentru clientul Supabase folosind config.SUPABASE_URL și config.SUPABASE_KEY."""
        if not self._client:
            if not config.SUPABASE_URL or not config.SUPABASE_KEY:
                logger.warning("Supabase URL or Key is missing.")
                return None
            try:
                self._client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
                logger.info("Supabase client initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client: {e}")
                return None
        return self._client

    def is_connected(self) -> bool:
        """Verifică dacă clientul este activ și conectat, fără a produce crash în caz de eroare."""
        return self.client is not None

    def fetch_uploads(self):
        return self.fetch_history()

    def fetch_history(self, limit=200):
        self.last_error = ""
        if not self.client:
            self.last_error = "Clientul Supabase nu este inițializat."
            logger.warning(self.last_error)
            return []
        try:
            response = (
                self.client.table("uploads")
                .select("*")
                .order("updated_at", desc=True)
                .limit(limit)
                .execute()
            )
            return response.data or []
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Eroare la fetch_history: {e}")
            return []

    def log_batch(self, records: list):
        self.last_error = ""
        if not self.client:
            self.last_error = "Clientul Supabase nu este inițializat."
            logger.warning(f"{self.last_error} Bulk insert anulat.")
            return False
        if not records:
            return True
        try:
            compatible_records = []
            for record in records:
                adobe_done = bool(record.get("adobe_status"))
                shutter_done = bool(record.get("shutter_status"))
                platforms = set(record.get("selected_platforms") or ("adobe", "shutterstock"))
                compatible_records.append({
                    "folder_path": record.get("folder_path", ""),
                    "filename": record.get("filename", ""),
                    "phototag_status": "done",
                    "adobe_status": "done" if adobe_done else ("failed" if "adobe" in platforms else "skipped"),
                    "shutter_status": "done" if shutter_done else ("failed" if "shutterstock" in platforms else "skipped"),
                    "api_done": True,
                    "exif_done": bool(record.get("exif_done", True)),
                    "ftp_done": all(
                        adobe_done if platform == "adobe" else shutter_done
                        for platform in platforms
                    ),
                })
            self.client.table("uploads").upsert(
                compatible_records,
                on_conflict="folder_path,filename",
            ).execute()
            logger.info(f"Upsert reușit: {len(compatible_records)} înregistrări.")
            return True
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Eroare la log_batch: {e}")
            return False

    def clear_history(self):
        self.last_error = ""
        if not self.client:
            self.last_error = "Clientul Supabase nu este inițializat."
            logger.warning(f"{self.last_error} Ștergerea istoricului a fost anulată.")
            return False
        try:
            self.client.table("uploads").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
            logger.info("Istoricul uploads a fost șters.")
            return True
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Eroare la clear_history: {e}")
            return False

    def get_file_status(self, folder_path: str, filename: str):
        if not self.client:
            return None
        try:
            response = self.client.table("uploads") \
                .select("*") \
                .eq("folder_path", folder_path) \
                .eq("filename", filename) \
                .execute()
            data = response.data
            return data[0] if data else None
        except Exception as e:
            logger.error(f"Error fetching file status: {e}")
            return None

    def upsert_file_status(self, folder_path: str, filename: str, status_data: dict):
        """
        Inserează sau actualizează starea fișierului.
        States: api_done, exif_done, ftp_done.
        """
        if not self.client:
            logger.warning("Supabase client not available. Skipping upsert.")
            return
        try:
            record = {
                "folder_path": folder_path,
                "filename": filename,
                **status_data
            }
            self.client.table("uploads").upsert(record, on_conflict="folder_path,filename").execute()
        except Exception as e:
            logger.error(f"Error upserting file status: {e}")

supabase_manager = SupabaseManager()
supabase_client = supabase_manager
