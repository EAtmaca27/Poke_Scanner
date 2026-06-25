import base64
import json
import os
import re
import time
import requests

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = "gpt-4o"

SCAN_PROMPT = (
    "This is a Pokémon TCG card. Extract the following and "
    "return ONLY a JSON object with these keys:\n"
    '- "name": the Pokémon name on the card\n'
    '- "hp": the HP value (number only, or null)\n'
    '- "number": the card number in the set (bottom of the card, e.g. "25/102", just the first number)\n'
    "Return only the JSON, no markdown fences or extra text."
)


def scan_with_cloud_llm(image_bytes, mime_type="image/png"):
    """Send card image to OpenAI's vision API and extract card info.
    Returns dict with keys: name, hp, number, model, input_tokens, output_tokens, total_tokens, duration_ms.
    """
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set in the .env file.")
    api_key = OPENAI_API_KEY

    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{b64_image}"

    start = time.perf_counter()

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": OPENAI_MODEL,
            "max_tokens": 256,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": SCAN_PROMPT},
                    ],
                }
            ],
        },
        timeout=30,
    )
    response.raise_for_status()

    duration_ms = int((time.perf_counter() - start) * 1000)

    body = response.json()
    usage = body.get("usage", {})
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)

    text = body["choices"][0]["message"]["content"].strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    result = json.loads(text)

    result["model"] = OPENAI_MODEL
    result["input_tokens"] = input_tokens
    result["output_tokens"] = output_tokens
    result["total_tokens"] = input_tokens + output_tokens
    result["duration_ms"] = duration_ms

    return result


def scan_with_tesseract(image_bytes):
    """Use Tesseract OCR locally to extract card info from an image."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        raise ImportError("pytesseract and Pillow are required. Install with: pip install pytesseract Pillow")

    pytesseract.pytesseract.tesseract_cmd = os.environ.get(
        "TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )

    import io
    image = Image.open(io.BytesIO(image_bytes))
    width, height = image.size

    def ocr_crop(box, scale=3):
        region = image.crop(box).convert("L")
        region = region.resize((region.width * scale, region.height * scale), Image.LANCZOS)
        return pytesseract.image_to_string(region).strip()

    name_text = ocr_crop((0, 0, width, int(height * 0.15)))

    hp_match = re.search(r"(\d{2,3})\s*HP", name_text, re.IGNORECASE)
    hp = hp_match.group(1) if hp_match else None

    name_candidates = re.findall(r"[A-Z][a-z]{2,}", name_text)
    pokemon_name = name_candidates[-1] if name_candidates else None

    if not pokemon_name:
        name = re.sub(r"\d{2,3}\s*HP.*", "", name_text).strip()
        name = re.sub(r"(Stage\s*\d|BASIC|Basic)\s*", "", name, flags=re.IGNORECASE).strip()
        pokemon_name = name.split("\n")[-1].strip() or None

    bottom_text = ocr_crop((0, int(height * 0.85), width, height), scale=4)
    number_match = re.search(r"(\d{1,3})\s*/\s*\d{1,3}", bottom_text)
    number = number_match.group(1) if number_match else None

    return {"name": pokemon_name, "hp": hp, "number": number}
