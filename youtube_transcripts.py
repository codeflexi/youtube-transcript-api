from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)

app = FastAPI(
    title="YouTube Transcript API",
    description="An API to fetch transcripts from YouTube videos",
    version="1.0.0",
)


@app.get("/transcript/", response_model=List[Dict[str, Any]])
async def get_transcript(video_id: str, language: str = "th"):
    """
    Get the transcript of a YouTube video.

    Parameters:
    - video_id: The YouTube video ID (the part after v= in the URL)
    - language: Language code (default: 'th' for Thai)
                Examples: 'th' (Thai), 'en' (English), 'ja' (Japanese)

    Returns:
    - List of transcript segments with text, start time, and duration
    """
    try:
        # Try to get all available transcripts first
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        # Try to get the requested language directly
        try:
            transcript = transcript_list.find_transcript([language])
            return transcript.fetch()
        except NoTranscriptFound:
            # If requested language not found, try English and translate
            try:
                transcript = transcript_list.find_transcript(["en"])
                translated = transcript.translate(language)
                return translated.fetch()
            except Exception:
                # If translation fails, try to get any available transcript
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
                        return translated.fetch()
                    else:
                        raise HTTPException(
                            status_code=400,
                            detail="No transcripts available for this video. Try video ID: 'PMtlIBtqNJo' which has Thai captions.",
                        )
                except Exception as e:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Translation failed. Error: {str(e)}. Try video ID: 'PMtlIBtqNJo' which has Thai captions.",
                    )

    except TranscriptsDisabled:
        raise HTTPException(
            status_code=400,
            detail="Transcripts are disabled for this video. Try video ID: 'PMtlIBtqNJo' which has Thai captions.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error fetching transcript: {str(e)}. Try video ID: 'PMtlIBtqNJo' which has Thai captions.",
        )


@app.get("/languages/{video_id}")
async def get_available_languages(video_id: str):
    """Get available languages for a video."""
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        languages = {"manual": [], "generated": [], "translatable": []}

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
            detail=f"Error fetching languages: {str(e)}. Try video ID: 'PMtlIBtqNJo' which has Thai captions.",
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
        "example": {
            "transcript": "/transcript/?video_id=PMtlIBtqNJo&language=th",
            "languages": "/languages/PMtlIBtqNJo",
        },
        "note": "Check available languages first using the /languages endpoint before requesting a specific language transcript.",
    }
