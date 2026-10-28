from pathlib import Path

from django.core.exceptions import ValidationError


MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".png",
    ".jpg",
    ".jpeg",
}

_OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_SIGNATURES = {
    ".pdf": (b"%PDF-",),
    ".doc": (_OLE_SIGNATURE,),
    ".xls": (_OLE_SIGNATURE,),
    ".ppt": (_OLE_SIGNATURE,),
    ".docx": (b"PK\x03\x04",),
    ".xlsx": (b"PK\x03\x04",),
    ".pptx": (b"PK\x03\x04",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
}


def validar_archivo(archivo):
    if not archivo:
        raise ValidationError("Debés seleccionar un archivo.")

    extension = Path(archivo.name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            "Formato no permitido. Subí PDF, Word, Excel, PowerPoint o una imagen."
        )
    if archivo.size > MAX_FILE_SIZE:
        raise ValidationError("El archivo no puede superar los 10 MB.")
    if archivo.size == 0:
        raise ValidationError("El archivo está vacío.")

    # Content-Type is supplied by the client and is not a trustworthy check.
    archivo.seek(0)
    header = archivo.read(16)
    archivo.seek(0)
    if not any(header.startswith(signature) for signature in _SIGNATURES[extension]):
        raise ValidationError("El contenido no coincide con la extensión del archivo.")
