import os
import shutil
import uuid
import zipfile
from pathlib import Path
from fastapi import HTTPException, UploadFile, status

# Allowed file extensions
ALLOWED_EXTENSIONS = {".docx", ".tex", ".pdf"}

# Security limits for docx zip archive inspection
MAX_ZIP_ENTRIES = 500
MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024  # 100 MB total uncompressed
MAX_COMPRESSION_RATIO = 100.0


class StorageService:
    def __init__(self, storage_root: str):
        self.root = Path(storage_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _ensure_project_dir(self, project_id: int) -> Path:
        pdir = (self.root / str(project_id)).resolve()
        self._guard_path(pdir)
        pdir.mkdir(parents=True, exist_ok=True)
        # Attempt to restrict permissions on POSIX systems
        try:
            os.chmod(pdir, 0o700)
        except Exception:
            pass
        return pdir

    def _guard_path(self, target: Path) -> None:
        """Raise an error if path resolves outside storage root (path traversal check)."""
        resolved = target.resolve()
        if not str(resolved).startswith(str(self.root)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Security violation: Path outside storage root",
            )

    def sanitize_display_filename(self, filename: str) -> str:
        """Strip directory paths, control characters, and limit to 255 chars."""
        base = Path(filename).name
        # Remove control characters and NUL
        clean = "".join(c for c in base if ord(c) >= 32 and ord(c) != 127)
        if not clean:
            clean = "manuscript"
        return clean[:255]

    def validate_content_sniffing(self, file_path: Path, ext: str) -> None:
        """Sniff file contents rather than trusting MIME type or file extension."""
        ext = ext.lower()
        if ext == ".docx":
            try:
                if not zipfile.is_zipfile(file_path):
                    raise ValueError("Not a valid zip archive")
                with zipfile.ZipFile(file_path, "r") as zf:
                    namelist = zf.namelist()
                    if len(namelist) > MAX_ZIP_ENTRIES:
                        raise ValueError("Excessive number of entries in docx archive (zip bomb protection)")

                    total_uncompressed = 0
                    for info in zf.infolist():
                        total_uncompressed += info.file_size
                        if info.compress_size > 0:
                            ratio = info.file_size / info.compress_size
                            if ratio > MAX_COMPRESSION_RATIO:
                                raise ValueError("Excessive compression ratio in docx (zip bomb protection)")

                    if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                        raise ValueError("Total uncompressed size too large (zip bomb protection)")

                    # Must contain word/document.xml and [Content_Types].xml
                    if "[Content_Types].xml" not in namelist or "word/document.xml" not in namelist:
                        raise ValueError("Missing required DOCX structures")

                    # Reject macros
                    if any("vbaProject.bin" in name for name in namelist):
                        raise ValueError("Macro-enabled documents (.docm / vbaProject) are not permitted")
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail=f"This file looks damaged or is not a valid docx file: {e}",
                )

        elif ext == ".pdf":
            try:
                with open(file_path, "rb") as f:
                    header = f.read(1024)
                    if not b"%PDF-" in header:
                        raise ValueError("Missing %PDF- magic header")
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail="This file looks damaged or is not a valid pdf file.",
                )

        elif ext == ".tex":
            try:
                with open(file_path, "rb") as f:
                    content = f.read()
                    if b"\x00" in content:
                        raise ValueError("LaTeX document contains binary NUL bytes")
                    content.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail="This file looks damaged or is not valid UTF-8 LaTeX text.",
                )
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail="This file looks damaged or is not a valid tex file.",
                )

    async def save_manuscript_stream(
        self,
        project_id: int,
        upload_file: UploadFile,
        max_bytes: int,
    ) -> tuple[str, str, int]:
        """
        Stream upload chunks directly to disk with chunked size limit abortion.
        Performs content sniffing validation.
        Returns: (relative_key, sanitized_display_name, total_bytes)
        """
        raw_name = upload_file.filename or "manuscript"
        clean_display_name = self.sanitize_display_filename(raw_name)

        ext = Path(clean_display_name).suffix.lower()
        if not ext:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Unsupported file type. Use .docx, .tex or .pdf.",
            )

        if ext == ".doc":
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Please save the file as .docx and try again.",
            )

        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Unsupported file type. Use .docx, .tex or .pdf.",
            )

        project_dir = self._ensure_project_dir(project_id)
        file_uuid = uuid.uuid4().hex
        temp_file_name = f"tmp_{file_uuid}{ext}"
        final_file_name = f"{file_uuid}{ext}"

        temp_path = project_dir / temp_file_name
        final_path = project_dir / final_file_name

        total_bytes = 0
        chunk_size = 64 * 1024  # 64 KB streaming chunks

        try:
            with open(temp_path, "wb") as f_out:
                while True:
                    chunk = await upload_file.read(chunk_size)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > max_bytes:
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail="File is too large (maximum 20 MB)",
                        )
                    f_out.write(chunk)

            if total_bytes == 0:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="This file is empty.",
                )

            # Perform content sniffing on temp file
            self.validate_content_sniffing(temp_path, ext)

            # Atomic rename / replace
            os.replace(temp_path, final_path)

        except Exception:
            # Clean up temp file on any error
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            raise

        relative_key = f"{project_id}/{final_file_name}"
        return relative_key, clean_display_name, total_bytes

    def delete_manuscript_file(self, relative_key: str | None) -> None:
        """Idempotently delete a manuscript file from storage root."""
        if not relative_key:
            return
        target = (self.root / relative_key).resolve()
        try:
            self._guard_path(target)
            if target.is_file():
                target.unlink()
        except Exception:
            pass

    def delete_project_storage(self, project_id: int) -> None:
        pdir = (self.root / str(project_id)).resolve()
        try:
            self._guard_path(pdir)
            if pdir.is_dir():
                shutil.rmtree(pdir, ignore_errors=True)
        except Exception:
            pass
