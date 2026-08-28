import socket
import ssl
import time
from ftplib import FTP, FTP_TLS, error_perm
from pathlib import Path
from urllib.parse import urlparse
import concurrent.futures

import paramiko

import config
from services.crypto_service import decrypt_password
from services.csv_service import generate_shutterstock_csv
from utils.logger import get_logger

logger = get_logger("ftp_service")

SHUTTER_FTPS_HOST = "ftps.shutterstock.com"
SHUTTER_FTPS_PORT = 21
SHUTTER_FTPS_USER = "damian@mad.ro"
ADOBE_SFTP_HOST = "sftp.contributor.adobestock.com"
ADOBE_SFTP_PORT = 22


def _parse_host(host: str) -> tuple[str, str, int]:
    raw = (host or "").strip()
    if not raw:
        return "", "ftp", 21
    if "://" not in raw:
        return raw, "ftp", 21
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "ftp").lower()
    hostname = parsed.hostname or raw
    if scheme == "sftp":
        return hostname, "sftp", parsed.port or 22
    if scheme in {"ftps", "ftp+tls"}:
        return hostname, "ftps", parsed.port or 21
    return hostname, "ftp", parsed.port or 21


def _resolve_password(raw: str) -> str:
    return decrypt_password(raw or "")


def _safe_disconnect(client) -> None:
    if client is None:
        return
    try:
        client.quit()
        return
    except Exception:
        pass
    try:
        client.close()
    except Exception:
        pass


def get_robust_ssl_context() -> ssl.SSLContext:
    return ssl._create_unverified_context()


def _ssl_context() -> ssl.SSLContext:
    return get_robust_ssl_context()


def get_verified_host(service_type: str) -> str:
    stype = (service_type or "").strip().lower()
    if "shutter" in stype:
        return SHUTTER_FTPS_HOST
    if "adobe" in stype:
        return ADOBE_SFTP_HOST
    raise ValueError(f"Unknown or invalid service type: {service_type}")


def verify_ftp_credentials(
    service_type: str,
    username: str,
    decrypted_password: str,
) -> tuple[bool, str]:
    service = (service_type or "").strip().lower()
    user = (username or "").strip()
    if not user or not decrypted_password:
        return False, "Credențiale invalide (Utilizator sau parolă greșită)."

    try:
        host = get_verified_host(service)
    except ValueError:
        return False, "Eroare de rețea / Conexiune: serviciu necunoscut."
    if not host:
        return False, "Eroare de rețea / Conexiune: host invalid."

    client = None
    try:
        if "adobe" in service:
            transport = paramiko.Transport((host, ADOBE_SFTP_PORT))
            client = transport
            transport.connect(username=user, password=decrypted_password)
            return True, "Conexiune reușită!"

        context = _ssl_context()
        client = FTP_TLS(context=context, timeout=20)
        client.connect(host, 21)
        client.login(user, decrypted_password)
        client.prot_p()
        client.set_pasv(True)
        return True, "Conexiune reușită!"
    except error_perm as e:
        error_str = str(e)
        if "530" in error_str:
            return False, "Credențiale invalide (Utilizator sau parolă greșită)."
        return False, f"Eroare permisiune server: {error_str}"
    except ssl.SSLError as e:
        return False, f"Eroare SSL/TLS Handshake: {str(e)}"
    except Exception as e:
        return False, f"Eroare de rețea / Conexiune: {str(e)}"
    finally:
        if isinstance(client, paramiko.Transport):
            client.close()
        else:
            _safe_disconnect(client)


class FtpUploader:
    def _upload_ftp(self, host: str, user: str, passwd: str, image_path: Path, port: int = 21) -> bool:
        ftp = FTP()
        try:
            ftp.connect(host, port, timeout=60)
            ftp.login(user, passwd)
            ftp.set_pasv(True)
            with open(image_path, "rb") as f:
                ftp.storbinary(f"STOR {image_path.name}", f, blocksize=131072)
            ftp.quit()
            return True
        except Exception as e:
            logger.error(f"FTP PASV eșuat pe {host}:{port} pentru {image_path.name}: {e}")
            try:
                ftp.close()
            except Exception:
                pass
            raise

    def _upload_ftps(self, host: str, user: str, passwd: str, image_path: Path, port: int = 21) -> bool:
        if not host:
            raise ValueError("Host FTPS invalid sau gol.")
        ftp = FTP_TLS(context=_ssl_context(), timeout=20)
        try:
            ftp.connect(host, port)
            ftp.login(user, passwd)
            ftp.prot_p()
            ftp.set_pasv(True)
            with open(image_path, "rb") as f:
                ftp.storbinary(f"STOR {image_path.name}", f, blocksize=131072)
            ftp.quit()
            return True
        except Exception as e:
            logger.error(f"FTPS eșuat pe {host}:{port} pentru {image_path.name}: {e}")
            try:
                ftp.close()
            except Exception:
                pass
            raise

    def _upload_sftp(self, host: str, user: str, passwd: str, image_path: Path, port: int = 22) -> bool:
        transport = paramiko.Transport((host, port))
        transport.connect(username=user, password=passwd)
        sftp = paramiko.SFTPClient.from_transport(transport)
        try:
            sftp.put(str(image_path), image_path.name)
        finally:
            sftp.close()
            transport.close()
        return True

    def _upload_single(self, host: str, user: str, passwd: str, image_path: Path, force_protocol: str = "") -> tuple[bool, str]:
        hostname, protocol, port = _parse_host(host)
        if force_protocol:
            protocol = force_protocol
        if not hostname or not user or not passwd:
            detail = f"Lipsesc credențialele FTP/SFTP pentru host: {host}"
            logger.error(detail)
            return False, detail

        last_error = None
        for attempt in range(3):
            try:
                if protocol == "sftp":
                    self._upload_sftp(hostname, user, passwd, image_path, port)
                elif protocol == "ftps":
                    self._upload_ftps(hostname, user, passwd, image_path, port)
                else:
                    self._upload_ftp(hostname, user, passwd, image_path, port)
                logger.info(
                    f"Upload reușit {image_path.name} -> {protocol}://{hostname} (încercarea {attempt + 1})"
                )
                return True, ""
            except Exception as e:
                last_error = e
                wait_seconds = 2 ** attempt
                logger.warning(
                    f"Upload {protocol} eșuat ({attempt + 1}/3) {hostname} {image_path.name}: {e}. Retry în {wait_seconds}s"
                )
                if attempt < 2:
                    time.sleep(wait_seconds)
        detail = str(last_error) if last_error else "Upload eșuat"
        logger.error(f"Upload eșuat pentru {image_path.name} pe {hostname}: {detail}")
        return False, detail

    def upload_adobe(self, image_path: Path) -> tuple[bool, str]:
        password = _resolve_password(config.FTP_ADOBE_PASS)
        try:
            host = get_verified_host("adobe")
            return self._upload_single(
                f"sftp://{host}:{ADOBE_SFTP_PORT}",
                config.FTP_ADOBE_USER,
                password,
                image_path,
                force_protocol="sftp",
            )
        except Exception as e:
            detail = str(e)
            logger.error(f"Adobe upload exception pentru {image_path.name}: {detail}")
            return False, detail

    def upload_shutter(self, image_path: Path) -> tuple[bool, str]:
        password = _resolve_password(config.FTP_SHUTTER_PASS)
        user = config.FTP_SHUTTER_USER or SHUTTER_FTPS_USER
        host = get_verified_host("shutterstock")
        return self._upload_single(
            f"ftps://{host}:{SHUTTER_FTPS_PORT}",
            user,
            password,
            image_path,
            force_protocol="ftps",
        )

    def upload_image_concurrently(self, image_path: Path) -> dict:
        results = {"adobe": False, "shutter": False, "adobe_error": "", "shutter_error": ""}
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_adobe = executor.submit(self.upload_adobe, image_path)
            future_shutter = executor.submit(self.upload_shutter, image_path)
            try:
                ok, detail = future_adobe.result()
                results["adobe"] = ok
                results["adobe_error"] = "" if ok else detail
            except Exception as e:
                logger.error(f"Eroare thread Adobe: {e}")
                results["adobe_error"] = str(e)
            try:
                ok, detail = future_shutter.result()
                results["shutter"] = ok
                results["shutter_error"] = "" if ok else detail
            except Exception as e:
                logger.error(f"Eroare thread Shutterstock: {e}")
                results["shutter_error"] = str(e)
        return results

    def upload_to_shutterstock(self, file_path: Path) -> tuple[bool, str]:
        return self.upload_shutter(file_path)

    def upload_batch_with_csv(
        self,
        image_paths_and_metadata: list[dict],
        output_dir: Path,
        upload_images: bool = True,
    ) -> tuple[bool, str]:
        csv_path = output_dir / "shutterstock_upload.csv"
        ftp = None
        try:
            csv_items = []
            image_paths = []
            for item in image_paths_and_metadata:
                image_path = Path(item.get("image_path") or item.get("filename") or "")
                csv_items.append({
                    "filename": image_path.name,
                    "description": item.get("description", ""),
                    "keywords": item.get("keywords", []),
                    "categories": item.get("categories", []),
                })
                if upload_images:
                    if not image_path.is_file():
                        return False, f"Fișierul nu există: {image_path}"
                    image_paths.append(image_path)

            generate_shutterstock_csv(csv_items, str(csv_path))

            host = get_verified_host("shutterstock")
            user = config.FTP_SHUTTER_USER or SHUTTER_FTPS_USER
            password = _resolve_password(config.FTP_SHUTTER_PASS)
            if not host or not user or not password:
                return False, "Lipsesc credențialele Shutterstock FTPS."

            ftp = FTP_TLS(context=_ssl_context(), timeout=20)
            ftp.connect(host, SHUTTER_FTPS_PORT)
            ftp.login(user, password)
            ftp.prot_p()
            ftp.set_pasv(True)

            for image_path in image_paths:
                with open(image_path, "rb") as image_file:
                    response = ftp.storbinary(
                        f"STOR {image_path.name}",
                        image_file,
                        blocksize=131072,
                    )
                logger.info("Shutterstock STOR %s: %s", image_path.name, response)

            logger.info(
                "Batch Shutterstock încărcat: %s imagini; CSV pregătit local la %s",
                len(image_paths),
                csv_path,
            )
            return True, str(csv_path)
        except Exception as e:
            detail = str(e)
            logger.error("Upload batch Shutterstock eșuat: %s", detail)
            return False, detail
        finally:
            _safe_disconnect(ftp)


ftp_uploader = FtpUploader()
