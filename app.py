import subprocess
print(subprocess.run(["ffmpeg", "-version"], capture_output=True).stdout.decode())

import os
import streamlit as st
from moviepy.editor import VideoFileClip
import whisper
import yt_dlp
import openai
from dotenv import load_dotenv
import json

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

st.title("YouTube Video Multi-Clipper AI")

youtube_url = st.text_input("Enter YouTube URL")
clip_length = st.number_input("Clip length (seconds)", min_value=30, max_value=180, value=90)
generate_max = st.checkbox("Generate maximum clips based on video length")

def download_youtube_video(url, output_path="video.mp4"):
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': output_path,
        'merge_output_format': 'mp4'
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

def transcribe_audio(file_path):
    model = whisper.load_model("base")
    result = model.transcribe(file_path)
    return result['text']

def ask_gpt_for_multiple_clips(transcript_text, clip_length=90, number_of_clips=3):
    system_prompt = (
        "You are a video editor AI. "
        f"Given a transcript, find the {number_of_clips} most engaging clips of about {clip_length} seconds each, suitable for TikTok. "
        "Return a JSON array with start and end timestamps in seconds, like: "
        '[{"start": 30, "end": 120}, {"start": 150, "end": 240}, {"start": 300, "end": 390}]'
    )
    user_prompt = f"Transcript:\n{transcript_text[:3000]}"
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    reply = response.choices[0].message.content
    st.write("GPT Response:", reply)
    try:
        clips = json.loads(reply)
        valid_clips = []
        for c in clips:
            if 'start' in c and 'end' in c and c['start'] < c['end']:
                valid_clips.append({'start': c['start'], 'end': c['end']})
        return valid_clips
    except Exception as e:
        st.warning(f"JSON parsing failed: {e}. Falling back to sequential clips.")
        fallback = []
        for i in range(number_of_clips):
            fallback.append({'start': i * clip_length, 'end': (i+1) * clip_length})
        return fallback

def create_multiple_clips(input_file, clips, prefix="clip"):
    video = VideoFileClip(input_file)
    output_files = []
    for i, c in enumerate(clips):
        start = max(0, c['start'])
        end = min(video.duration, c['end'])
        clip = video.subclip(start, end)
        output_path = f"{prefix}_{i+1}.mp4"
        clip.write_videofile(output_path, codec="libx264", verbose=False, logger=None)
        output_files.append(output_path)
    return output_files

if st.button("Generate Clips"):
    if not youtube_url:
        st.error("Please enter a valid YouTube URL.")
    else:
        with st.spinner("Downloading video..."):
            video_path = "video.mp4"
            try:
                download_youtube_video(youtube_url, video_path)
            except Exception as e:
                st.error(f"Download failed: {e}")
                st.stop()

        video = VideoFileClip(video_path)
        video_duration = video.duration

        if generate_max:
            num_clips = int(video_duration // clip_length)
            st.write(f"Generating maximum clips: {num_clips}")
        else:
            num_clips = st.number_input("Number of clips to generate", min_value=1, max_value=30, value=3)

        with st.spinner("Transcribing audio..."):
            transcript_text = transcribe_audio(video_path)
            st.text_area("Transcript Preview", transcript_text[:1000], height=200)

        with st.spinner("Getting clip timestamps from GPT..."):
            clips = ask_gpt_for_multiple_clips(transcript_text, clip_length=clip_length, number_of_clips=num_clips)

        with st.spinner(f"Creating {len(clips)} clips..."):
            output_files = create_multiple_clips(video_path, clips)

        st.success(f"🎉 Created {len(output_files)} clips!")
        for f in output_files:
            st.video(f)
