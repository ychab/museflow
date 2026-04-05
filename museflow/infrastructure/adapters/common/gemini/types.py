from enum import StrEnum


class GeminiModel(StrEnum):
    # Gemini 2.5 — latest stable series (recommended)
    PRO_2_5 = "gemini-2.5-pro"
    FLASH_2_5 = "gemini-2.5-flash"
    FLASH_LITE_2_5 = "gemini-2.5-flash-lite"

    # Gemini 3.x — preview only, IDs may change
    PRO_3_1_PREVIEW = "gemini-3.1-pro-preview"
    FLASH_3_0_PREVIEW = "gemini-3-flash-preview"
    FLASH_LITE_3_1_PREVIEW = "gemini-3.1-flash-lite-preview"

    # Alias — resolves to latest; not recommended for production
    PRO_LATEST = "gemini-pro-latest"
    FLASH_LATEST = "gemini-flash-latest"
    FLASH_LITE_LATEST = "gemini-flash-lite-latest"
