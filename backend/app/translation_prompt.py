import json
from collections.abc import Iterable, Sequence

SUPPORTED_LANGUAGES: dict[str, str] = {
    "en": "English",
    "ko": "Korean",
    "zh-hans": "Simplified Chinese",
    "zh-hant": "Traditional Chinese",
}


def supported_languages(codes: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    languages: list[str] = []
    for code in codes:
        if code in SUPPORTED_LANGUAGES and code not in seen:
            seen.add(code)
            languages.append(code)
    return tuple(languages)


def build_prompt(
    active_languages: Sequence[str],
    *,
    context_lines: Sequence[str] = (),
) -> str:
    languages = supported_languages(active_languages)
    if not languages:
        raise ValueError("At least one supported language is required.")

    language_list = "\n".join(
        f'- "{code}": {SUPPORTED_LANGUAGES[code]}' for code in languages
    )
    key_list = ", ".join(f'"{code}"' for code in languages)
    output_example = json.dumps(
        {
            "japanese": "<cleaned Japanese transcript>",
            "translations": {
                code: f"<{SUPPORTED_LANGUAGES[code]} translation>"
                for code in languages
            },
        },
        ensure_ascii=False,
        indent=2,
    )

    context_section = ""
    cleaned_context = [line.strip() for line in context_lines if line.strip()]
    if cleaned_context:
        context_section = (
            "\nRECENT CONTEXT (already translated; use it for continuity "
            "and terminology)\n"
            + "\n".join(f"- {line}" for line in cleaned_context)
            + "\n"
            + "The audio may begin with a short overlap that repeats the end "
            "of this context. Do not repeat any text that is already covered "
            "above; start from the new speech.\n"
        )

    return f"""You are an expert real-time interpreter for a Japanese Christian church sermon.

TASK
1. Transcribe the Japanese speech into clean Japanese.
2. Translate the same speech into every target language listed below.
3. Return only the JSON object described at the end.

JAPANESE TRANSCRIPT
- Remove hesitation sounds, stutters, and fillers such as え, えっと, あの, うーん, ええと, まあ, and ね.
- Remove standalone はい, うん, and そう when they are conversational pauses or acknowledgements. Keep them when they are meaningful answers or part of a real sentence.
- Preserve the speaker's meaning. Do not complete an unfinished thought or invent information.
- Ignore music, coughing, silence, and other non-speech sounds.
- If there is no meaningful speech, return empty strings.

TRANSLATION STYLE
- English: fluent, warm, pastoral, and faithful. Use ESV wording for direct Scripture quotations.
- Korean: formal polite style (존댓말), faithful and pastoral. Use 개역개정 wording for direct Scripture quotations.
- Simplified Chinese: Protestant terminology, faithful and pastoral. Use 和合本 wording for direct Scripture quotations.
- Traditional Chinese: Protestant terminology, faithful and pastoral. Use 和合本 wording for direct Scripture quotations.
- The source Bible text is 新共同訳. When the speaker quotes Scripture directly, use the target-language version above. When the speaker paraphrases, translate the paraphrase; do not substitute a different verse.
- Keep names and recurring terms consistent across the sermon, following the RECENT CONTEXT wording.
{context_section}
TARGET LANGUAGES
{language_list}

OUTPUT
Return only a JSON object with this exact shape:
{output_example}

Use exactly these translation keys: {key_list}. Do not wrap the JSON in markdown."""


def build_response_schema(active_languages: Sequence[str]) -> dict:
    languages = supported_languages(active_languages)
    if not languages:
        raise ValueError("At least one supported language is required.")

    return {
        "type": "OBJECT",
        "properties": {
            "japanese": {
                "type": "STRING",
                "description": (
                    "Cleaned Japanese transcript of the chunk. "
                    "Empty when there is no meaningful speech."
                ),
            },
            "translations": {
                "type": "OBJECT",
                "description": "Translations keyed by language code.",
                "properties": {
                    code: {
                        "type": "STRING",
                        "description": (
                            f"{SUPPORTED_LANGUAGES[code]} translation. "
                            "Empty when there is no meaningful speech."
                        ),
                    }
                    for code in languages
                },
                "required": list(languages),
            },
        },
        "required": ["japanese", "translations"],
    }
