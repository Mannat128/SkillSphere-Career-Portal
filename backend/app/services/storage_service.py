import logging
import hashlib
import shutil
from pathlib import Path
from typing import Any, Optional

from app.core.config import settings
from app.core.exceptions import SkillSphereException

logger = logging.getLogger(__name__)

PRIVATE_RECORDING_DIR = (
    Path(settings.UPLOAD_DIR).resolve().parent / "private_proctoring_recordings"
).resolve()
CLOUDINARY_REFERENCE_PREFIX = "cloudinary://"
S3_REFERENCE_PREFIX = "s3://"


class StorageService:
    """Private recording storage for local development, legacy S3, and Cloudinary."""

    @classmethod
    def get_backend_name(cls) -> str:
        return (settings.STORAGE_BACKEND or "cloudinary").lower().strip()

    @classmethod
    def is_cloudinary_configured(cls) -> bool:
        return bool(
            settings.CLOUDINARY_CLOUD_NAME
            and settings.CLOUDINARY_API_KEY
            and settings.CLOUDINARY_API_SECRET
        )

    @classmethod
    def _configure_cloudinary(cls):
        if not cls.is_cloudinary_configured():
            raise SkillSphereException(
                503,
                "Cloudinary recording storage is not configured in the backend environment.",
            )
        try:
            import cloudinary
        except ImportError as exc:
            raise SkillSphereException(
                500,
                "The Cloudinary Python SDK is required. Install the backend requirements.",
            ) from exc

        return cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            secure=True,
        )

    @classmethod
    def _get_s3_client(cls, backend_override: Optional[str] = None):
        """Retain S3 support for existing s3:// references, not as the active provider."""
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise SkillSphereException(500, "The boto3 package is required for legacy S3 recording references.") from exc

        backend = backend_override or cls.get_backend_name()
        if backend != "s3":
            raise SkillSphereException(500, "S3 storage is not selected.")
        if not all((settings.AWS_S3_BUCKET_NAME, settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY)):
            raise SkillSphereException(503, "Legacy S3 configuration is incomplete; AWS_S3_BUCKET_NAME and credentials are required.")

        kwargs = {
            "service_name": "s3",
            "region_name": settings.AWS_REGION or "us-east-1",
            "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
            "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
            "config": Config(signature_version="s3v4"),
        }
        if settings.AWS_S3_ENDPOINT_URL:
            kwargs["endpoint_url"] = settings.AWS_S3_ENDPOINT_URL
        return boto3.client(**kwargs)

    @classmethod
    def save_recording_with_metadata(
        cls,
        source_path: Path,
        destination_filename: str,
        content_type: str = "video/webm",
        idempotency_key: Optional[str] = None,
        content_sha256: Optional[str] = None,
    ) -> dict[str, Any]:
        backend = cls.get_backend_name()
        if backend not in {"local", "s3", "cloudinary"}:
            raise SkillSphereException(500, "Unsupported recording storage backend. Choose local, s3, or cloudinary.")

        if backend == "cloudinary":
            cls._configure_cloudinary()
            import cloudinary.api
            import cloudinary.uploader

            key = idempotency_key or Path(destination_filename).stem
            safe_key = "".join(character for character in str(key) if character.isalnum() or character in "-_/")
            if not safe_key or safe_key.startswith("/") or ".." in safe_key:
                raise SkillSphereException(400, "Invalid recording upload identifier.")
            public_id = f"skillsphere/proctoring/{safe_key}"
            if content_sha256:
                digest = content_sha256
            else:
                hasher = hashlib.sha256()
                with source_path.open("rb") as source_stream:
                    for block in iter(lambda: source_stream.read(1024 * 1024), b""):
                        hasher.update(block)
                digest = hasher.hexdigest()

            def read_existing_asset():
                try:
                    return cloudinary.api.resource(
                        public_id,
                        resource_type="video",
                        type="authenticated",
                        context=True,
                    )
                except Exception as lookup_error:
                    # cloudinary.exceptions.NotFound in the official SDK does
                    # not expose an http_code/code attribute. Recognize that
                    # documented exception explicitly, while retaining support
                    # for SDK/API response wrappers that do expose a 404 code.
                    try:
                        from cloudinary.exceptions import NotFound as CloudinaryNotFound
                    except ImportError:
                        CloudinaryNotFound = ()
                    is_not_found = (
                        isinstance(lookup_error, CloudinaryNotFound)
                        or getattr(lookup_error, "http_code", None) == 404
                        or getattr(lookup_error, "code", None) == 404
                        or getattr(lookup_error, "status_code", None) == 404
                    )
                    if is_not_found:
                        return None
                    logger.warning("Cloudinary recording reconciliation lookup failed (%s).", type(lookup_error).__name__)
                    raise SkillSphereException(
                        502,
                        "Cloudinary recording reconciliation is unavailable. Verify that the API key can read authenticated video asset metadata; the recording was not marked complete.",
                    ) from lookup_error

            def metadata_from_resource(resource):
                context = resource.get("context") or {}
                custom = context.get("custom") or {}
                if custom.get("session_id") != str(key) or custom.get("sha256") != digest:
                    raise SkillSphereException(
                        409,
                        "A Cloudinary asset already exists for this assessment but its content cannot be safely matched. Contact support; no asset was overwritten.",
                    )
                if not resource.get("asset_id") or not resource.get("public_id"):
                    raise SkillSphereException(502, "Cloudinary returned incomplete recording metadata.")
                return {
                    "storage_reference": f"{CLOUDINARY_REFERENCE_PREFIX}{resource['public_id']}",
                    "provider": "cloudinary",
                    "asset_id": str(resource["asset_id"]),
                    "public_id": str(resource["public_id"]),
                    "version": str(resource.get("version", "")),
                    "format": str(resource.get("format", "")),
                    "bytes": int(resource.get("bytes", source_path.stat().st_size)),
                    "resource_type": str(resource.get("resource_type", "video")),
                    "delivery_type": str(resource.get("type", "authenticated")),
                }

            # Reconcile before upload so a retry after a lost response can reuse
            # only the exact asset created for this assignment and video content.
            existing = read_existing_asset()
            if existing:
                return metadata_from_resource(existing)
            try:
                result = cloudinary.uploader.upload_large(
                    str(source_path),
                    resource_type="video",
                    type="authenticated",
                    public_id=public_id,
                    overwrite=False,
                    unique_filename=False,
                    chunk_size=6 * 1024 * 1024,
                    use_filename=False,
                    context={"session_id": str(key), "sha256": digest},
                )
                if not result.get("asset_id") or not result.get("public_id"):
                    raise RuntimeError("Cloudinary did not return the uploaded asset identifiers.")
                if (
                    result.get("public_id") != public_id
                    or result.get("resource_type") != "video"
                    or result.get("type") != "authenticated"
                    or int(result.get("bytes", -1)) != source_path.stat().st_size
                ):
                    raise RuntimeError("Cloudinary upload metadata did not match the private recording request.")
                # Never persist secure_url: authenticated playback URLs are generated per access.
                return {
                    "storage_reference": f"{CLOUDINARY_REFERENCE_PREFIX}{result['public_id']}",
                    "provider": "cloudinary",
                    "asset_id": str(result["asset_id"]),
                    "public_id": str(result["public_id"]),
                    "version": str(result.get("version", "")),
                    "format": str(result.get("format", "")),
                    "bytes": int(result.get("bytes", source_path.stat().st_size)),
                    "resource_type": str(result.get("resource_type", "video")),
                    "delivery_type": str(result.get("type", "authenticated")),
                }
            except Exception as exc:
                # Upload may have reached Cloudinary even if the response was
                # lost. Look up the stable public ID and accept only a matching
                # session/content fingerprint. Never overwrite or delete here.
                try:
                    recovered = read_existing_asset()
                except SkillSphereException:
                    raise
                if recovered:
                    return metadata_from_resource(recovered)
                logger.error("Cloudinary recording upload failed (%s).", type(exc).__name__)
                raise SkillSphereException(502, "Cloudinary recording upload failed. The recording was not marked complete.") from exc

        if backend == "s3":
            s3 = cls._get_s3_client("s3")
            key = f"recordings/{destination_filename}"
            try:
                with open(source_path, "rb") as stream:
                    s3.upload_fileobj(stream, settings.AWS_S3_BUCKET_NAME, key, ExtraArgs={"ContentType": content_type, "ServerSideEncryption": "AES256"})
                return {"storage_reference": f"{S3_REFERENCE_PREFIX}{settings.AWS_S3_BUCKET_NAME}/{key}", "provider": "s3"}
            except Exception as exc:
                logger.exception("S3 recording upload failed.")
                raise SkillSphereException(502, "S3 recording upload failed.") from exc

        PRIVATE_RECORDING_DIR.mkdir(parents=True, exist_ok=True)
        target_path = (PRIVATE_RECORDING_DIR / destination_filename).resolve()
        if PRIVATE_RECORDING_DIR not in target_path.parents:
            raise SkillSphereException(400, "Unsafe destination filename detected.")
        if source_path.resolve() != target_path:
            shutil.copy2(str(source_path), str(target_path))
        return {"storage_reference": str(target_path), "provider": "local"}

    @classmethod
    def save_recording_file(cls, source_path: Path, destination_filename: str, content_type: str = "video/webm") -> str:
        """Compatibility wrapper for existing callers that need only a reference."""
        return cls.save_recording_with_metadata(source_path, destination_filename, content_type)["storage_reference"]

    @classmethod
    def delete_recording(cls, storage_reference: str) -> bool:
        if not storage_reference:
            return False
        if storage_reference.startswith(CLOUDINARY_REFERENCE_PREFIX):
            try:
                cls._configure_cloudinary()
                import cloudinary.uploader
                public_id = storage_reference[len(CLOUDINARY_REFERENCE_PREFIX):]
                result = cloudinary.uploader.destroy(public_id, resource_type="video", type="authenticated", invalidate=True)
                return result.get("result") in {"ok", "not found"}
            except Exception:
                logger.error("Cloudinary recording deletion failed; provider response details omitted.")
                return False
        if storage_reference.startswith(S3_REFERENCE_PREFIX):
            try:
                cls._get_s3_client("s3").delete_object(
                    Bucket=storage_reference[5:].split("/", 1)[0],
                    Key=storage_reference[5:].split("/", 1)[1],
                )
                return True
            except Exception:
                logger.exception("Legacy S3 recording deletion failed.")
                return False
        try:
            path = Path(storage_reference).resolve()
            if PRIVATE_RECORDING_DIR not in path.parents:
                logger.error("Skipping deletion of unsafe recording path.")
                return False
            if path.exists() and path.is_file():
                path.unlink()
            return not path.exists()
        except Exception:
            logger.exception("Local recording deletion failed.")
            return False

    @classmethod
    def get_access_url(cls, storage_reference: str, expires_in_seconds: int = 600, asset_format: str = "webm", attachment: bool = False) -> Optional[str]:
        if not storage_reference:
            return None
        if storage_reference.startswith(CLOUDINARY_REFERENCE_PREFIX):
            cls._configure_cloudinary()
            import cloudinary.utils
            from datetime import datetime, timedelta, timezone

            public_id = storage_reference[len(CLOUDINARY_REFERENCE_PREFIX):]
            expires_at = int((datetime.now(timezone.utc) + timedelta(seconds=min(expires_in_seconds, 600))).timestamp())
            try:
                return cloudinary.utils.private_download_url(
                    public_id,
                    asset_format,
                    resource_type="video",
                    type="authenticated",
                    expires_at=expires_at,
                    attachment=attachment,
                )
            except Exception as exc:
                logger.error("Cloudinary playback signing failed (%s).", type(exc).__name__)
                raise SkillSphereException(500, "Could not generate secure Cloudinary playback link.") from None
        if storage_reference.startswith(S3_REFERENCE_PREFIX):
            self = cls._get_s3_client("s3")
            bucket, key = storage_reference[5:].split("/", 1)
            params = {"Bucket": bucket, "Key": key}
            if attachment:
                params["ResponseContentDisposition"] = "attachment"
            return self.generate_presigned_url(
                ClientMethod="get_object",
                Params=params,
                ExpiresIn=min(expires_in_seconds, 600),
            )
        return None

    @classmethod
    def is_file_available(cls, storage_reference: str) -> bool:
        if not storage_reference:
            return False
        if storage_reference.startswith(CLOUDINARY_REFERENCE_PREFIX):
            # Upload metadata is committed only after Cloudinary confirms success;
            # avoid requiring broader Admin API permissions on every playback.
            return cls.is_cloudinary_configured()
        if storage_reference.startswith(S3_REFERENCE_PREFIX):
            try:
                bucket, key = storage_reference[5:].split("/", 1)
                cls._get_s3_client("s3").head_object(Bucket=bucket, Key=key)
                return True
            except Exception:
                return False
        path = Path(storage_reference).resolve()
        return PRIVATE_RECORDING_DIR in path.parents and path.exists() and path.is_file()
