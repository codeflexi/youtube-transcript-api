import re
import time
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from youtube_transcript_api import (
    NoTranscriptFound,
    TooManyRequests,
    TranscriptsDisabled,
    VideoUnavailable,
    YouTubeTranscriptApi,
)

app = FastAPI(
    title="YouTube Transcript API",
    description="An API to fetch transcripts from YouTube videos",
    version="1.0.0",
)

# Cache to store recently fetched transcripts
transcript_cache = {}
CACHE_DURATION = 3600  # 1 hour in seconds
RETRY_DELAY = 2  # seconds to wait between retries


def extract_video_id(video_id: str) -> str:
    """Extract clean video ID from various YouTube URL formats."""
    # If it contains '&t=' (timestamp), remove it
    if "&t=" in video_id:
        video_id = video_id.split("&t=")[0]

    # If it's a full URL, extract the ID
    patterns = [
        r"(?:v=|/)([0-9A-Za-z_-]{11}).*",  # Regular YouTube URLs
        r"^([0-9A-Za-z_-]{11})$",  # Just the ID
    ]

    for pattern in patterns:
        match = re.search(pattern, video_id)
        if match:
            return match.group(1)

    return video_id  # Return as-is if no pattern matches


def validate_video_id(video_id: str) -> bool:
    """Validate YouTube video ID format."""
    pattern = r"^[0-9A-Za-z_-]{11}$"
    return bool(re.match(pattern, video_id))


def get_cached_transcript(video_id: str, language: str) -> List[Dict[str, Any]]:
    """Get transcript from cache if available and not expired."""
    cache_key = f"{video_id}_{language}"
    if cache_key in transcript_cache:
        cached_data = transcript_cache[cache_key]
        if time.time() - cached_data["timestamp"] < CACHE_DURATION:
            return cached_data["transcript"]
        else:
            del transcript_cache[cache_key]
    return None


def cache_transcript(video_id: str, language: str, transcript: List[Dict[str, Any]]):
    """Store transcript in cache."""
    cache_key = f"{video_id}_{language}"
    transcript_cache[cache_key] = {
        "transcript": transcript,
        "timestamp": time.time(),
    }


@app.get("/transcript/", response_model=List[Dict[str, Any]])
async def get_transcript(video_id: str, language: str = "th"):
    """
    Get the transcript of a YouTube video.

    Parameters:
    - video_id: The YouTube video ID or URL
    - language: Language code (default: 'th' for Thai)
                Examples: 'th' (Thai), 'en' (English), 'ja' (Japanese)

    Returns:
    - List of transcript segments with text, start time, and duration
    """
    try:
        # Clean up video ID
        clean_video_id = extract_video_id(video_id)

        # Validate video ID format
        if not validate_video_id(clean_video_id):
            raise HTTPException(
                status_code=400,
                detail="Invalid video ID format. Please provide a valid YouTube video ID (11 characters, alphanumeric with - and _)",
            )

        # Check cache first
        cached_transcript = get_cached_transcript(clean_video_id, language)
        if cached_transcript:
            return cached_transcript

        # Add delay to avoid rate limiting
        time.sleep(RETRY_DELAY)

        # Try to get all available transcripts
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(clean_video_id)
        except VideoUnavailable:
            raise HTTPException(
                status_code=400,
                detail="Video is unavailable. It might be private or doesn't exist.",
            )
        except TooManyRequests:
            raise HTTPException(
                status_code=429,
                detail="YouTube is rate limiting requests. Please try again in a few minutes.",
            )
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Could not access video transcripts: {str(e)}",
            )

        # Try to get the requested language directly
        try:
            transcript = transcript_list.find_transcript([language])
            result = transcript.fetch()
            cache_transcript(clean_video_id, language, result)
            return result
        except NoTranscriptFound:
            # If requested language not found, try English and translate
            try:
                # Try to get English transcript first
                transcript = transcript_list.find_transcript(["en"])
                translated = transcript.translate(language)
                result = translated.fetch()
                cache_transcript(clean_video_id, language, result)
                return result
            except Exception:
                # If English not available or translation fails, try any available transcript
                try:
                    # Get list of available transcripts
                    available_transcripts = list(
                        transcript_list._manually_created_transcripts.values()
                    )
                    if available_transcripts:
                        # Get first available transcript
                        available = available_transcripts[0]
                        # Try to translate it
                        translated = available.translate(language)
                        result = translated.fetch()
                        cache_transcript(clean_video_id, language, result)
                        return result
                    else:
                        # List available languages for better error message
                        available_langs = []
                        for t in transcript_list._manually_created_transcripts.values():
                            available_langs.append(f"{t.language_code} ({t.language})")
                        for t in transcript_list._generated_transcripts.values():
                            available_langs.append(f"{t.language_code} ({t.language})")

                        raise HTTPException(
                            status_code=400,
                            detail=f"No transcripts available in {language}. Available languages: {', '.join(available_langs) if available_langs else 'none'}",
                        )
                except Exception as e:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Could not get or translate transcript: {str(e)}",
                    )

    except TranscriptsDisabled:
        raise HTTPException(
            status_code=400,
            detail="Transcripts are disabled for this video. Please try a different video that has captions enabled.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error processing request: {str(e)}",
        )


@app.get("/languages/{video_id}")
async def get_available_languages(video_id: str):
    """Get available languages for a video."""
    try:
        # Clean up video ID
        clean_video_id = extract_video_id(video_id)

        # Validate video ID format
        if not validate_video_id(clean_video_id):
            raise HTTPException(
                status_code=400,
                detail="Invalid video ID format. Please provide a valid YouTube video ID (11 characters, alphanumeric with - and _)",
            )

        # Add delay to avoid rate limiting
        time.sleep(RETRY_DELAY)

        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(clean_video_id)
        except VideoUnavailable:
            raise HTTPException(
                status_code=400,
                detail="Video is unavailable. It might be private or doesn't exist.",
            )
        except TooManyRequests:
            raise HTTPException(
                status_code=429,
                detail="YouTube is rate limiting requests. Please try again in a few minutes.",
            )
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Could not access video transcripts: {str(e)}",
            )

        languages = {
            "manual": [],
            "generated": [],
            "translatable": [],
            "video_id": clean_video_id,
        }

        # Get manually created transcripts
        for transcript in transcript_list._manually_created_transcripts.values():
            languages["manual"].append(
                {
                    "language": transcript.language,
                    "code": transcript.language_code,
                }
            )

        # Get generated transcripts
        for transcript in transcript_list._generated_transcripts.values():
            languages["generated"].append(
                {
                    "language": transcript.language,
                    "code": transcript.language_code,
                }
            )

        # Get translatable languages
        try:
            first_transcript = next(
                iter(transcript_list._manually_created_transcripts.values())
            )
            languages["translatable"] = first_transcript.translation_languages
        except:
            pass

        return languages
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error fetching languages: {str(e)}",
        )


@app.get("/")
async def root():
    """Welcome message and API information."""
    return {
        "message": "Welcome to YouTube Transcript API",
        "usage": {
            "get_transcript": "GET /transcript/?video_id=YOUR_VIDEO_ID&language=th",
            "check_languages": "GET /languages/YOUR_VIDEO_ID",
        },
        "notes": [
            "Check available languages first using the /languages endpoint",
            "The video_id can be a full YouTube URL or just the ID",
            "Make sure the video has captions enabled",
            "If you get rate limit errors, wait a few minutes and try again",
        ],
    }
