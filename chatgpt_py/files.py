"""Backward compatibility — re-exports from modules.files."""
from .modules.files import (
    upload_file,
    upload_multiple,
    list_uploaded_files,
    download_last_file,
    remove_uploaded_file,
)

download_last = download_last_file
