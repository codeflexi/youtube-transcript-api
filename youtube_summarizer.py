import openai
from youtube_transcript_api import YouTubeTranscriptApi

# API Keys
openai.api_key = "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"
VIDEO_ID = "zp0GqmvlwnQ"  # Replace with your desired video ID


def get_transcript(video_id: str) -> str:
    """Fetch the transcript from YouTube using youtube_transcript_api."""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join(item["text"] for item in transcript_list)
    except Exception as e:
        print(f"Error fetching transcript: {e}")
        return None


def generate_summary(transcript: str) -> str:
    """Generate a summary using OpenAI's GPT-4."""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that creates concise bullet-point summaries.",
                },
                {
                    "role": "user",
                    "content": f"Summarize this transcript in bullet points:\n\n{transcript}",
                },
            ],
            temperature=0.7,
            max_tokens=500,
        )
        return response.choices[0].message["content"]
    except Exception as e:
        print(f"Error generating summary: {e}")
        return None


def main():
    # Get the transcript
    print("Fetching transcript...")
    transcript = get_transcript(VIDEO_ID)

    if not transcript:
        print("Failed to fetch transcript.")
        return

    # Generate summary
    print("Generating summary...")
    summary = generate_summary(transcript)

    if not summary:
        print("Failed to generate summary.")
        return

    # Print the summary
    print("\nSummary:")
    print("-" * 50)
    print(summary)
    print("-" * 50)


if __name__ == "__main__":
    main()
