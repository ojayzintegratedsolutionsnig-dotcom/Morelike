import os
import yt_dlp
import time
import random
from apify_client import ApifyClient

# Apify API Configuration
APIFY_API_KEY = os.environ.get('APIFY_API_KEY', '')
APIFY_ACTOR_ID = "faVsWy9VTSNVIhWpR"  # YouTube Transcript Extractor

def clean_url(url):
    """
    Forces the URL to point to the 'Popular' tab so we get
    Viral Hits (Views), not just Recent uploads.
    """
    if "/videos" not in url:
        url = url.rstrip('/') + "/videos"

    # This 'sort=p' parameter tells YouTube: "Show me the most viewed"
    if "sort=p" not in url:
        url += "?view=0&sort=p"

    return url

def get_viral_videos(channel_url, limit, progress_callback=None):
    target_url = clean_url(channel_url)

    if progress_callback:
        progress_callback({
            'status': 'scanning',
            'message': f'🎯 Targeted URL: {target_url}',
            'progress': 5
        })

    ydl_opts = {
        'extract_flat': True,
        'playlistend': limit,
        'quiet': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(target_url, download=False)
            if 'entries' in info:
                return list(info['entries'])
    except Exception as e:
        if progress_callback:
            progress_callback({
                'status': 'error',
                'message': f'Error: {str(e)}',
                'progress': 0
            })
        return []

def get_transcript_apify(video_id, progress_callback=None):
    """
    Get transcript using Apify API for 100% reliability
    Uses actor: faVsWy9VTSNVIhWpR (YouTube Transcript Extractor)
    """
    print(f"DEBUG: Fetching transcript via Apify for video_id: {video_id}")

    try:
        # Initialize Apify client
        client = ApifyClient(APIFY_API_KEY)

        # Prepare the Actor input - this actor expects videoUrl (singular)
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        run_input = {
            "videoUrl": video_url
        }

        # Run the Actor and wait for it to finish
        print(f"DEBUG: Starting Apify actor for {video_id} (URL: {video_url})")
        run = client.actor(APIFY_ACTOR_ID).call(run_input=run_input)

        # Fetch results from the run's dataset
        transcript_text = ""
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            print(f"DEBUG: Apify returned item keys: {item.keys()}")

            # The actor returns {"data": [{"start": "...", "dur": "...", "text": "..."}, ...]}
            if 'data' in item and isinstance(item['data'], list):
                # Extract text from each segment and join
                segments = [seg.get('text', '') for seg in item['data'] if seg.get('text')]
                transcript_text = " ".join(segments)
                print(f"DEBUG: Found {len(segments)} transcript segments")

        if transcript_text:
            print(f"DEBUG: ✅ Successfully got transcript from Apify for {video_id} ({len(transcript_text)} chars)")
            return transcript_text
        else:
            print(f"DEBUG: ⚠️ No transcript data returned from Apify for {video_id}")
            return None

    except Exception as e:
        print(f"DEBUG: ❌ Apify error for {video_id}: {str(e)}")
        import traceback
        print(f"DEBUG: Full traceback: {traceback.format_exc()}")
        return None

def extract_viral_content(channel_url, limit=20, progress_callback=None):
    """
    Main extraction function that can report progress
    Uses Apify for reliable transcript extraction
    """
    if progress_callback:
        progress_callback({
            'status': 'starting',
            'message': '🚀 Initializing Viral Extractor...',
            'progress': 0
        })

    videos = get_viral_videos(channel_url, limit, progress_callback)

    if not videos:
        if progress_callback:
            progress_callback({
                'status': 'error',
                'message': '❌ No videos found. Check URL.',
                'progress': 0
            })
        return None

    full_data = "=== CONTENT BLUEPRINT ANALYSIS ===\n(Sorted by Most Popular of All Time)\n\n"
    count = 0
    total = len(videos)

    if progress_callback:
        progress_callback({
            'status': 'extracting',
            'message': f'✅ Found {total} Viral Hits. Extracting transcripts via Apify...',
            'progress': 10
        })

    for idx, v in enumerate(videos):
        title = v.get('title', 'Unknown')
        v_id = v.get('id')

        # Calculate progress (10% to 90% during extraction)
        current_progress = 10 + int((idx / total) * 80)

        if progress_callback:
            progress_callback({
                'status': 'extracting',
                'message': f'[{idx+1}/{total}] Extracting via Apify: {title[:50]}...',
                'progress': current_progress,
                'current': idx + 1,
                'total': total
            })

        text = get_transcript_apify(v_id, progress_callback)

        if text:
            full_data += f"### VIDEO: {title} ###\nURL: https://youtu.be/{v_id}\n\n{text}\n\n"
            count += 1
            if progress_callback:
                progress_callback({
                    'status': 'success',
                    'message': f'✅ [{idx+1}/{total}] Successfully extracted: {title[:40]}',
                    'progress': current_progress
                })
        else:
            if progress_callback:
                progress_callback({
                    'status': 'warning',
                    'message': f'⚠️ No subtitles found for: {title[:40]}',
                    'progress': current_progress
                })

        # Small delay between Apify calls (Apify handles rate limiting internally)
        time.sleep(random.uniform(1, 2))

    # Save to file
    output_file = "content_blueprint.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(full_data)

    if progress_callback:
        progress_callback({
            'status': 'complete',
            'message': f'🎉 DONE! Saved {count} scripts to "{output_file}"',
            'progress': 100,
            'output_file': output_file,
            'videos_processed': count
        })

    return {
        'success': True,
        'output_file': output_file,
        'videos_processed': count,
        'content': full_data
    }
