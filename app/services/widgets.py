import io
import json
import mimetypes
import re
import shutil
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

from werkzeug.utils import secure_filename


BUILTIN_WIDGET_STYLES = [
    {"id": "neon", "label": "1. Neon Tech Widget", "custom": False},
    {"id": "glass", "label": "2. Glassmorphism Dashboard", "custom": False},
    {"id": "oled", "label": "3. Minimal OLED Widget", "custom": False},
    {"id": "home", "label": "4. Smart Home Energy Card", "custom": False},
    {"id": "control", "label": "5. Futuristic Control Panel", "custom": False},
    {"id": "mobile", "label": "6. Mobile App Style Widget", "custom": False},
    {"id": "industrial", "label": "7. Industrial Monitoring Widget", "custom": False},
    {"id": "liquid", "label": "8. Liquid Battery Widget", "custom": False},
    {"id": "radial", "label": "9. Radial Energy Hub", "custom": False},
    {"id": "premium", "label": "10. Premium Dark UI", "custom": False},
]

MAX_WIDGET_ZIP_BYTES = 2 * 1024 * 1024
MAX_WIDGET_PACKAGE_BYTES = 2 * 1024 * 1024
MAX_WIDGET_FILE_COUNT = 40
ALLOWED_WIDGET_SUFFIXES = {
    ".css",
    ".gif",
    ".jpeg",
    ".jpg",
    ".json",
    ".otf",
    ".png",
    ".ttf",
    ".webp",
    ".woff",
    ".woff2",
    ".xml",
}
IGNORED_PACKAGE_FILES = {".ds_store"}


class WidgetUploadError(ValueError):
    def __init__(self, message_key, **params):
        super().__init__(message_key)
        self.message_key = message_key
        self.params = params


class WidgetManager:
    def __init__(self, storage_path):
        self.storage_path = Path(storage_path)
        self.manifest_path = self.storage_path / "widgets.json"

    def list_options(self):
        return [*BUILTIN_WIDGET_STYLES, *self.list_custom()]

    def list_custom(self):
        manifest = self._read_manifest()
        styles = []
        for style_id, meta in sorted(manifest.items(), key=lambda item: item[1]["label"].lower()):
            if meta.get("package_dir"):
                package_dir = meta["package_dir"]
                css_file = meta.get("css_file", "style.css")
                if not (self.storage_path / package_dir / css_file).is_file():
                    continue
                styles.append(
                    {
                        "id": style_id,
                        "label": meta.get("label") or style_id,
                        "version": meta.get("version", ""),
                        "author": meta.get("author", ""),
                        "package_dir": package_dir,
                        "css_file": css_file,
                        "custom": True,
                    }
                )
                continue

            filename = meta.get("filename", f"{style_id}.css")
            if not (self.storage_path / filename).is_file():
                continue
            styles.append(
                {
                    "id": style_id,
                    "label": meta.get("label") or style_id,
                    "filename": filename,
                    "custom": True,
                }
            )
        return styles

    def get_custom(self, style_id):
        for style in self.list_custom():
            if style["id"] == style_id:
                return style
        return None

    def install_package(self, uploaded_file):
        if not uploaded_file or not uploaded_file.filename:
            raise WidgetUploadError("widget.error.select_zip")

        original_name = Path(uploaded_file.filename).name
        if Path(original_name).suffix.lower() != ".zip":
            raise WidgetUploadError("widget.error.zip_only")

        package_bytes = uploaded_file.read(MAX_WIDGET_ZIP_BYTES + 1)
        if len(package_bytes) > MAX_WIDGET_ZIP_BYTES:
            raise WidgetUploadError("widget.error.zip_too_large")

        files = self._read_zip_files(package_bytes)
        package_meta = self._read_package_meta(files, original_name)
        css_text = self._decode_css(files[package_meta["css_file"]])
        self._validate_css(css_text)

        style_id = self._style_id_from(package_meta["id"] or package_meta["label"])
        package_dir = style_id

        self.storage_path.mkdir(parents=True, exist_ok=True)
        manifest = self._read_manifest()
        if style_id in manifest:
            self._remove_meta_files(manifest[style_id])

        package_path = self.storage_path / package_dir
        if package_path.exists():
            shutil.rmtree(package_path)
        package_path.mkdir(parents=True, exist_ok=True)

        for relative_path, content in files.items():
            target = package_path / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)

        manifest[style_id] = {
            "label": package_meta["label"],
            "version": package_meta["version"],
            "author": package_meta["author"],
            "package_dir": package_dir,
            "css_file": package_meta["css_file"],
        }
        self._write_manifest(manifest)
        return self.get_custom(style_id)

    def delete_custom(self, style_id):
        manifest = self._read_manifest()
        meta = manifest.get(style_id)
        if not meta:
            raise WidgetUploadError("widget.error.custom_not_found")

        self._remove_meta_files(meta)
        manifest.pop(style_id, None)
        self._write_manifest(manifest)

    def css_path_for(self, filename):
        safe_filename = secure_filename(filename)
        if not safe_filename or safe_filename != filename or not filename.endswith(".css"):
            return None
        css_path = self.storage_path / safe_filename
        return css_path if css_path.is_file() else None

    def file_path_for(self, style_id, filename):
        style = self.get_custom(style_id)
        if not style or not style.get("package_dir"):
            return None

        relative_path = self._safe_relative_path(filename)
        if relative_path is None:
            return None

        if relative_path.suffix.lower() not in ALLOWED_WIDGET_SUFFIXES:
            return None

        package_path = (self.storage_path / style["package_dir"]).resolve()
        asset_path = (package_path / relative_path.as_posix()).resolve()
        try:
            asset_path.relative_to(package_path)
        except ValueError:
            return None
        return asset_path if asset_path.is_file() else None

    @staticmethod
    def mimetype_for(path):
        suffix = Path(path).suffix.lower()
        font_mimetypes = {
            ".otf": "font/otf",
            ".ttf": "font/ttf",
            ".woff": "font/woff",
            ".woff2": "font/woff2",
        }
        if suffix in font_mimetypes:
            return font_mimetypes[suffix]
        return mimetypes.guess_type(str(path))[0]

    def _read_zip_files(self, package_bytes):
        try:
            archive = zipfile.ZipFile(io.BytesIO(package_bytes))
        except zipfile.BadZipFile as exc:
            raise WidgetUploadError("widget.error.bad_zip") from exc

        with archive:
            entries = []
            for info in archive.infolist():
                if info.is_dir():
                    continue
                relative_path = self._safe_zip_path(info.filename)
                if relative_path is None:
                    continue
                entries.append((info, relative_path))

            if not entries:
                raise WidgetUploadError("widget.error.empty_zip")
            if len(entries) > MAX_WIDGET_FILE_COUNT:
                raise WidgetUploadError("widget.error.too_many_files")

            root_folder = self._single_root_folder([relative_path for _, relative_path in entries])
            files = {}
            total_size = 0
            for info, relative_path in entries:
                if root_folder:
                    relative_path = PurePosixPath(*relative_path.parts[1:])
                if not relative_path.name:
                    continue
                if relative_path.suffix.lower() not in ALLOWED_WIDGET_SUFFIXES:
                    raise WidgetUploadError(
                        "widget.error.bad_file_type",
                        path=relative_path,
                    )

                total_size += info.file_size
                if total_size > MAX_WIDGET_PACKAGE_BYTES:
                    raise WidgetUploadError("widget.error.package_too_large")

                key = relative_path.as_posix()
                if key in files:
                    raise WidgetUploadError("widget.error.duplicate_file", path=key)
                files[key] = archive.read(info)

        if not files:
            raise WidgetUploadError("widget.error.empty_zip")
        return files

    def _read_package_meta(self, files, original_name):
        json_meta = self._read_widget_json(files)
        xml_meta = self._read_addon_xml(files) if not json_meta else {}
        meta = {**xml_meta, **json_meta}

        css_file = self._safe_relative_path(meta.get("stylesheet") or meta.get("css") or "style.css")
        if css_file is None or css_file.as_posix() not in files:
            css_candidates = [path for path in files if path.endswith(".css")]
            if len(css_candidates) == 1:
                css_file = PurePosixPath(css_candidates[0])
            else:
                raise WidgetUploadError("widget.error.missing_css")

        label = (
            meta.get("name")
            or meta.get("label")
            or Path(original_name).stem
            or "Custom widget"
        ).strip()

        return {
            "id": meta.get("id") or label,
            "label": label,
            "version": str(meta.get("version") or ""),
            "author": str(meta.get("author") or meta.get("provider") or ""),
            "css_file": css_file.as_posix(),
        }

    @staticmethod
    def _read_widget_json(files):
        if "widget.json" not in files:
            return {}
        try:
            meta = json.loads(files["widget.json"].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WidgetUploadError("widget.error.bad_widget_json") from exc
        if not isinstance(meta, dict):
            raise WidgetUploadError("widget.error.widget_json_object")
        return meta

    @staticmethod
    def _read_addon_xml(files):
        if "addon.xml" not in files:
            return {}
        try:
            root = ElementTree.fromstring(files["addon.xml"].decode("utf-8"))
        except (UnicodeDecodeError, ElementTree.ParseError) as exc:
            raise WidgetUploadError("widget.error.bad_addon_xml") from exc

        meta = {
            "id": root.get("id", ""),
            "name": root.get("name", ""),
            "version": root.get("version", ""),
            "author": root.get("provider-name", ""),
        }
        for extension in root.findall("extension"):
            stylesheet = extension.get("stylesheet") or extension.get("css")
            if stylesheet:
                meta["stylesheet"] = stylesheet
                break
        return meta

    @staticmethod
    def _decode_css(css_bytes):
        try:
            return css_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise WidgetUploadError("widget.error.bad_css_encoding") from exc

    @staticmethod
    def _validate_css(css_text):
        lowered = css_text.lower()
        blocked_tokens = (
            "<script",
            "</style",
            "@import",
            "javascript:",
            "data:",
            "http://",
            "https://",
            "url(//",
        )
        if any(token in lowered for token in blocked_tokens):
            raise WidgetUploadError("widget.error.blocked_css")

    def _remove_meta_files(self, meta):
        if meta.get("package_dir"):
            package_path = self.storage_path / secure_filename(meta["package_dir"])
            if package_path.is_dir():
                shutil.rmtree(package_path)
        if meta.get("filename"):
            css_path = self.storage_path / secure_filename(meta["filename"])
            if css_path.is_file():
                css_path.unlink()

    def _style_id_from(self, value):
        safe_value = secure_filename(str(value or "")).lower()
        slug = re.sub(r"[^a-z0-9]+", "-", safe_value).strip("-") or "custom-widget"
        style_id = slug if slug.startswith("user-") else f"user-{slug}"
        builtin_ids = {style["id"] for style in BUILTIN_WIDGET_STYLES}
        if style_id in builtin_ids:
            style_id = f"user-{style_id}"
        return style_id

    def _read_manifest(self):
        try:
            return json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_manifest(self, manifest):
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _safe_zip_path(filename):
        relative_path = WidgetManager._safe_relative_path(filename)
        if relative_path is None:
            raise WidgetUploadError("widget.error.bad_zip_path", path=filename)
        if "__MACOSX" in relative_path.parts:
            return None
        if relative_path.name.lower() in IGNORED_PACKAGE_FILES:
            return None
        return relative_path

    @staticmethod
    def _safe_relative_path(path_value):
        if not path_value:
            return None
        normalized = str(path_value).replace("\\", "/")
        relative_path = PurePosixPath(normalized)
        if relative_path.is_absolute():
            return None

        safe_parts = []
        for part in relative_path.parts:
            if part in ("", ".", ".."):
                return None
            safe_part = secure_filename(part)
            if not safe_part or safe_part != part:
                return None
            safe_parts.append(safe_part)
        return PurePosixPath(*safe_parts) if safe_parts else None

    @staticmethod
    def _single_root_folder(paths):
        if not paths or any(len(path.parts) < 2 for path in paths):
            return ""
        roots = {path.parts[0] for path in paths}
        return roots.pop() if len(roots) == 1 else ""
