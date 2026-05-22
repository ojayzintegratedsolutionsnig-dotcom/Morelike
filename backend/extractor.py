import os
import yt_dlp
import re
import tempfile


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
            'message': f'Scanning: {target_url}',
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


def _parse_vtt(raw):
    """Strip VTT timestamps and HTML tags, return clean text."""
    lines = raw.split('\n')
    out = []
    for line in lines:
        line = line.strip()
        # Skip headers and blank lines
        if not line or line.startswith('WEBVTT') or line.startswith('Kind:') or line.startswith('Language:'):
            continue
        # Skip timestamp lines and cue numbers
        if re.match(r'^\d{2}:\d{2}', line) or re.match(r'^NOTE', line):
            continue
        if line.isdigit():
            continue
        # Strip HTML tags and alignment markers
        clean = re.sub(r'<[^>]+>', '', line)
        clean = re.sub(r'&amp;', '&', clean)
        clean = re.sub(r'&lt;', '<', clean)
        clean = re.sub(r'&gt;', '>', clean)
        clean = re.sub(r'&quot;', '"', clean)
        clean = re.sub(r'&#39;', "'", clean)
        if clean.strip():
            out.append(clean.strip())
    return ' '.join(out)


def get_transcript(video_id, progress_callback=None):
    """
    Extract auto-generated English subtitles from YouTube via yt-dlp.
    Tries download first, falls back to extract_info for direct subtitle URLs.
    """
    video_url = f'https://www.youtube.com/watch?v={video_id}'

    # ── Method 1: download subtitles to temp dir ──────────────────
    with tempfile.TemporaryDirectory() as tmpdir:
        ydl_opts = {
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en', 'en-US', 'en-GB', 'en-orig'],
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            'outtmpl': {'default': f'{tmpdir}/sub.%(ext)s'},
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
        except Exception as e:
            print(f"DEBUG: yt-dlp download error for {video_id}: {e}")

        # Recursive search for subtitle file
        sub_files = []
        for root, dirs, files in os.walk(tmpdir):
            for f in files:
                if f.endswith(('.vtt', '.srt')):
                    sub_files.append(os.path.join(root, f))

        if sub_files:
            sub_path = sub_files[0]
            try:
                with open(sub_path, 'r', encoding='utf-8') as f:
                    raw = f.read()
            except UnicodeDecodeError:
                with open(sub_path, 'r', encoding='latin-1') as f:
                    raw = f.read()

            text = _parse_vtt(raw)
            if text and len(text) > 50:
                print(f"DEBUG: Subtitle extracted for {video_id} ({len(text)} chars)")
                return text

    # ── Method 2: use extract_info to get direct subtitle URLs ────
    try:
        ydl_opts2 = {
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en', 'en-US', 'en-GB'],
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts2) as ydl:
            info = ydl.extract_info(video_url, download=False)
            subtitles = info.get('subtitles', {}) or {}
            auto_captions = info.get('automatic_captions', {}) or {}

            for lang_key in ['en', 'en-US', 'en-GB']:
                sub_list = subtitles.get(lang_key) or auto_captions.get(lang_key)
                if sub_list:
                    sub_url = None
                    for fmt in sub_list:
                        if fmt.get('ext') in ('vtt', 'srv1', 'srv2', 'srv3'):
                            sub_url = fmt.get('url')
                            break
                    if not sub_url and sub_list:
                        sub_url = sub_list[0].get('url')
                    if sub_url:
                        import requests
                        try:
                            resp = requests.get(sub_url, timeout=30, headers={
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                            })
                            if resp.status_code == 200:
                                text = _parse_vtt(resp.text)
                                if text and len(text) > 50:
                                    print(f"DEBUG: Subtitle extracted via URL for {video_id} ({len(text)} chars)")
                                    return text
                        except Exception as e:
                            print(f"DEBUG: URL subtitle fetch error for {video_id}: {e}")
    except Exception as e:
        print(f"DEBUG: extract_info fallback error for {video_id}: {e}")

    # ── Method 3: youtube-transcript-api (direct timedtext) ──────
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id, languages=['en', 'en-US', 'en-GB'])
        if transcript:
            text = ' '.join([snippet.text for snippet in transcript])
            if text and len(text) > 50:
                print(f"DEBUG: Subtitle extracted via API for {video_id} ({len(text)} chars)")
                return text
    except Exception as e:
        print(f"DEBUG: transcript-api error for {video_id}: {e}")

    print(f"DEBUG: No transcript for {video_id}")
    return None


def extract_viral_content(channel_url, limit=20, progress_callback=None):
    """
    Main extraction: scan top videos → fetch auto-generated transcripts via yt-dlp.
    No external APIs needed — yt-dlp handles both video discovery and transcripts.
    """
    if progress_callback:
        progress_callback({
            'status': 'starting',
            'message': 'Initializing YouTube extractor...',
            'progress': 0
        })

    effective_limit = min(limit, 3)
    videos = get_viral_videos(channel_url, effective_limit, progress_callback)

    if not videos:
        if progress_callback:
            progress_callback({
                'status': 'error',
                'message': 'No videos found. Check URL.',
                'progress': 0
            })
        return None

    full_data = "=== CONTENT BLUEPRINT ANALYSIS ===\n(Sorted by Most Popular of All Time)\n\n"
    count = 0
    total = len(videos)
    video_ids = []

    if progress_callback:
        progress_callback({
            'status': 'extracting',
            'message': f'Found {total} top videos. Extracting auto-generated transcripts...',
            'progress': 10
        })

    for idx, v in enumerate(videos):
        title = v.get('title', 'Unknown')
        v_id = v.get('id')

        current_progress = 10 + int((idx / total) * 80)

        if progress_callback:
            progress_callback({
                'status': 'extracting',
                'message': f'[{idx+1}/{total}] Extracting transcript: {title[:50]}...',
                'progress': current_progress,
                'current': idx + 1,
                'total': total
            })

        text = get_transcript(v_id, progress_callback)

        if text:
            full_data += f"### VIDEO: {title} ###\nURL: https://youtu.be/{v_id}\n\n{text}\n\n"
            count += 1
            video_ids.append(v_id)
            if progress_callback:
                progress_callback({
                    'status': 'success',
                    'message': f'[{idx+1}/{total}] Transcript extracted: {title[:40]}',
                    'progress': current_progress
                })
        else:
            if progress_callback:
                progress_callback({
                    'status': 'warning',
                    'message': f'[{idx+1}/{total}] No transcript available: {title[:40]}',
                    'progress': current_progress
                })

    if count == 0:
        if progress_callback:
            progress_callback({
                'status': 'error',
                'message': 'No transcripts found on any video. The channel may have captions disabled.',
                'progress': 0
            })
        return None

    # Save to file
    output_file = "content_blueprint.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(full_data)

    if progress_callback:
        progress_callback({
            'status': 'complete',
            'message': f'Done. Extracted transcripts from {count} video(s).',
            'progress': 100,
            'output_file': output_file,
            'videos_processed': count
        })

    return {
        'success': True,
        'output_file': output_file,
        'videos_processed': count,
        'content': full_data,
        'video_ids': video_ids
    }
