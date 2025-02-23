import re
import time
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


def get_transcript_with_retry(
    video_id: str, language: str = None, max_retries: int = 3
):
    """Get transcript with retry logic."""
    last_error = None
    for attempt in range(max_retries):
        try:
            if language:
                return YouTubeTranscriptApi.get_transcript(
                    video_id, languages=[language]
                )
            else:
                return YouTubeTranscriptApi.get_transcript(video_id)
        except TooManyRequests:
            if attempt < max_retries - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))  # Exponential backoff
                continue
            last_error = "Too many requests. Please try again later."
        except NoTranscriptFound:
            last_error = (
                f"No transcript found in language: {language if language else 'any'}"
            )
            break
        except VideoUnavailable:
            last_error = "Video is unavailable. It might be private or doesn't exist."
            break
        except TranscriptsDisabled:
            last_error = "Transcripts are disabled for this video."
            break
        except Exception as e:
            last_error = str(e)
            if attempt < max_retries - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
                continue
            break

    raise Exception(last_error)


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

        try:
            # Try to get transcript with retries
            transcript = get_transcript_with_retry(clean_video_id, language)
            cache_transcript(clean_video_id, language, transcript)
            return transcript
        except Exception:
            # If requested language fails, try English
            try:
                transcript = get_transcript_with_retry(clean_video_id, "en")
                cache_transcript(clean_video_id, language, transcript)
                return transcript
            except Exception:
                # If English fails, try without language specification
                try:
                    transcript = get_transcript_with_retry(clean_video_id)
                    cache_transcript(clean_video_id, language, transcript)
                    return transcript
                except Exception as final_error:
                    raise HTTPException(
                        status_code=400,
                        detail=str(final_error),
                    )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
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
