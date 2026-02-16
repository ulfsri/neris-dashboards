"""
Export functionality for NERIS Dash apps.

"""

import io
import zipfile
import base64
from datetime import datetime
from typing import List, Tuple

from pandas import DataFrame

__all__ = [
    "create_zip_from_dataframes",
]


def create_zip_from_dataframes(
    dataframes: List[Tuple[str, DataFrame]],
    zip_filename: str | None = None,
    timestamp: bool = True,
) -> dict:
    """Create a zip file containing CSV files from multiple DataFrames.

    Args:
        dataframes: List of tuples (filename_without_extension, DataFrame)
        zip_filename: Base name for the zip file (without .zip extension).
                     If None, defaults to "export".
        timestamp: Whether to append a timestamp to the zip filename.

    Returns:
        Dictionary suitable for dcc.Download component with keys:
        - content: base64-encoded zip file content
        - filename: suggested filename for download
        - type: MIME type ("application/zip")
        - base64: True (indicates content is base64-encoded)

    """
    zip_buffer = io.BytesIO()

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S") if timestamp else None
    full_zip_filename = (
        f"{zip_filename}{f'_{timestamp_str}' if timestamp_str else ''}.zip"
    )

    # After the context manager exits, zip file is fully written and closed
    with zipfile.ZipFile(
        zip_buffer,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        allowZip64=True,
    ) as zip_file:
        for filename, df in dataframes:
            csv_content = df.to_csv(index=False)
            zip_file.writestr(filename, csv_content.encode("utf-8"))

    zip_bytes = zip_buffer.getvalue()
    zip_buffer.close()

    # Base64 encode the zip file for dcc.Download
    zip_base64 = base64.b64encode(zip_bytes).decode("utf-8")

    return dict(
        content=zip_base64,
        filename=full_zip_filename,
        type="application/zip",
        base64=True,
    )
