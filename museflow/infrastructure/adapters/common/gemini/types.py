from enum import StrEnum


class GeminiModel(StrEnum):
    # --- STABLE / GA SERIES ---
    PRO_2_5 = "gemini-2.5-pro"
    FLASH_2_5 = "gemini-2.5-flash"
    FLASH_LITE_2_5 = "gemini-2.5-flash-lite"

    # --- GEMINI 3.1 FLAGSHIP (April 2026 Standard) ---
    PRO_3_1 = "gemini-3.1-pro-preview"
    FLASH_3_1 = "gemini-3.1-flash-preview"
    FLASH_LITE_3_1 = "gemini-3.1-flash-lite-preview"
