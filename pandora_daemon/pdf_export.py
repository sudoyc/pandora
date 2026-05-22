"""PDF export helpers for downloaded Pandora library galleries."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import tempfile

from PIL import Image
from pypdf import PdfReader, PdfWriter

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
_SAFE_OUTPUT_NAME_RE = re.compile(r"^[^\\/]+\.pdf$", re.IGNORECASE)


@dataclass(frozen=True)
class PdfExportPlan:
    gid: str
    output_path: Path
    page_paths: list[Path]


@dataclass(frozen=True)
class PdfExportResult:
    gid: str
    path: str
    password_protected: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": True,
            "gid": self.gid,
            "format": "pdf",
            "path": self.path,
            "password_protected": self.password_protected,
        }


class PdfExportError(ValueError):
    """Raised when a library gallery cannot be exported to PDF."""


def _numeric_page_key(path: Path) -> tuple[int, str]:
    try:
        return int(path.stem), path.name
    except ValueError:
        return 10**12, path.name


def _page_files(gallery_dir: Path) -> list[Path]:
    pages_dir = gallery_dir / "pages"
    if not pages_dir.exists() or not pages_dir.is_dir():
        return []
    return sorted(
        (
            p for p in pages_dir.iterdir()
            if p.is_file() and p.suffix.lower() in _IMAGE_EXTENSIONS and not p.name.endswith(".tmp")
        ),
        key=_numeric_page_key,
    )


def _resolve_output_path(gallery_dir: Path, gid: str, output_name: str | None) -> Path:
    name = output_name or f"{gid}.pdf"
    if not _SAFE_OUTPUT_NAME_RE.match(name):
        raise PdfExportError("Invalid PDF output name")
    exports_dir = gallery_dir / "exports"
    exports_dir.mkdir(exist_ok=True)
    return exports_dir / name


def _write_pdf_from_images(page_paths: list[Path], output_path: Path) -> None:
    images: list[Image.Image] = []
    try:
        for page_path in page_paths:
            image = Image.open(page_path)
            if image.mode != "RGB":
                image = image.convert("RGB")
            else:
                image = image.copy()
            images.append(image)

        if not images:
            raise PdfExportError("No page images found")

        output_path.parent.mkdir(exist_ok=True)
        with tempfile.NamedTemporaryFile(suffix=".pdf", dir=output_path.parent, delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            first, rest = images[0], images[1:]
            first.save(tmp_path, "PDF", save_all=True, append_images=rest)
            tmp_path.replace(output_path)
        finally:
            tmp_path.unlink(missing_ok=True)
    finally:
        for image in images:
            image.close()


def _encrypt_pdf(path: Path, password: str) -> None:
    reader = PdfReader(str(path))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(password)

    with tempfile.NamedTemporaryFile(suffix=".pdf", dir=path.parent, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        writer.write(tmp)
    try:
        tmp_path.replace(path)
    finally:
        tmp_path.unlink(missing_ok=True)


def plan_gallery_pdf_export(
    gallery_dir: Path,
    gid: str,
    *,
    output_name: str | None = None,
    include_cover: bool = False,
) -> PdfExportPlan:
    page_paths = _page_files(gallery_dir)
    if include_cover:
        for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
            cover = gallery_dir / f"cover{ext}"
            if cover.exists():
                page_paths = [cover, *page_paths]
                break
    if not page_paths:
        raise PdfExportError("No downloaded page images found")

    output_path = _resolve_output_path(gallery_dir, gid, output_name)
    return PdfExportPlan(gid=gid, output_path=output_path, page_paths=page_paths)


def execute_gallery_pdf_export(
    plan: PdfExportPlan,
    *,
    password: str | None = None,
) -> PdfExportResult:
    _write_pdf_from_images(plan.page_paths, plan.output_path)
    if password:
        _encrypt_pdf(plan.output_path, password)

    return PdfExportResult(
        gid=plan.gid,
        path=str(plan.output_path),
        password_protected=bool(password),
    )


def export_gallery_pdf(
    gallery_dir: Path,
    gid: str,
    *,
    password: str | None = None,
    output_name: str | None = None,
    include_cover: bool = False,
) -> PdfExportResult:
    plan = plan_gallery_pdf_export(
        gallery_dir,
        gid,
        output_name=output_name,
        include_cover=include_cover,
    )
    return execute_gallery_pdf_export(plan, password=password)
