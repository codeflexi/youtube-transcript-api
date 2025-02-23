import json

from youtube_transcript_api import YouTubeTranscriptApi

# Replace with your desired video ID
VIDEO_ID = "zp0GqmvlwnQ"


def get_transcript(video_id: str) -> list:
    """Fetch the transcript from YouTube and return as a list of segments."""
    try:
        return YouTubeTranscriptApi.get_transcript(video_id)
    except Exception as e:
        print(f"Error fetching transcript: {e}")
        return None


def main():
    # Get the transcript
    print("Fetching transcript...")
    transcript = get_transcript(VIDEO_ID)

    if not transcript:
        print("Failed to fetch transcript.")
        return

    # Print the transcript in JSON format
    print("\nTranscript:")
    print("-" * 50)
    print(json.dumps(transcript, indent=2))
    print("-" * 50)


if __name__ == "__main__":
    main()
