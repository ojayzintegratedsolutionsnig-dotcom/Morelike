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
from functools import wraps
from extractor import extract_viral_content
from tokens import init_db, is_token_valid, get_credits, use_credit, create_token
from tokens import claim_token_by_email, log_action, save_feedback, get_all_feedback, save_reply
from emailer import send_token_email, send_reply_email

load_dotenv()

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

init_db()

GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

groq_client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1") if GROQ_API_KEY else None
deepseek_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com") if DEEPSEEK_API_KEY else None
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

admin_sessions = set()

extraction_status = {
    'running': False,
    'progress': 0,
    'message': '',
    'status': 'idle'
}

extracted_subtitles = {
    'content': '',
    'videos_processed': 0
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

## Target
Niche: {niche}
Duration: {target_length} minutes (~{target_length} × 150 words)

# OUTPUT FORMAT
Produce the following sections in order. Every section is mandatory.

═══════════════════════════════════
USER PLAN: $8 Creator Plan
SCRIPT DURATION: [X] min [Y] sec (Formula: [W] words ÷ 150 words/min)
═══════════════════════════════════

STYLE DNA CONFIRMATION
Niche: [one-line niche statement]
Target word count: [number] (±5%)
Pacing: [words/sec, sentence rhythm from DNA]
Hook style: [how the DNA hooks, applied to this script]
Emotional flow: [tension arc across the script]

───────────────────────────────────────
FINAL SEO TITLE
(after A/B analysis — winner with max 2 hyper-optimized SEO emojis)

DESCRIPTION
- Above-fold hook (first 2 lines): [hook using high-search-volume keywords]
- Body: [3-5 sentences describing the video, max 2 relevant emojis as visual anchors]
- Hashtags: #tag1 #tag2 #tag3

TAGS/KEYWORDS
tag1, tag2, tag3

═══════════════════════════════════
THUMBNAIL DESIGN
═══════════════════════════════════
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

═══════════════════════════════════
BEATS (Voice + Image + Video per Beat, max 8 seconds each)
═══════════════════════════════════
Generate the full script as numbered BEATS. Each beat = ~8 seconds (~20 spoken words). A {target_length}-minute video needs roughly {target_length} × 7.5 beats. Generate ALL beats in full — never truncate.

For EVERY beat, use the Visual Style Profile data above to maintain absolute consistency. The style tags, color palette, lighting, and composition from the analysis must be baked into every image and video prompt.

BEAT 1 — [Hook Moment]
VOICE OVER: [Pure dialogue. No stage directions. No brackets. Copy-paste ready for TTS.]

IMAGE PROMPT: [Standalone text-to-image prompt. Describe the full scene — subject, environment, composition, lighting, mood. End with: | Style: {style_tags}, 16:9]

VIDEO PROMPT: [Shot type + camera movement + subject action + environment dynamics + lighting animation + depth/parallax + transition out. End with: | Style: {style_tags}, 16:9]

BEAT 2 — [Beat Name]
VOICE OVER: [...]
IMAGE PROMPT: [...] | Style: {style_tags}, 16:9
VIDEO PROMPT: [...] | Style: {style_tags}, 16:9

(Continue ALL beats — BEAT 3, BEAT 4, BEAT 5, BEAT 6... all the way to the final beat. EVERY beat gets Voice Over + Image Prompt + Video Prompt. NO skipping. NO truncation. NO "(Continue...)". All style tags must be identical across every prompt.)

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
    import time

    # Ordered: Groq (fast/cheap) → DeepSeek (large context) → OpenAI (reliable fallback)
    clients = []
    if groq_client:
        clients.append(('groq', groq_client, 'llama-3.3-70b-versatile'))
    if deepseek_client:
        clients.append(('deepseek', deepseek_client, 'deepseek-chat'))
    if openai_client:
        clients.append(('openai', openai_client, 'gpt-4o-mini'))

    if not clients:
        raise Exception("No AI API key configured")

    for provider, client, model in clients:
        last_error = None
        for attempt in range(2):
            try:
                response = client.chat.completions.create(
                    model=model,
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
                last_error = e
                err_str = str(e).lower()
                # Don't retry on rate limits or size errors — go straight to fallback
                if '413' in err_str or 'rate_limit' in err_str or 'too large' in err_str:
                    break
                if attempt < 1:
                    time.sleep(3)

        # If we're on the last provider, raise. Otherwise try next.
        if provider == clients[-1][0]:
            hint = ''
            if len(clients) == 1:
                hint = ' (no fallback configured — add DEEPSEEK_API_KEY for automatic failover)'
            raise Exception(f"AI API error ({provider}){hint}: {str(last_error)}")

    raise Exception("AI API error: all providers exhausted")


def call_ai_deepseek(system_prompt, user_message, max_tokens=16384):
    """Call DeepSeek directly for large-context creative synthesis."""
    import time
    if not deepseek_client:
        raise Exception("DeepSeek API key not configured")
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
        return jsonify({'valid': True, 'credits': creds['credits'], 'email': creds.get('email')})
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
        return jsonify({'success': True, 'token': result['token'], 'credits': result['credits']})

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

    if not email:
        return jsonify({'error': 'No email in order'}), 400

    token = create_token(email=email, credits=3, lemon_order_id=order_id)
    try:
        send_token_email(email, token)
    except Exception as e:
        print(f"Failed to send email: {e}")

    return jsonify({'success': True, 'token': token})


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
    return jsonify(creds)


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


@app.route('/api/status', methods=['GET'])
def status():
    return jsonify(extraction_status)


@app.route('/api/subtitles', methods=['GET'])
def get_subtitles():
    if not extracted_subtitles['content']:
        return jsonify({'error': 'No subtitles available. Please extract videos first.'}), 404
    return jsonify({
        'content': extracted_subtitles['content'],
        'videos_processed': extracted_subtitles['videos_processed']
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

    if not viral_dna:
        return jsonify({'error': 'Viral DNA is required. Generate analysis first.'}), 400

    try:
        niche = extract_niche(viral_dna)
        system_prompt = TITLE_IDEAS_SYSTEM_INSTRUCTION.format(viral_dna=viral_dna, niche=niche)
        result = call_ai(system_prompt, f"Generate 3 title ideas about {niche} based on the Viral DNA.")
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

    if not viral_dna:
        return jsonify({'error': 'Viral DNA is required'}), 400
    if not chosen_title:
        return jsonify({'error': 'A chosen title is required'}), 400

    try:
        video_length = int(video_length)
        video_length = max(1, min(3, video_length))
    except (ValueError, TypeError):
        video_length = 3

    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    creds = get_credits(token)
    if not creds or creds['credits'] <= 0:
        return jsonify({'error': 'No credits remaining. Purchase more to continue.'}), 402

    log_action(token, 'generate_package')

    try:
        niche = extract_niche(viral_dna)

        # Build style context from vision analysis
        vis_str = json.dumps(visual_json, indent=2) if visual_json else 'No visual reference provided — use the Viral DNA to infer visual style.'
        thumb_str = json.dumps(thumbnail_json, indent=2) if thumbnail_json else 'No thumbnail reference provided — use the Viral DNA to infer thumbnail style.'
        style_tags = ', '.join(visual_json.get('style_tags', [])) if visual_json else 'match the Viral DNA aesthetic'

        # Use DeepSeek for quality synthesis (avoids Groq's 12K TPM bottleneck)
        system_prompt = MASTER_PACKAGE_SYSTEM_INSTRUCTION.format(
            viral_dna=viral_dna,
            niche=niche,
            target_length=video_length,
            visual_json=vis_str,
            thumbnail_json=thumb_str,
            style_tags=style_tags
        )
        user_message = f"TITLE: {chosen_title}\nTOPIC: {topic or chosen_title}\nNICHE: {niche}\nTARGET LENGTH: {video_length} minutes"

        # Send directly to DeepSeek for large-context creative synthesis
        if not deepseek_client:
            result = call_ai(system_prompt, user_message, max_tokens=16384)
        else:
            result = call_ai_deepseek(system_prompt, user_message, max_tokens=16384)

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

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    try:
        credits = max(1, min(100, int(credits)))
    except (ValueError, TypeError):
        credits = 3

    token = create_token(email=email, credits=credits)
    try:
        send_token_email(email, token)
    except Exception as e:
        print(f"Failed to send email: {e}")

    return jsonify({'success': True, 'token': token, 'email': email, 'credits': credits})


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
        ('groq', groq_client, 'llama-3.3-70b-versatile'),
        ('deepseek', deepseek_client, 'deepseek-chat'),
        ('openai', openai_client, 'gpt-4o-mini'),
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
