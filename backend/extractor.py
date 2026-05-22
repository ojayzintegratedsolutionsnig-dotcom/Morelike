import os
import yt_dlp
import re
import tempfile
import json
import requests


def _extract_transcript_from_watch_page(video_id):
    """
    Parse captions straight from the watch page HTML — no yt-dlp, no InnerTube.
    This avoids the bot-detection that blocks datacenter IPs.
    """
    try:
        html = requests.get(
            f'https://www.youtube.com/watch?v={video_id}',
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
            },
            timeout=20
        ).text
    except Exception as e:
        print(f"DEBUG: Watch page fetch failed for {video_id}: {e}")
        return None

    # Extract ytInitialPlayerResponse JSON
    match = re.search(r'(?:var\s+ytInitialPlayerResponse\s*=\s*|window\["ytInitialPlayerResponse"\]\s*=\s*)(\{.+?\});\s*(?:var\s|function\s|</script>)', html, re.DOTALL)
    if not match:
        match = re.search(r'ytInitialPlayerResponse\s*=\s*(\{.+?\});', html, re.DOTALL)
    if not match:
        # Try the JSON-in-script approach: find in any script tag
        for m in re.finditer(r'ytInitialPlayerResponse\s*=\s*(\{.+?\});', html, re.DOTALL):
            try:
                data = json.loads(m.group(1))
                if 'captions' in data:
                    match = m
                    break
            except json.JSONDecodeError:
                continue
    if not match:
        print(f"DEBUG: Could not find ytInitialPlayerResponse for {video_id}")
        return None

    try:
        player_response = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        print(f"DEBUG: JSON parse error for {video_id}: {e}")
        return None

    captions = player_response.get('captions', {}).get('playerCaptionsTracklistRenderer', {})
    caption_tracks = captions.get('captionTracks', [])

    if not caption_tracks:
        print(f"DEBUG: No caption tracks in player response for {video_id}")
        return None

    # Prefer English, manual or auto
    best_url = None
    for track in caption_tracks:
        lang = track.get('languageCode', '')
        if lang in ('en', 'en-US', 'en-GB'):
            best_url = track.get('baseUrl', '')
            break
    if not best_url:
        # Take the first available track
        best_url = caption_tracks[0].get('baseUrl', '')

    if not best_url:
        print(f"DEBUG: No caption URL for {video_id}")
        return None

    try:
        resp = requests.get(best_url, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        if resp.status_code != 200:
            print(f"DEBUG: Caption fetch HTTP {resp.status_code} for {video_id}")
            return None
        text = _parse_xml_transcript(resp.text)
        if text and len(text) > 50:
            print(f"DEBUG: Watch-page transcript extracted for {video_id} ({len(text)} chars)")
            return text
    except Exception as e:
        print(f"DEBUG: Caption fetch error for {video_id}: {e}")

    return None


def _parse_xml_transcript(xml_str):
    """Parse YouTube's XML transcript format into plain text."""
    # Strip XML tags, keep text content
    text = re.sub(r'<text[^>]*>', '', xml_str)
    text = re.sub(r'</text>', ' ', text)
    # Decode common entities
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&quot;', '"').replace('&#39;', "'")
    text = text.replace('\\n', ' ').replace('\n', ' ')
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


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


def get_transcript(video_id, progress_callback=None, fast_only=False):
    """
    Extract English subtitles from YouTube.
    Tries fast methods first (watch-page, transcript-api).
    Only falls back to slow yt-dlp methods if fast_only=False.
    Returns (text, was_bot_blocked) — was_bot_blocked=True if YouTube rejected the request.
    """
    video_url = f'https://www.youtube.com/watch?v={video_id}'

    # ── Method 0: parse captions from watch page (fast, ~1-3s) ──
    text = _extract_transcript_from_watch_page(video_id)
    if text:
        return text, False

    # ── Method 3: youtube-transcript-api (fast, ~2-5s) ─────────
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import RequestBlocked, IpBlocked
        api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id, languages=['en', 'en-US', 'en-GB'])
        if transcript:
            text = ' '.join([snippet.text for snippet in transcript])
            if text and len(text) > 50:
                print(f"DEBUG: Subtitle extracted via API for {video_id} ({len(text)} chars)")
                return text, False
    except (RequestBlocked, IpBlocked) as e:
        print(f"DEBUG: Bot-blocked for {video_id}: {e}")
        return None, True
    except Exception as e:
        print(f"DEBUG: transcript-api error for {video_id}: {e}")

    # If we got here and fast_only, skip the slow yt-dlp methods
    if fast_only:
        print(f"DEBUG: Skipping slow methods for {video_id} (fast_only)")
        return None, False

    # ── Method 1: yt-dlp download subtitles to temp dir (slow, ~10-30s) ──
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
                return text, False

    # ── Method 2: extract_info to get direct subtitle URLs (slow, ~10-20s) ──
    try:
        ydl_opts2 = {
            'writesubtitles': True, 'writeautomaticsub': True,
            'subtitleslangs': ['en', 'en-US', 'en-GB'],
            'skip_download': True, 'quiet': True, 'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts2) as ydl:
            info = ydl.extract_info(video_url, download=False)
            subtitles = info.get('subtitles', {}) or {}
            auto_captions = info.get('automatic_captions', {}) or {}
            for lang_key in ['en', 'en-US', 'en-GB']:
                sub_list = subtitles.get(lang_key) or auto_captions.get(lang_key)
                if sub_list:
                    sub_url = sub_list[0].get('url') if sub_list else None
                    if sub_url:
                        try:
                            resp = requests.get(sub_url, timeout=15, headers={
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                            })
                            if resp.status_code == 200:
                                text = _parse_vtt(resp.text)
                                if text and len(text) > 50:
                                    print(f"DEBUG: Subtitle extracted via URL for {video_id} ({len(text)} chars)")
                                    return text, False
                        except Exception as e:
                            print(f"DEBUG: URL fetch error for {video_id}: {e}")
                    break
    except Exception as e:
        print(f"DEBUG: extract_info fallback error for {video_id}: {e}")

    print(f"DEBUG: No transcript for {video_id}")
    return None, False


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
    video_meta = []  # Always collected for manual fallback

    if progress_callback:
        progress_callback({
            'status': 'extracting',
            'message': f'Found {total} top videos. Extracting auto-generated transcripts...',
            'progress': 10
        })

    bot_blocked = False
    for idx, v in enumerate(videos):
        title = v.get('title', 'Unknown')
        v_id = v.get('id')
        video_meta.append({'id': v_id, 'title': title, 'url': f'https://youtu.be/{v_id}'})

        current_progress = 10 + int((idx / total) * 80)

        if progress_callback:
            progress_callback({
                'status': 'extracting',
                'message': f'[{idx+1}/{total}] Extracting transcript: {title[:50]}...',
                'progress': current_progress,
                'current': idx + 1,
                'total': total
            })

        # If first video was bot-blocked, skip remaining videos entirely
        if bot_blocked:
            if progress_callback:
                progress_callback({
                    'status': 'warning',
                    'message': f'[{idx+1}/{total}] Skipped (bot-blocked): {title[:40]}',
                    'progress': current_progress
                })
            continue

        text, was_blocked = get_transcript(v_id, progress_callback, fast_only=bot_blocked)
        if was_blocked:
            bot_blocked = True

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
                'status': 'needs_manual',
                'message': 'Auto-extraction blocked. Paste transcripts manually for these videos.',
                'progress': 100,
                'videos': video_meta,
                'total': total
            })
        return {
            'success': True,
            'content': None,
            'videos_processed': 0,
            'video_ids': [],
            'needs_manual': True,
            'video_meta': video_meta
        }

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
