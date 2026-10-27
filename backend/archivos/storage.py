from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateFileSystemStorage(FileSystemStorage):
    """Local disk storage deliberately located outside MEDIA_ROOT/STATIC_ROOT."""

    def __init__(self, location=None, base_url=None, **kwargs):
        super().__init__(
            location=location or settings.PRIVATE_MEDIA_ROOT,
            base_url=base_url,
            **kwargs,
        )

    def url(self, name):
        raise ValueError("Los archivos académicos privados no tienen URL pública; usa la vista de descarga autorizada.")
