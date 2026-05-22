import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from openai import OpenAI
import os
from dotenv import load_dotenv
import threading
import uuid
import base64
import json
import re
import urllib.request
from functools import wraps
from extractor import extract_viral_content
from tokens import init_db, is_token_valid, get_credits, use_credit, create_token
from tokens import claim_token_by_email, log_action, save_feedback, get_all_feedback, save_reply
from tokens import get_plan_limits, PLAN_CONFIG
from emailer import send_token_email, send_reply_email

load_dotenv()

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

init_db()

DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

deepseek_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com") if DEEPSEEK_API_KEY else None
groq_client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1") if GROQ_API_KEY else None

admin_sessions = set()

extraction_status = {
    'running': False,
    'progress': 0,
    'message': '',
    'status': 'idle'
}

extracted_subtitles = {
    'content': '',
    'videos_processed': 0,
    'video_ids': []
}

last_generated_package = {
    'content': '',
    'title': ''
}

# ── Auth helpers ──────────────────────────────────────────────

def require_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token or not is_token_valid(token):
            return jsonify({'error': 'Invalid or expired token'}), 401
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        admin_token = request.headers.get('X-Admin-Token', '')
        if admin_token not in admin_sessions:
            return jsonify({'error': 'Admin access required'}), 401
        return f(*args, **kwargs)
    return decorated


# ── Prompts ───────────────────────────────────────────────────

VIRAL_DNA_SYSTEM_INSTRUCTION = """This file contains the transcripts of the top viral videos from a specific YouTube creator.
Reverse-engineer their "Viral Algorithm" so we can produce new content in the EXACT SAME NICHE.

0. THE NICHE IDENTITY (CRITICAL — DO THIS FIRST)
- What is the channel's SPECIFIC topic/niche? (e.g., "Bible commentary for young adults," "SaaS marketing tips," "horror story narration")
- Who is the target audience? (age, interest, pain point)
- What are 3-5 recurring themes or subtopics across the transcripts?
- State the niche clearly: "This channel is about [X] for [Y audience]."

1. THE HOOK ARCHITECTURE (0:00 - 0:30)
- How exactly do they start? (e.g., "They start with a visual contradiction," or "They ask a rhetorical question")
- What is the average word count before the first "cut" or topic shift?

2. THE RETENTION LOOPS
- Identify the specific phrases they use to keep people watching (e.g., "I'll show you that in a minute," or "But here is the catch").
- How frequently do they inject a "pattern interrupt"?

3. THE SENTENCE RHYTHM
- Analyze the sentence length. Are they short and punchy? Or long and descriptive?
- Give me 3 examples of "Transition Sentences" they use to move between points.

4. THE TEMPLATE
- Create a blank "Fill-in-the-Blanks" script template that follows their exact pacing structure, which can be used for ANY topic WITHIN THIS NICHE."""

TITLE_IDEAS_SYSTEM_INSTRUCTION = """You are a viral content strategist. Given the Viral DNA analysis below, generate 3 video title ideas.

CRITICAL CONSTRAINT: The analyzed channel's niche is:
{niche}

ALL 3 titles MUST stay within this exact niche. Do NOT change topics, do NOT drift into another genre, do NOT suggest titles about a different subject. If the channel is about Bible commentary, every title must be about Bible commentary. If the channel is about cooking, every title must be about cooking.

The Viral DNA is:
{viral_dna}

Generate exactly 3 titles. Each title must:
- Stay strictly within the channel's niche (see constraint above)
- Use the hook patterns and retention tactics identified in the DNA
- Be specific enough to spark curiosity
- Avoid clickbait cliches that the original creator wouldn't use
- Sound like a real video this creator would actually publish

Return EXACTLY in this format (no extra text, no commentary):

1. [First title]
2. [Second title]
3. [Third title]"""

MASTER_PACKAGE_SYSTEM_INSTRUCTION = """# ROLE: AI YouTube Content Engine
You analyze, model, and recreate YouTube content styles. Match style, not phrasing. Outputs are fully original.

# CONTEXT
## Viral DNA (Channel Style Blueprint)
{viral_dna}

## Visual Style Profile (from reference image analysis)
{visual_json}

## Thumbnail Style Data (from thumbnail analysis)
{thumbnail_json}

## Transcript Excerpts (from the channel's top-performing videos)
{transcript_context}

## Target
Niche: {niche}
Duration: {target_length} minutes (~{target_length} × 150 words)

# OUTPUT FORMAT
Produce the following sections in order. Every section is mandatory.

═══════════════════════════════════
USER PLAN: $8 Creator Plan
SCRIPT DURATION: [X] min [Y] sec (Formula: [W] words ÷ 150 words/min)
═══════════════════════════════════

SCRIPT DNA
	Niche: [one-line niche statement]
	Target word count: [number] (±5%)
	Pacing: [words/sec, sentence rhythm from DNA]
	Hook style: [how the DNA hooks, applied to this script]
	Emotional flow: [tension arc across the script]
	Global Visual Style: [from Visual Style Profile — art style, color palette, lighting setup, render quality, atmosphere. This exact style is fully embedded in every image and video prompt below. No separate style section needed — each prompt is self-contained.]

	────────────────────────────────────────
	FINAL SEO TITLE
	(after A/B analysis — winner with max 2 hyper-optimized SEO emojis)

	DESCRIPTION
	- Above-fold hook (first 2 lines): [hook using high-search-volume keywords]
	- Body: [3-5 sentences describing the video, max 2 relevant emojis as visual anchors]
	- Hashtags: #tag1 #tag2 #tag3

	TAGS/KEYWORDS
	tag1, tag2, tag3

	════════════════════════════════════════
	THUMBNAIL DESIGN
	════════════════════════════════════════
	Design as a cinematic movie poster using thumbnail style data above.

	Concept A — Emotion-Forward:
	  Focal Point: [exactly what the viewer sees — character close-up or epic scene]
	  Emotional Hook: [the question this image plants]
	  Composition: [foreground frame → midground subject → background atmosphere]
	  Text Overlay: [wording (1-4 words), cinematic serif font, gold/emboss texture, drop shadow, position]
	  Color + Lighting: [palette + key light + rim + volumetrics]

	Concept B — CTR-Optimized Alternative:
	  (Different composition, different emotional angle, different text treatment)

	A/B Analysis:
	  Concept A strength: [which CTR lever]
	  Concept B strength: [which CTR lever]
	  Final Recommendation: [winner + niche-specific reasoning]

	════════════════════════════════════════
	BEATS (Voice + Image + Video per Beat, max 8 seconds each)
	════════════════════════════════════════
	Generate the full script as numbered BEATS. Each beat = ~8 seconds (~20 spoken words). A {target_length}-minute video needs roughly {target_length} × 7.5 beats. Generate ALL beats in full — never truncate.

	CRITICAL: Every image and video prompt must be a fully detailed, self-contained, copy-paste-ready prompt. Bake the Global Visual Style (art style, color palette, lighting, composition, render quality, atmosphere) directly into every single prompt. NO shorthand like "| Style: tags" — the style IS the prompt. Each prompt must be complete enough to paste directly into an AI image/video generator with zero context.

	BEAT 1 — [Hook Moment]
	VOICE OVER: [Pure dialogue. No stage directions. No brackets. Copy-paste ready for TTS.]

	IMAGE PROMPT: [Fully detailed, self-contained text-to-image prompt. Include: subject description + pose/expression + environment + composition/framing + lighting setup (key light direction, quality, color temp) + color palette (3-5 named colors) + art style + render quality + atmosphere + aspect ratio. The global visual style is fully baked into this description. No references, no shorthand, no pipe-delimited tags — everything spelled out in detailed prose.]

	VIDEO PROMPT: [Fully detailed, self-contained text-to-video prompt. Include: shot type + camera movement + subject action/motion + environment dynamics (wind, particles, water) + lighting animation (how light moves/changes) + depth/parallax layers + transition out + art style + color palette + atmosphere + aspect ratio. The global visual style is fully baked into this description. No references, no shorthand, no pipe-delimited tags — everything spelled out in detailed prose.]

	BEAT 2 — [Beat Name]
	VOICE OVER: [...]
	IMAGE PROMPT: [Fully detailed, self-contained. Subject + environment + composition + lighting + color palette + art style + render quality + atmosphere + aspect ratio. All style details spelled out in full prose.]
	VIDEO PROMPT: [Fully detailed, self-contained. Shot + camera + subject action + environment dynamics + lighting animation + depth + transition + art style + color palette + atmosphere + aspect ratio. All style details spelled out in full prose.]

	(Continue ALL beats — BEAT 3, BEAT 4, BEAT 5, BEAT 6... all the way to the final beat. EVERY beat gets Voice Over + Image Prompt + Video Prompt. NO skipping. NO truncation. NO "(Continue...)". Every image and video prompt is fully self-contained with the global visual style baked in — detailed prose, no shorthand, no pipe tags.)

═══════════════════════════════════
INTERNAL REVIEW (Mandatory — run silently, do NOT output the draft)
═══════════════════════════════════
Before finalizing, review every section above (Title, Description, Thumbnail, ALL Beats) against these 5 hostile critics:

1. THE ENDLESS SCROLLER — Would they leave in 2 seconds? Is the hook a generic question or a genuine pattern interrupt? If the first beat doesn't create a curiosity gap, it fails.

2. THE SEEN-IT-ALL CYNIC — What feels derivative, recycled, or AI-slop? Where did you default to "delve into" / "unlock the secrets" / "in a world where"? Flag every cliché phrase and every beat that sounds like every other video in this niche.

3. THE SILENT JUDGE — What is unclear, confusing, or wasting time? Flag any beat where the viewer's mental response is "get to the point." Flag any voice-over line that would sound unnatural spoken aloud.

4. THE SHARE-GATEKEEPER — Why would someone feel embarrassed to share this? Is the emotional tone cringe, try-hard, or inauthentic? Does it match how real humans in this niche actually talk?

5. THE PLATFORM NATIVE — Where does retention drop? Flag the exact beat number where pacing dies, where the middle sags, where the payoff disappoints. Is there a pattern interrupt every 15-20 seconds? Does the ending earn the watch?

For each critic, identify at least one CRITICAL FAILURE. Then REBUILD:
- Hook weak? Replace it with a specific, visual, surprising pattern interrupt from the Viral DNA.
- Middle dragging? Cut filler beats, inject a retention loop (open loop, stakes raise, or format twist).
- Ending flat? Add a twist, an emotional payoff, or a specific call-to-comment tied to the topic.
- Cliché phrases? Rewrite with concrete, niche-specific language the original creator would actually use.

Output ONLY the final, post-review version. Never show the draft or the critique.

═══════════════════════════════════
VOICE PROMPT
═══════════════════════════════════
Tone: [vocal tone — warm, urgent, mysterious, authoritative]
Mood Arc: [how emotion shifts — curious → tense → relieved]
Pacing: [tempo — rapid opening, slow contemplation, building urgency]
Vocal Register: [pitch, breathiness, projection]
{{if multiple characters, include per character: Character [Name]: [vocal quality, accent, age feel, personality in voice]}}

═══════════════════════════════════
ALIGNMENT SUMMARY
═══════════════════════════════════
Beat 1 → Voice: "[line]" → Image: [scene] → Video: [motion]
Beat 2 → Voice: "[line]" → Image: [scene] → Video: [motion]
(All beats mapped. Shows visual-audio sync.)"""


# ── Helpers ────────────────────────────────────────────────────

def extract_niche(viral_dna):
    """Pull the niche description from the Viral DNA analysis."""
    import re
    match = re.search(r'This channel is about\s*(.+?)(?:\n|$)', viral_dna, re.IGNORECASE)
    if match:
        return match.group(1).strip().rstrip('.')
    # Fallback: grab the first line under "0. THE NICHE IDENTITY"
    match = re.search(r'0\.?\s*THE NICHE IDENTITY.*?\n(.+?)(?:\n\n|\n[#\d]|\n[A-Z])', viral_dna, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip().rstrip('.')[:200]
    return "the creator's niche"


# ── AI helpers ────────────────────────────────────────────────

def call_ai(system_prompt, user_message, max_tokens=8192):
    """Call DeepSeek for all text generation. Single provider, no fallback chain."""
    import time
    if not deepseek_client:
        raise Exception("DeepSeek API key not configured. Set DEEPSEEK_API_KEY.")
    for attempt in range(2):
        try:
            response = deepseek_client.chat.completions.create(
                model='deepseek-chat',
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=1.0,
                max_tokens=max_tokens,
                timeout=300.0,
            )
            return response.choices[0].message.content
        except Exception as e:
            if attempt < 1:
                time.sleep(3)
            else:
                raise Exception(f"DeepSeek error: {str(e)}")


def call_groq_vision(system_prompt, user_message, image_base64_list, max_tokens=4096):
    """Groq Vision analysis — uses llama-4-scout for structured image extraction."""
    import time

    if not groq_client:
        raise Exception("Groq API key required for vision analysis")

    user_content = [{"type": "text", "text": user_message}]
    for b64 in image_base64_list:
        user_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
        })

    for attempt in range(2):
        try:
            response = groq_client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.3,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                timeout=120.0,
            )
            raw = response.choices[0].message.content
            return json.loads(raw)
        except Exception as e:
            if attempt < 1:
                time.sleep(2)
            else:
                raise Exception(f"Groq Vision error: {str(e)}")


STYLE_TAG_MAP = {
    'warm cinematic glow': 'golden-hour-cinematic',
    'golden hour lighting': 'golden-hour-cinematic',
    'amber rim light': 'golden-hour-cinematic',
    'soft warm backlight': 'golden-hour-cinematic',
    'dramatic shadows': 'high-contrast-dramatic',
    'high contrast chiaroscuro': 'high-contrast-dramatic',
    'deep shadows': 'high-contrast-dramatic',
    'volumetric fog': 'atmospheric-haze',
    'atmospheric haze': 'atmospheric-haze',
    'dust motes': 'atmospheric-haze',
    'god rays': 'divine-light-beams',
    'divine light rays': 'divine-light-beams',
    'heavenly backlight': 'divine-light-beams',
    'cinematic lighting': 'cinematic-lighting',
    'movie trailer lighting': 'cinematic-lighting',
    'pixar-style': 'stylized-3d-soft',
    'dreamworks-style': 'stylized-3d-soft',
    'unreal-engine': 'cinematic-realtime',
    'photorealistic': 'photorealistic',
    'stylized 2d': 'stylized-2d-flat',
    'flat illustration': 'stylized-2d-flat',
}


def normalize_visual_json(raw_json):
    """Normalize style tags from Groq Vision into canonical tokens."""
    if not raw_json:
        return raw_json
    tags = raw_json.get('style_tags', [])
    if tags:
        normalized = []
        seen = set()
        for tag in tags:
            tag_lower = tag.lower().strip()
            canonical = STYLE_TAG_MAP.get(tag_lower, tag_lower.replace(' ', '-'))
            if canonical not in seen:
                normalized.append(canonical)
                seen.add(canonical)
        raw_json['style_tags'] = normalized
    return raw_json


# ── Vision prompts ─────────────────────────────────────────────

VISUAL_ANALYSIS_SYSTEM_INSTRUCTION = """Analyze this reference image from a video. Extract objective visual data for AI image/video recreation.
Return ONLY a JSON object with these exact keys:
{
  "art_style": "stylized 3D / 2D illustration / photorealistic / cinematic animation / etc.",
  "camera_angle": "eye-level / low angle / high angle / dutch tilt / aerial / etc.",
  "lighting": "key light direction + quality (soft/hard) + color temperature",
  "color_palette": "dominant 3-5 colors with descriptive names",
  "subject_description": "main subject — pose, expression, clothing, distinguishing features",
  "facial_expression": "emotion on face — neutral, intense, joyful, sorrowful, etc.",
  "emotion": "overall emotional tone of the scene",
  "environment": "location, time of day, atmospheric conditions",
  "composition": "subject placement, framing, depth layers (foreground/midground/background)",
  "foreground_elements": "objects/elements closest to camera",
  "background_elements": "objects/environment in background",
  "cinematic_style": "Pixar-like / Unreal Engine cinematic / anime / hand-drawn / etc.",
  "time_of_day": "golden hour / midday / night / twilight / interior no window / etc.",
  "render_quality": "low-poly / high-detail / painterly / smooth / textured",
  "style_tags": ["tag1", "tag2", "tag3"]
}
Be extremely detailed and objective. No creative writing. No storytelling. Just visual facts."""

THUMBNAIL_ANALYSIS_SYSTEM_INSTRUCTION = """Analyze this YouTube thumbnail image. Extract objective design data.
Return ONLY a JSON object with these exact keys:
{
  "text_style": "font family feel, size, weight, color, effects (emboss/shadow/gradient)",
  "text_placement": "top center / bottom center / upper third / etc.",
  "composition": "focal point placement, depth layers, rule of thirds usage",
  "color_contrast": "dominant contrast strategy — warm subject + cool bg / complementary / monochromatic",
  "emotion_trigger": "what emotion does this thumbnail provoke — curiosity, awe, urgency, fear, hope",
  "visual_hooks": ["hook1", "hook2"],
  "art_style": "same categories as video reference",
  "lighting": "thumbnail-specific lighting treatment",
  "color_palette": "dominant 3-5 colors"
}
Be detailed and objective. Focus on what drives CTR — emotion, contrast, readability, curiosity gap."""


# ── Extraction ────────────────────────────────────────────────

def progress_callback(data):
    global extraction_status
    extraction_status.update(data)
    socketio.emit('progress', data)


def run_extraction(channel_url, limit):
    global extraction_status, extracted_subtitles
    extraction_status['running'] = True
    try:
        result = extract_viral_content(channel_url, limit, progress_callback)
        extraction_status['running'] = False
        if result and result.get('content'):
            extracted_subtitles['content'] = result['content']
            extracted_subtitles['videos_processed'] = result.get('videos_processed', 0)
            extracted_subtitles['video_ids'] = result.get('video_ids', [])
        return result
    except Exception as e:
        extraction_status['running'] = False
        socketio.emit('progress', {
            'status': 'error',
            'message': f'Error: {str(e)}',
            'progress': 0
        })


# ── Public endpoints ──────────────────────────────────────────

@app.route('/api/validate-token', methods=['POST'])
def validate_token():
    data = request.json or {}
    token = data.get('token', '')
    if not token:
        return jsonify({'valid': False, 'error': 'Token is required'}), 400
    valid = is_token_valid(token)
    if valid:
        creds = get_credits(token)
        plan = creds.get('plan', 'basic')
        limits = PLAN_CONFIG.get(plan, PLAN_CONFIG['basic'])
        return jsonify({
            'valid': True,
            'credits': creds['credits'],
            'email': creds.get('email'),
            'plan': plan,
            'limits': limits
        })
    return jsonify({'valid': False, 'error': 'Invalid or expired token'})


@app.route('/api/claim-token', methods=['POST'])
def claim_token():
    data = request.json or {}
    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({'error': 'Email is required'}), 400
    if not email.endswith('@gmail.com'):
        return jsonify({'error': 'Only @gmail.com emails are accepted'}), 400

    result = claim_token_by_email(email)
    if result:
        plan = result.get('plan', 'basic')
        limits = PLAN_CONFIG.get(plan, PLAN_CONFIG['basic'])
        return jsonify({
            'success': True,
            'token': result['token'],
            'credits': result['credits'],
            'plan': plan,
            'limits': limits
        })

    # No token with lemon_order_id — no purchase found
    return jsonify({'error': 'No completed purchase found for this email. Please check your email or contact support.'}), 404


@app.route('/api/webhook/lemonsqueezy', methods=['POST'])
def lemonsqueezy_webhook():
    import hmac
    import hashlib

    # Verify webhook signature — reject all unsigned requests
    webhook_secret = os.environ.get('LEMON_SQUEEZY_WEBHOOK_SECRET', '')
    if not webhook_secret:
        print('[SECURITY] Webhook rejected: no LEMON_SQUEEZY_WEBHOOK_SECRET configured')
        return jsonify({'error': 'Webhook not configured'}), 500

    signature = request.headers.get('X-Signature', '')
    raw_body = request.get_data(as_text=True)

    expected = None
    if signature.startswith('sha256='):
        expected = 'sha256=' + hmac.new(
            webhook_secret.encode('utf-8'),
            raw_body.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    if not expected or not hmac.compare_digest(expected, signature):
        print('[SECURITY] Webhook rejected: invalid signature')
        return jsonify({'error': 'Invalid signature'}), 401

    data = request.json or {}
    event = data.get('meta', {}).get('event_name', '')
    if event != 'order_created':
        return jsonify({'received': True})

    order_data = data.get('data', {}).get('attributes', {})
    email = order_data.get('user_email', '') or order_data.get('email', '')
    order_id = data.get('data', {}).get('id', '')

    # Detect which plan was purchased from the product ID
    first_item = order_data.get('first_order_item', {}) or {}
    product_id = first_item.get('product_id', '')

    # Map product IDs to plans — product IDs configurable via env
    PRO_PRODUCT_ID = os.environ.get('LEMON_SQUEEZY_PRODUCT_PRO', '')
    PROMAX_PRODUCT_ID = os.environ.get('LEMON_SQUEEZY_PRODUCT_PROMAX', '')
    if PROMAX_PRODUCT_ID and product_id == PROMAX_PRODUCT_ID:
        plan = 'promax'
    elif PRO_PRODUCT_ID and product_id == PRO_PRODUCT_ID:
        plan = 'pro'
    else:
        plan = 'basic'

    if not email:
        return jsonify({'error': 'No email in order'}), 400

    token = create_token(email=email, lemon_order_id=order_id, plan=plan)
    try:
        send_token_email(email, token)
    except Exception as e:
        print(f"Failed to send email: {e}")

    return jsonify({'success': True, 'token': token, 'plan': plan})


@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.json or {}
    password = data.get('password', '')
    if password == ADMIN_PASSWORD:
        session_token = uuid.uuid4().hex
        admin_sessions.add(session_token)
        return jsonify({'success': True, 'admin_token': session_token})
    return jsonify({'error': 'Invalid password'}), 401


# ── Token-gated portal endpoints ──────────────────────────────

@app.route('/api/credits', methods=['GET'])
@require_token
def credits():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    creds = get_credits(token)
    if creds:
        plan = creds.get('plan', 'basic')
        creds['limits'] = PLAN_CONFIG.get(plan, PLAN_CONFIG['basic'])
    return jsonify(creds or {})


@app.route('/api/extract', methods=['POST'])
def extract():
    if extraction_status['running']:
        return jsonify({'error': 'Extraction already running'}), 400

    data = request.json
    channel_url = data.get('channel_url')
    limit = data.get('limit', 20)

    if not channel_url:
        return jsonify({'error': 'Channel URL is required'}), 400

    import re
    yt_pattern = r'^https?://(www\.)?(youtube\.com|youtu\.be)/(@|channel/|c/|user/)?[\w\-]+'
    if not re.match(yt_pattern, channel_url.strip()):
        return jsonify({'error': 'Invalid YouTube channel URL. Expected format: https://www.youtube.com/@ChannelName'}), 400

    thread = threading.Thread(target=run_extraction, args=(channel_url, limit))
    thread.daemon = True
    thread.start()

    return jsonify({'message': 'Extraction started', 'status': 'started'})


@app.route('/api/debug-transcript', methods=['GET'])
def debug_transcript():
    """Test transcript extraction on a known-good video and report per-method results."""
    test_video_id = 'YWbBrbOaz58'  # Known to have English captions
    results = {'video_id': test_video_id}

    # Method 1: yt-dlp download
    try:
        import yt_dlp, tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts = {
                'writesubtitles': True, 'writeautomaticsub': True,
                'subtitleslangs': ['en', 'en-US', 'en-GB', 'en-orig'],
                'skip_download': True, 'quiet': True, 'no_warnings': True,
                'outtmpl': {'default': f'{tmpdir}/sub.%(ext)s'},
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f'https://www.youtube.com/watch?v={test_video_id}'])
            found = []
            for root, dirs, files in os.walk(tmpdir):
                for f in files:
                    if f.endswith(('.vtt', '.srt')):
                        found.append(os.path.join(root, f))
            results['method1_ytdlp'] = f'OK: {len(found)} files' if found else 'FAIL: no subtitle files produced'
    except Exception as e:
        results['method1_ytdlp'] = f'FAIL: {type(e).__name__}: {str(e)[:200]}'

    # Method 2: yt-dlp extract_info + URL fetch
    try:
        import yt_dlp
        ydl_opts2 = {
            'writesubtitles': True, 'writeautomaticsub': True,
            'subtitleslangs': ['en'], 'skip_download': True,
            'quiet': True, 'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts2) as ydl:
            info = ydl.extract_info(f'https://www.youtube.com/watch?v={test_video_id}', download=False)
            subtitles = info.get('subtitles', {}) or {}
            auto_captions = info.get('automatic_captions', {}) or {}
            found_url = None
            for lang_key in ['en', 'en-US', 'en-GB']:
                sub_list = subtitles.get(lang_key) or auto_captions.get(lang_key)
                if sub_list:
                    found_url = sub_list[0].get('url') if sub_list else None
                    break
            results['method2_extractinfo'] = f'OK: found URL' if found_url else f'FAIL: no subtitle URL in info. subs={list(subtitles.keys())}, auto={list(auto_captions.keys())}'
    except Exception as e:
        results['method2_extractinfo'] = f'FAIL: {type(e).__name__}: {str(e)[:200]}'

    # Method 3: youtube-transcript-api
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi()
        transcript = api.fetch(test_video_id, languages=['en', 'en-US', 'en-GB'])
        text = ' '.join([snippet.text for snippet in transcript])
        results['method3_transcriptapi'] = f'OK: {len(transcript)} snippets, {len(text)} chars'
    except Exception as e:
        results['method3_transcriptapi'] = f'FAIL: {type(e).__name__}: {str(e)[:200]}'

    # Method 4: raw HTTP fetch of YouTube watch page
    try:
        import requests as req
        resp = req.get(f'https://www.youtube.com/watch?v={test_video_id}', timeout=15,
                       headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        results['method4_rawhttp'] = f'OK: {resp.status_code}, {len(resp.text)} chars'
    except Exception as e:
        results['method4_rawhttp'] = f'FAIL: {type(e).__name__}: {str(e)[:200]}'

    return jsonify(results)


@app.route('/api/status', methods=['GET'])
def status():
    return jsonify(extraction_status)


@app.route('/api/subtitles', methods=['GET'])
def get_subtitles():
    if not extracted_subtitles['content']:
        return jsonify({'error': 'No subtitles available. Please extract videos first.'}), 404
    return jsonify({
        'content': extracted_subtitles['content'],
        'videos_processed': extracted_subtitles['videos_processed'],
        'video_ids': extracted_subtitles['video_ids']
    })


@app.route('/api/generate-viral-dna', methods=['POST'])
def generate_viral_dna():
    data = request.json or {}
    subtitles = data.get('subtitles', extracted_subtitles.get('content', ''))

    if not subtitles:
        return jsonify({'error': 'No subtitles provided. Extract or paste first.'}), 400

    stripped = subtitles.strip()
    if len(stripped) < 50:
        return jsonify({'error': 'Not enough content. Please provide at least one full video transcript.'}), 400

    # Only block single-line non-transcript inputs (greetings, one-word chats)
    single_line = stripped.split('\n')[0].strip().lower()
    if len(stripped) < 150 and single_line in ['hello', 'hi', 'hey', 'hi there', 'test', 'testing', 'yo', 'sup']:
        return jsonify({'error': 'Please paste actual video transcripts, not a chat message.'}), 400

    # Trim content to prevent oversized prompts (DeepSeek: 64K context window)
    trimmed = subtitles.strip()
    if len(trimmed) > 30000:
        # Keep first 10K and last 5K — hook patterns in beginning, retention in ending
        trimmed = trimmed[:10000] + "\n\n...[content trimmed]...\n\n" + trimmed[-5000:]

    try:
        viral_dna = call_ai(VIRAL_DNA_SYSTEM_INSTRUCTION, trimmed)
        return jsonify({'viral_dna': viral_dna, 'success': True})
    except Exception as e:
        return jsonify({'error': f'Failed to generate Viral DNA: {str(e)}'}), 500


@app.route('/api/generate-titles', methods=['POST'])
def generate_titles():
    data = request.json or {}
    viral_dna = data.get('viral_dna', '')
    num_titles = data.get('count', 3)

    if not viral_dna:
        return jsonify({'error': 'Viral DNA is required. Generate analysis first.'}), 400

    try:
        niche = extract_niche(viral_dna)
        system_prompt = TITLE_IDEAS_SYSTEM_INSTRUCTION.replace('Generate exactly 3 titles.', f'Generate exactly {num_titles} titles.').replace('ALL 3 titles', f'ALL {num_titles} titles').format(viral_dna=viral_dna, niche=niche)
        result = call_ai(system_prompt, f"Generate {num_titles} title ideas about {niche} based on the Viral DNA.")
        return jsonify({'titles': result, 'success': True})
    except Exception as e:
        return jsonify({'error': f'Failed to generate titles: {str(e)}'}), 500


@app.route('/api/generate-package', methods=['POST'])
@require_token
def generate_package():
    global last_generated_package
    data = request.json or {}
    viral_dna = data.get('viral_dna', '')
    chosen_title = data.get('title', '')
    topic = data.get('topic', '')
    video_length = data.get('video_length', 3)
    visual_json = data.get('visual_json', None)
    thumbnail_json = data.get('thumbnail_json', None)
    transcript_context = data.get('transcript_context', '')

    if not viral_dna:
        return jsonify({'error': 'Viral DNA is required'}), 400
    if not chosen_title:
        return jsonify({'error': 'A chosen title is required'}), 400

    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    creds = get_credits(token)
    if not creds or creds['credits'] <= 0:
        return jsonify({'error': 'No credits remaining. Purchase more to continue.'}), 402

    # Apply plan-based max video length
    plan = creds.get('plan', 'basic')
    limits = PLAN_CONFIG.get(plan, PLAN_CONFIG['basic'])
    max_minutes = limits['max_minutes']

    try:
        video_length = int(video_length)
        video_length = max(1, min(max_minutes, video_length))
    except (ValueError, TypeError):
        video_length = max_minutes

    log_action(token, 'generate_package')

    try:
        niche = extract_niche(viral_dna)

        # Build style context from vision analysis
        vis_str = json.dumps(visual_json, indent=2) if visual_json else 'No visual reference provided — use the Viral DNA to infer visual style.'
        thumb_str = json.dumps(thumbnail_json, indent=2) if thumbnail_json else 'No thumbnail reference provided — use the Viral DNA to infer thumbnail style.'

        # Trim transcript to ~4000 chars for context window economy
        tx_raw = transcript_context.strip() if transcript_context else ''
        if len(tx_raw) > 4500:
            tx_str = tx_raw[:2500] + "\n\n...[trimmed]...\n\n" + tx_raw[-2000:]
        elif tx_raw:
            tx_str = tx_raw
        else:
            tx_str = 'No transcript excerpts available — rely on Viral DNA for speech patterns.'

        system_prompt = MASTER_PACKAGE_SYSTEM_INSTRUCTION.format(
            viral_dna=viral_dna,
            niche=niche,
            target_length=video_length,
            visual_json=vis_str,
            thumbnail_json=thumb_str,
            transcript_context=tx_str
        )
        user_message = f"TITLE: {chosen_title}\nTOPIC: {topic or chosen_title}\nNICHE: {niche}\nTARGET LENGTH: {video_length} minutes"

        result = call_ai(system_prompt, user_message, max_tokens=16384)

        use_credit(token)
        last_generated_package = {'content': result, 'title': chosen_title}
        remaining = get_credits(token)
        return jsonify({
            'package': result,
            'credits_remaining': remaining['credits'] if remaining else 0,
            'success': True
        })
    except Exception as e:
        return jsonify({'error': f'Failed to generate package: {str(e)}'}), 500


@app.route('/api/download-package', methods=['GET'])
@require_token
def download_package():
    content = last_generated_package.get('content', '')
    title = last_generated_package.get('title', 'script')

    if not content:
        return jsonify({'error': 'No package generated yet. Generate a script first.'}), 404

    filename = f"{title[:50].replace(' ', '_').replace('/', '-')}.txt"
    filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    return send_file(filepath, as_attachment=True, download_name=filename)


@app.route('/api/feedback', methods=['POST'])
@require_token
def submit_feedback():
    data = request.json or {}
    message = data.get('message', '').strip()

    if not message:
        return jsonify({'error': 'Feedback message is required'}), 400

    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    creds = get_credits(token)
    email = creds.get('email', '') if creds else ''
    save_feedback(token, message, email)
    log_action(token, 'feedback_submitted')
    return jsonify({'success': True, 'message': 'Thank you for your feedback!'})


# ── Admin endpoints ───────────────────────────────────────────

@app.route('/api/admin/feedback', methods=['GET'])
@require_admin
def admin_feedback():
    feedbacks = get_all_feedback()
    return jsonify({'feedback': feedbacks})


@app.route('/api/admin/reply', methods=['POST'])
@require_admin
def admin_reply():
    data = request.json or {}
    feedback_id = data.get('feedback_id')
    reply_text = data.get('reply', '').strip()
    email = data.get('email', '').strip()

    if not feedback_id or not reply_text:
        return jsonify({'error': 'feedback_id and reply are required'}), 400

    save_reply(feedback_id, reply_text)

    if email:
        try:
            send_reply_email(email, reply_text)
        except Exception as e:
            print(f"Failed to send reply email: {e}")

    return jsonify({'success': True})


@app.route('/api/admin/generate-token', methods=['POST'])
@require_admin
def admin_generate_token():
    data = request.json or {}
    email = data.get('email', '').strip()
    credits = data.get('credits', 3)
    plan = data.get('plan', 'basic')

    if not email:
        return jsonify({'error': 'Email is required'}), 400
    if plan not in PLAN_CONFIG:
        return jsonify({'error': f'Invalid plan. Choose: {", ".join(PLAN_CONFIG.keys())}'}), 400

    try:
        credits = max(1, min(100, int(credits)))
    except (ValueError, TypeError):
        credits = 3

    token = create_token(email=email, credits=credits, plan=plan)
    try:
        send_token_email(email, token)
    except Exception as e:
        print(f"Failed to send email: {e}")

    return jsonify({'success': True, 'token': token, 'email': email, 'credits': credits, 'plan': plan})


@app.route('/api/admin/diag', methods=['GET'])
@require_admin
def admin_diag():
    import time
    results = {}
    # Test outbound connectivity
    import urllib.request
    targets = {
        'httpbin': 'https://httpbin.org/ip',
        'groq': 'https://api.groq.com/openai/v1/models',
        'deepseek': 'https://api.deepseek.com/v1/models',
    }
    for name, url in targets.items():
        try:
            req = urllib.request.Request(url)
            t0 = time.time()
            urllib.request.urlopen(req, timeout=10)
            results[name] = f"OK ({time.time() - t0:.1f}s)"
        except Exception as e:
            results[name] = f"FAIL: {type(e).__name__}: {str(e)[:100]}"

    # Test AI connectivity
    for name, client, model in [
        ('deepseek', deepseek_client, 'deepseek-chat'),
        ('groq', groq_client, 'llama-3.3-70b-versatile'),
    ]:
        if client:
            try:
                t0 = time.time()
                r = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "Say OK"}],
                    max_tokens=5,
                    timeout=15.0,
                )
                results[f'ai_{name}'] = f"OK ({time.time() - t0:.1f}s): {r.choices[0].message.content}"
            except Exception as e:
                results[f'ai_{name}'] = f"FAIL: {type(e).__name__}: {str(e)[:200]}"
        else:
            results[f'ai_{name}'] = "No API key configured"
    return jsonify(results)


# ── Vision Analysis ────────────────────────────────────────────

@app.route('/api/analyze-visuals', methods=['POST'])
@require_token
def analyze_visuals():
    """Analyze 3-5 video reference images via Groq Vision. Returns structured JSON."""
    if not groq_client:
        return jsonify({'error': 'Groq API key not configured'}), 500

    files = request.files.getlist('images')
    if not files or len(files) < 3:
        return jsonify({'error': 'Minimum 3 reference images required'}), 400
    if len(files) > 5:
        return jsonify({'error': 'Maximum 5 reference images allowed'}), 400

    try:
        image_b64_list = []
        for f in files:
            if f.content_type not in ('image/jpeg', 'image/png', 'image/webp'):
                return jsonify({'error': f'Unsupported format: {f.content_type}. Use JPEG, PNG, or WebP.'}), 400
            img_bytes = f.read()
            if len(img_bytes) > 4 * 1024 * 1024:
                return jsonify({'error': f'{f.filename} exceeds 4MB limit'}), 400
            image_b64_list.append(base64.b64encode(img_bytes).decode('utf-8'))

        results = []
        for i, b64 in enumerate(image_b64_list):
            analysis = call_groq_vision(
                VISUAL_ANALYSIS_SYSTEM_INSTRUCTION,
                "Analyze this reference video image. Return structured JSON.",
                [b64]
            )
            results.append(normalize_visual_json(analysis))

        # Merge results: use most common values, aggregate style tags
        merged = {}
        all_tags = []
        for r in results:
            all_tags.extend(r.get('style_tags', []))
            for key in r:
                if key == 'style_tags':
                    continue
                merged[key] = r[key]  # last one wins — reasonable for consistent images

        # Deduplicate and order tags by frequency
        from collections import Counter
        tag_counts = Counter(all_tags)
        merged['style_tags'] = [tag for tag, _ in tag_counts.most_common(15)]
        merged['per_image_analysis'] = results

        return jsonify({'visual_profile': merged, 'success': True})
    except Exception as e:
        return jsonify({'error': f'Vision analysis failed: {str(e)}'}), 500


@app.route('/api/analyze-thumbnails', methods=['POST'])
@require_token
def analyze_thumbnails():
    """Analyze 2-3 thumbnail reference images via Groq Vision. Returns structured JSON."""
    if not groq_client:
        return jsonify({'error': 'Groq API key not configured'}), 500

    files = request.files.getlist('images')
    if not files or len(files) < 2:
        return jsonify({'error': 'Minimum 2 thumbnail images required'}), 400
    if len(files) > 3:
        return jsonify({'error': 'Maximum 3 thumbnail images allowed'}), 400

    try:
        image_b64_list = []
        for f in files:
            if f.content_type not in ('image/jpeg', 'image/png', 'image/webp'):
                return jsonify({'error': f'Unsupported format: {f.content_type}. Use JPEG, PNG, or WebP.'}), 400
            img_bytes = f.read()
            if len(img_bytes) > 4 * 1024 * 1024:
                return jsonify({'error': f'{f.filename} exceeds 4MB limit'}), 400
            image_b64_list.append(base64.b64encode(img_bytes).decode('utf-8'))

        results = []
        for b64 in image_b64_list:
            analysis = call_groq_vision(
                THUMBNAIL_ANALYSIS_SYSTEM_INSTRUCTION,
                "Analyze this YouTube thumbnail. Return structured JSON.",
                [b64]
            )
            results.append(analysis)

        # Merge thumbnail results
        merged = {}
        for r in results:
            for key in r:
                if key not in merged:
                    merged[key] = r[key]
        merged['per_thumbnail_analysis'] = results

        return jsonify({'thumbnail_profile': merged, 'success': True})
    except Exception as e:
        return jsonify({'error': f'Thumbnail analysis failed: {str(e)}'}), 500


@app.route('/api/analyze-thumbnails-auto', methods=['POST'])
@require_token
def analyze_thumbnails_auto():
    """Auto-fetch YouTube thumbnails from video IDs and analyze via Groq Vision."""
    if not groq_client:
        return jsonify({'error': 'Groq API key not configured'}), 500

    data = request.json or {}
    video_ids = data.get('video_ids', [])

    if not video_ids or len(video_ids) < 2:
        return jsonify({'error': 'Minimum 2 video IDs required for thumbnail analysis'}), 400

    try:
        image_b64_list = []
        for v_id in video_ids[:3]:
            # Try resolutions from highest to lowest
            img_bytes = None
            for res in ['maxresdefault', 'hqdefault', 'mqdefault', 'default']:
                url = f'https://img.youtube.com/vi/{v_id}/{res}.jpg'
                try:
                    req = urllib.request.Request(url, headers={'User-Agent': 'Morelike/1.0'})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        if resp.status == 200:
                            img_bytes = resp.read()
                            if len(img_bytes) > 2000:  # skip tiny placeholder images
                                break
                            img_bytes = None
                except Exception:
                    continue

            if img_bytes:
                image_b64_list.append(base64.b64encode(img_bytes).decode('utf-8'))

        if len(image_b64_list) < 2:
            return jsonify({'error': 'Could not fetch enough thumbnails from the provided video IDs'}), 400

        results = []
        for b64 in image_b64_list:
            analysis = call_groq_vision(
                THUMBNAIL_ANALYSIS_SYSTEM_INSTRUCTION,
                "Analyze this YouTube thumbnail. Return structured JSON.",
                [b64]
            )
            results.append(analysis)

        merged = {}
        for r in results:
            for key in r:
                if key not in merged:
                    merged[key] = r[key]
        merged['per_thumbnail_analysis'] = results

        return jsonify({'thumbnail_profile': merged, 'success': True})
    except Exception as e:
        return jsonify({'error': f'Auto-thumbnail analysis failed: {str(e)}'}), 500


# ── Socket.IO ─────────────────────────────────────────────────

@socketio.on('connect')
def handle_connect():
    print('Client connected')


@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')


# ── Entrypoint ────────────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
