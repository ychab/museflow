from enum import StrEnum


class GeminiModel(StrEnum):
    # --- GEMINI 2.5 GA SERIES ---
    PRO_2_5 = "gemini-2.5-pro"
    FLASH_2_5 = "gemini-2.5-flash"
    FLASH_LITE_2_5 = "gemini-2.5-flash-lite"

    # --- GEMINI 3.X GA SERIES ---
    PRO_3_1 = "gemini-3.1-pro-preview"  # stable Pro not yet GA
    FLASH_3_5 = "gemini-3.5-flash"
    FLASH_LITE_3_1 = "gemini-3.1-flash-lite"
