from flask import Flask, render_template, request
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
from urllib.parse import urlparse, parse_qs
import re

app = Flask(__name__)

def extract_video_id(url):

    if not url:
        return None
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/|v\/|youtu\.be\/)([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def get_transcript_text(video_id):
    """Fetches and concatenates transcript text."""
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        transcript = None
        # Try to find a manually created transcript first
        try:
            transcript = transcript_list.find_manually_created_transcript(['en'])
        except NoTranscriptFound:
            app.logger.info(f"No manual English transcript for {video_id}. Trying generated.")
            # If not found, try to find an auto-generated one in English
            try:
                transcript = transcript_list.find_generated_transcript(['en'])
            except NoTranscriptFound:
                app.logger.warning(f"No generated English transcript for {video_id}. Trying any available.")
                # If English is not found, try to get any available transcript
                # This might not be ideal for summarization if not in a known language
                # Iterate through available languages to find the first available transcript object
                available_langs = transcript_list.available_languages
                if available_langs:
                    # This part might need more sophisticated language selection
                    # For simplicity, taking the first one found by find_generated_transcript
                    for lang_code in [lang['language_code'] for lang in available_langs]:
                        try:
                            transcript = transcript_list.find_generated_transcript([lang_code])
                            app.logger.info(f"Using transcript in language: {lang_code} for {video_id}")
                            break
                        except NoTranscriptFound:
                            continue # Try next language
                if not transcript: # If still no transcript after trying all available
                    return None, "No transcripts found for this video in any language."


        fetched_transcript_segments = transcript.fetch()

        # --- THIS IS THE CORRECTED PART ---
        # The error indicates 'segment' is an object, so we use attribute access '.text'
        # instead of dictionary access ['text'].
        full_text = " ".join([segment.text for segment in fetched_transcript_segments])
        # --- END OF CORRECTION ---

        return full_text, None # Return full_text and no error message
        
    except TranscriptsDisabled:
        app.logger.warning(f"Transcripts disabled for video {video_id}")
        return None, "Transcripts are disabled for this video."
    except NoTranscriptFound: # This might be redundant if handled above, but good as a catch-all
        app.logger.warning(f"No transcript found for video {video_id} after all attempts.")
        return None, "No transcript found for this video."
    except Exception as e:
        app.logger.error(f"Error fetching transcript for {video_id}: {e}")
        return None, f"An unexpected error occurred: {str(e)}"
def basic_summarizer(text):
    if not text:
        return ""
    return text


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/summarize', methods=['POST'])
def summarize_video():
    video_url = request.form.get('video_url', '').strip()
    video_id = extract_video_id(video_url)
    
    summary_text = None
    error_msg = None
    fetched_text_content = None # Renamed for clarity

    if not video_url:
        error_msg = "Please enter a YouTube video URL."
    elif not video_id:
        error_msg = "Invalid YouTube URL or could not extract Video ID. Please use a valid format (e.g., https://www.youtube.com/watch?v=VIDEO_ID or https://youtu.be/VIDEO_ID)."
    else:
        app.logger.info(f"Processing video ID: {video_id}")
        fetched_text_content, error_msg_from_fetch = get_transcript_text(video_id)

        if error_msg_from_fetch:
            error_msg = error_msg_from_fetch
        elif fetched_text_content:
            summary_text = basic_summarizer(fetched_text_content)
            if not summary_text and not error_msg : # Should ideally not happen if fetched_text_content is there
                error_msg = "Could not generate summary from the transcript."
        elif not error_msg: # If transcript fetching didn't set an error, but we still don't have text
             error_msg = "Could not retrieve transcript for the video (no text content)."


    return render_template('index.html',
                           summary=summary_text,
                           error_message=error_msg,
                           video_url_input=video_url,
                           full_transcript=fetched_text_content if error_msg and fetched_text_content else None)

if __name__ == '__main__':
    app.run(debug=True)
