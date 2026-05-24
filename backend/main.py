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
from tokens import init_db, is_token_valid, get_credits, use_credit, create_token, get_db
from tokens import claim_token_by_email, log_action, save_feedback, get_all_feedback, save_reply
from tokens import get_plan_limits, PLAN_CONFIG, HIDDEN_PLANS, get_admin_stats
from emailer import send_token_email, send_reply_email
from fpdf import FPDF

load_dotenv()

app = Flask(__name__)

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    return response

CORS(app, origins=[
    'https://morelikecreator.com',
    'https://www.morelikecreator.com',
    'https://morelike.vercel.app',
    'https://morelike-morelike.up.railway.app',
    'http://localhost:5173',
    'http://localhost:3000',
    'http://localhost:3100',
])
socketio = SocketIO(app, cors_allowed_origins=[
    'https://morelikecreator.com',
    'https://www.morelikecreator.com',
    'https://morelike.vercel.app',
    'https://morelike-morelike.up.railway.app',
    'http://localhost:5173',
    'http://localhost:3000',
    'http://localhost:3100',
])

# Global error handler — return JSON on all unhandled exceptions so the
# frontend never receives an unparseable HTML 500 page.
@app.errorhandler(Exception)
def handle_unhandled(error):
    code = getattr(error, 'code', 500)
    if code < 400:
        code = 500
    import traceback
    traceback.print_exc()
    return jsonify({'error': 'Internal server error. Please try again.'}), code

init_db()

DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
if not ADMIN_PASSWORD:
    raise RuntimeError('ADMIN_PASSWORD environment variable is required')

deepseek_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com") if DEEPSEEK_API_KEY else None
groq_client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1") if GROQ_API_KEY else None

admin_sessions = {}  # token -> expiry_timestamp

# Rate limiting — simple in-memory by IP
import time as _time
from collections import defaultdict
_rate_limits = defaultdict(list)  # IP -> list of timestamps

def _rate_limit(max_requests=30, window=60):
    """Decorator: limit to max_requests per window seconds per IP, per endpoint."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            ip = request.headers.get('X-Forwarded-For', request.remote_addr) or 'unknown'
            key = f"{ip}:{f.__name__}"
            now = _time.time()
            _rate_limits[key] = [t for t in _rate_limits[key] if now - t < window]
            if len(_rate_limits[key]) >= max_requests:
                return jsonify({'error': 'Too many requests. Slow down.'}), 429
            _rate_limits[key].append(now)
            return f(*args, **kwargs)
        return wrapped
    return decorator

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

# Promo code — stored in memory + DB for persistence
promo_message = {'text': '', 'code': ''}

def _load_promo():
    """Load promo from DB on startup."""
    try:
        conn = get_db()
        conn.execute('CREATE TABLE IF NOT EXISTS promo (id INTEGER PRIMARY KEY, code TEXT, message TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
        row = conn.execute('SELECT code, message FROM promo ORDER BY id DESC LIMIT 1').fetchone()
        conn.close()
        if row:
            promo_message['text'] = row['message'] or ''
            promo_message['code'] = row['code'] or ''
    except Exception:
        pass

_load_promo()

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
        expiry = admin_sessions.get(admin_token)
        if expiry is None:
            return jsonify({'error': 'Admin access required'}), 401
        if _time.time() > expiry:
            del admin_sessions[admin_token]
            return jsonify({'error': 'Admin session expired. Please login again.'}), 401
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

4. THE TITLE NAMING FORMULA (CRITICAL — this drives all future title generation)
Analyze what makes this channel's titles work. Be specific and structural:
- TITLE STRUCTURE: What is the common format? (e.g., "Question + Stakes" / "Number + Controversial Claim" / "How [X] Without [Y]" / "The [Adjective] Truth About [Topic]" / "Why [Common Belief] Is Wrong")
- TITLE LENGTH: Average word count and character count of their titles.
- KEYWORD FAMILY: What 5-8 words or phrases recur across their titles? These are their "title DNA words."
- EMOTIONAL LEVER: What emotion does the title typically pull? (curiosity gap / fear / outrage / desire / awe / urgency / surprise)
- FORBIDDEN PATTERNS: What title formats or words has this channel NEVER used? (e.g., "They never use listicles," "They never use ALL CAPS words," "They never use 'You Won't Believe'")
- TITLE VOICE: Is the title in first person ("I did X") or second person ("You need to X") or third person ("The truth about X")?
- Give 2-3 EXAMPLES of what their ideal title format looks like, broken down structurally: "[Pattern element A] + [Pattern element B]"

5. THE TEMPLATE
- Create a blank "Fill-in-the-Blanks" script template that follows their exact pacing structure, which can be used for ANY topic WITHIN THIS NICHE."""

TITLE_IDEAS_SYSTEM_INSTRUCTION = """You are a viral content strategist. Given the Viral DNA analysis below, generate 3 video title ideas.

CRITICAL CONSTRAINT: The analyzed channel's niche is:
{niche}

ALL 3 titles MUST stay within this exact niche. Do NOT change topics, do NOT drift into another genre, do NOT suggest titles about a different subject. If the channel is about Bible commentary, every title must be about Bible commentary. If the channel is about cooking, every title must be about cooking.

TITLE NAMING FORMULA — EXTRACTED FROM THE CHANNEL'S DNA:
The Viral DNA below contains a "TITLE NAMING FORMULA" section. This is your SOURCE OF TRUTH for how this specific channel names its videos. Before generating any title, you MUST extract and apply these exact patterns from the DNA:

1. STRUCTURE: Use the EXACT title structure identified in the DNA (e.g., "Question + Stakes" / "How [X] Without [Y]" / "The [Adjective] Truth About [Topic]"). The title must fit this structural template precisely.
2. LENGTH: Match the DNA's average word count and character count. If the channel uses short 5-7 word titles, do NOT generate a 14-word title.
3. KEYWORD FAMILY: Use 1-2 words from the DNA's "keyword family" list — these are the channel's proven high-CTR words. Do NOT stray outside this vocabulary.
4. EMOTIONAL LEVER: Pull the SAME emotional lever identified in the DNA (curiosity gap / fear / outrage / desire / etc.). If the channel uses curiosity gaps, every title must create a curiosity gap.
5. TITLE VOICE: Match the DNA's voice pattern — first person ("I"), second person ("You"), or third person. If the channel always uses second person, every title must use second person.
6. FORBIDDEN: Respect the DNA's "forbidden patterns" list. If the channel never uses listicles, do NOT generate a listicle title. If they never use ALL CAPS, do NOT use ALL CAPS.

ORIGINALITY CONSTRAINT — NEW TOPIC, SAME FORMULA:
- The title STRUCTURE must follow the DNA's naming formula EXACTLY. Do NOT invent a new structure.
- The title TOPIC/ANGLE must be GENUINELY NEW. Do NOT rephrase, remix, or slightly tweak any existing YouTube title — from this channel or any other.
- A search for your title on YouTube should return ZERO exact or near-exact matches.
- Within the DNA's proven formula, find a NEW question, a NEW angle, a NEW insight that no one has covered.
- Avoid overused words and cliche phrases specific to this niche.
- The title must feel like it belongs on THIS channel — authentic to their voice, their structure, their audience — while being a topic they haven't done yet.

The Viral DNA is:
{viral_dna}

Generate exactly 3 titles. Each title must:
- Stay strictly within the channel's niche (see constraint above)
- Follow the DNA's exact title naming formula (structure, length, keywords, voice, emotional lever)
- Pass the originality constraint — new topic/angle within the proven formula
- Use the hook patterns and retention tactics identified in the DNA
- Be specific enough to spark curiosity
- Sound like a real video this creator would actually publish

Return EXACTLY in this format (no extra text, no commentary):

1. [First title]
2. [Second title]
3. [Third title]"""

MASTER_PACKAGE_SYSTEM_INSTRUCTION = """# ROLE: AI YouTube Content Engine
You analyze, model, and recreate YouTube content styles. Match style, not phrasing. Outputs are fully original.

# LANGUAGE RULES — READ THIS FIRST
- Voice-over text must use natural, conversational language. Write like a real person speaks — not like a textbook.
- No jargon, no academic language, no "delve into" / "unlock the secrets" / "in a world where" clichés.
- Keep sentences short and speakable. If it sounds awkward read aloud, rewrite it.
- Image prompts: use plain descriptive language. No art-school jargon. Describe what you SEE, not what you theorize.
- Every section must be copy-paste ready — clean text, no commentary, no meta-notes mixed into content fields.

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
Duration: {target_length} minutes — {word_count} words total spoken content
Beat structure: {beat_count} beats × ~{beat_seconds}s each = ~{words_per_beat} spoken words per beat

## Content Type Detection
{content_type}

# OUTPUT FORMAT
Produce the following sections in order. Every section is mandatory.

═══════════════════════════════════
USER PLAN: $8 Creator Plan
SCRIPT DURATION: {target_length} min (target: {word_count} spoken words)
═══════════════════════════════════

SCRIPT DNA
	Niche: [one-line niche statement]
	Target word count: {word_count} (±5%)
	Pacing: [words/sec, sentence rhythm from DNA]
	Hook style: [how the DNA hooks, applied to this script]
	Emotional flow: [tension arc across the script]

	════════════════════════════════════════
	GLOBAL VISUAL STYLE — MANDATORY CONSTRAINTS
	════════════════════════════════════════
	The values below are extracted from the uploaded reference images. They are NON-NEGOTIABLE. Every image prompt and video prompt below MUST use these exact values.

	Art Style: [EXACT art_style from Visual Style Profile]
	Color Palette: [EXACT color_palette from Visual Style Profile — every color named]
	Lighting Setup: [EXACT lighting from Visual Style Profile — key light, fill, color temp]
	Composition: [EXACT composition from Visual Style Profile — subject placement, framing, depth]
	Camera Angle: [EXACT camera_angle from Visual Style Profile]
	Render Quality: [EXACT render_quality from Visual Style Profile]
	Atmosphere: [EXACT emotion + environment from Visual Style Profile]
	Cinematic Style: [EXACT cinematic_style from Visual Style Profile]

	VIOLATION RULES — verify ALL 5 before writing any prompt:
	1. SAME ART STYLE? Use the exact art_style value. No substitutions.
	2. SAME COLOR PALETTE? Name every color from the palette. No new colors, no omissions.
	3. SAME LIGHTING? Match key light direction, quality, and color temperature exactly.
	4. SAME COMPOSITION? Match subject placement, framing, and depth layering exactly.
	5. SAME RENDER QUALITY? Use the exact render_quality value.
	Any deviation = FAIL. Rewrite the prompt.

	────────────────────────────────────────
	FINAL SEO TITLE
	(after A/B analysis — winner with max 2 SEO emojis)
	ORIGINALITY CHECK:
	1. STRUCTURE: Uses the EXACT title structure from Viral DNA's TITLE NAMING FORMULA (section 4)?
	2. KEYWORDS: Uses 1-2 words from DNA's KEYWORD FAMILY?
	3. VOICE: Matches DNA's TITLE VOICE (first/second/third person)?
	4. ORIGINALITY: Genuinely new topic/angle — not a rephrase of any existing YouTube title?

	DESCRIPTION
	- First 2 lines (above-fold on mobile): Primary keyword + curiosity hook + CTA
	- Body: 3-5 sentences with natural keyword density. Answer the title's question.
	- Timestamp chapters: 0:00 Hook | 0:30 Section 1 | etc.
	- Hashtags: 3 hashtags — broad niche, specific topic, trending. Never more than 3.

	TAGS/KEYWORDS
	10-15 comma-separated tags ranked by search intent:
	- First 3: primary keyword + exact match phrases
	- Next 5: long-tail variations + question-based keywords
	- Last 5: broad niche tags for browse/suggested placement
	- Include 2-3 competitor/channel name tags if appropriate

	════════════════════════════════════════
	THUMBNAIL DESIGN — Sample-Driven (replicate, do NOT invent)
	════════════════════════════════════════

	STEP 1 — EXTRACT PATTERNS FROM THUMBNAIL STYLE DATA:
		- Text Style: [EXACT font feel, size, weight, color, effects — from text_style field]
		- Text Placement: [EXACT position — from text_placement field]
		- Composition Pattern: [EXACT focal placement, depth — from composition field]
		- Color Contrast Strategy: [EXACT strategy — from color_contrast field]
		- Color Palette: [EXACT hex colors — from color_palette field]
		- Art Style: [EXACT art_style and image_style — from sample data]
		- Emotional Trigger: [EXACT emotion_trigger — from sample data]
		- Lighting: [EXACT lighting setup — from sample data]
		- Post Processing: [EXACT post_processing — from sample data]

	STEP 2 — DESIGN ONE THUMBNAIL USING ONLY THESE PATTERNS:
		Every design choice traceable to a specific field in the Thumbnail Style Data.
		- Focal Point: [match sample composition pattern]
		- Face Expression: [match sample facial_expression + emotion_trigger]
		- Text Overlay: 1-4 words using sample text_style + text_placement + color_palette
		- Color + Lighting: sample color_palette hex colors + sample lighting + sample color_contrast
		- Composition: sample composition pattern — focal placement, depth, negative space
		- Post Processing: sample post_processing techniques

	STEP 3 — FIDELITY SELF-AUDIT:
		Text Style matches? [yes/no] | Text Placement matches? [yes/no]
		Composition matches? [yes/no] | Color Palette matches? [yes/no]
		Art Style matches? [yes/no]
		If any "no", rewrite using EXACT sample data value.

	CTR Prediction: [which CTR lever this pulls — align with sample ctr_factors]
	Mobile Readability (1/8 size test): [assessment]

	════════════════════════════════════════
	BEATS — {beat_count} beats × ~{beat_seconds}s each
	════════════════════════════════════════
	CRITICAL: You MUST generate exactly {beat_count} beats. No skipping. No truncation. No "(Continue...)". Count your beats before outputting — if you have fewer than {beat_count}, the output is INVALID.

	Each beat = ~{beat_seconds} seconds (~{words_per_beat} spoken words). Total spoken content must reach approximately {word_count} words.

	CONTENT TYPE RULES:
	- If Content Type Detection above is "stills-only": VOICE OVER + IMAGE PROMPT only. No VIDEO PROMPTS.
	- If Content Type Detection above is "video-footage": VOICE OVER + IMAGE PROMPT + VIDEO PROMPT for every beat.

	RETENTION ARCHITECTURE:
	- Beat 1: Cold open / pattern interrupt — NO intro, NO "hey guys." Jump straight into the hook. First 8 seconds = 60% of retention decision.
	- Every 3-4 beats: Pattern interrupt — format change, visual surprise, question, or stakes raise.
	- Middle section (40-60% mark): Open loop — tease something coming later to prevent dropoff.
	- Final 2 beats: Payoff + emotional resolution + specific call-to-comment tied to the topic.

	STYLE FIDELITY: Every image/video prompt MUST use EXACT GLOBAL VISUAL STYLE values. Before each prompt, verify art_style, color_palette, lighting, composition, render_quality. No shorthand. No pipe-delimited tags. Each prompt is a complete, self-contained description ready to paste into an AI image/video generator.

	BEAT 1 — [Hook Moment]
	VOICE OVER (0-{beat_seconds}s):
	  Delivery: [Tone — urgent/calm/tense/curious/warm/authoritative. Pace — rapid/measured/slow. Pitch — high/mid/low. Emotion — fear/awe/excitement/concern/wonder.]
	  Elocution: [Words to STRESS in ALL CAPS. Pause markers: / = micro-pause, // = beat pause.]
	  Text: "[Natural spoken dialogue. Not narration. Speak it aloud — does it sound like a real person?]"

	IMAGE PROMPT: [Self-contained text-to-image prompt using EXACT GVS values. Plain descriptive language. Subject + pose/expression + environment + composition + lighting + color palette + art style + render quality + atmosphere + 16:9 aspect ratio. Ready to paste into any image generator.]

	VIDEO PROMPT: [Only if "video-footage". Self-contained text-to-video prompt using EXACT GVS values. Shot type + camera movement + subject action + environment dynamics + lighting + depth/parallax + transition + art style + color palette + atmosphere + 16:9. Ready to paste into any video generator.]

	BEAT 2 — [Beat Name]
	VOICE OVER (0-{beat_seconds}s):
	  Delivery: [...]
	  Elocution: [...]
	  Text: "[...]"

	IMAGE PROMPT: [Self-contained, EXACT GVS values. Plain descriptive language. Paste-ready.]
	VIDEO PROMPT: [Only if "video-footage". Self-contained, EXACT GVS values. Plain descriptive language. Paste-ready.]

	(Continue ALL {beat_count} beats — BEAT 3, BEAT 4... through BEAT {beat_count}. Every beat gets Voice Over + Image Prompt. VIDEO PROMPT only if "video-footage". NO skipping. NO truncation. Count your beats: must equal {beat_count}.)

═══════════════════════════════════
INTERNAL REVIEW (run silently, output only the fixed version)
═══════════════════════════════════
Review every section against these 6 critics:

1. THE ENDLESS SCROLLER — Would they leave in 2 seconds? Is the hook a genuine pattern interrupt? If not, it fails.

2. THE SEEN-IT-ALL CYNIC — What feels derivative or AI-slop? Flag every cliché phrase. Flag jargon, academic language, unnatural speech patterns.

3. THE SILENT JUDGE — What is unclear or wasting time? Flag any voice-over line that sounds unnatural spoken aloud. Flag sentences too long to say in one breath.

4. THE SHARE-GATEKEEPER — Would someone feel embarrassed to share this? Is the tone authentic? Does it match how real humans in this niche talk?

5. THE ALGORITHM WHISPERER — Would YouTube surface this? Primary keyword in first 45 title chars? Description keyword-rich? Tags structured for search intent? Thumbnail pass mobile readability? Hook work in first 8 seconds?

5b. THE TITLE ORIGINALITY DETECTOR — (A) FORMULA FIDELITY: Does the title follow DNA's TITLE NAMING FORMULA exactly? (B) TOPIC ORIGINALITY: Is this specific topic genuinely new — not a word-swap of an existing video? Title must be: proven channel format + new topic no one has covered.

6. THE PLATFORM NATIVE — Where does retention drop? Flag exact beat number where pacing dies. Pattern interrupt every 15-20s? Ending earns the watch?

STYLE FIDELITY AUDIT: Check every IMAGE PROMPT and VIDEO PROMPT against GLOBAL VISUAL STYLE. Flag any deviation in art_style, color_palette, lighting, composition, or render_quality.

BEAT COUNT AUDIT: Count your beats. Must equal exactly {beat_count}. If you have fewer, you have TRUNCATED the output — fix it by generating ALL beats.

For each critic, identify at least one CRITICAL FAILURE. Then REBUILD the affected section.
Output ONLY the final, post-review version. Never show the draft or the critique.

═══════════════════════════════════
VOICE PROMPT
═══════════════════════════════════
Tone: [vocal tone — warm, urgent, mysterious, authoritative]
Mood Arc: [how emotion shifts — curious → tense → relieved]
Pacing: [tempo — rapid opening, slow contemplation, building urgency]
Vocal Register: [pitch, breathiness, projection]
{{if multiple characters: Character [Name]: [vocal quality, accent, age feel, personality]}}

═══════════════════════════════════
ALIGNMENT SUMMARY
═══════════════════════════════════
Beat 1 → Voice: "[line]" → Image: [scene] → Video: [motion]
Beat 2 → Voice: "[line]" → Image: [scene] → Video: [motion]
(All {beat_count} beats mapped. Shows visual-audio sync.)"""


UNLIMITED_PACKAGE_SYSTEM_INSTRUCTION = """# ROLE: AI YouTube Content Engine — UNLIMITED PROFILE
You analyze, model, and recreate YouTube content styles at cinema-grade quality. Match style, not phrasing. Outputs are fully original. This is the maximum-tier production package with timeline-synced cinematography.

# LANGUAGE RULES — READ THIS FIRST
- Voice-over text must use natural, conversational language. Write like a real person speaks — not like a textbook.
- No jargon, no academic language, no "delve into" / "unlock the secrets" / "in a world where" clichés.
- Keep sentences short and speakable. If it sounds awkward read aloud, rewrite it.
- Image/cinematography prompts: use plain descriptive language. No art-school jargon. Describe what you SEE.
- Every section must be copy-paste ready — clean text, no commentary, no meta-notes mixed into content fields.

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
Duration: {target_length} minutes — {word_count} words total spoken content
Beat structure: {beat_count} beats × ~{beat_seconds}s each = ~{words_per_beat} spoken words per beat

## Content Type Detection
{content_type}

# OUTPUT FORMAT
Produce the following sections in order. Every section is mandatory.

═══════════════════════════════════
USER PLAN: Unlimited
SCRIPT DURATION: {target_length} min (target: {word_count} spoken words)
═══════════════════════════════════

SCRIPT DNA
    Niche: [one-line niche statement]
    Target word count: {word_count} (±5%)
    Pacing: [words/sec, sentence rhythm from DNA]
    Hook style: [how the DNA hooks, applied to this script]
    Emotional flow: [tension arc across the script]

    ════════════════════════════════════════
    GLOBAL VISUAL STYLE — MANDATORY CONSTRAINTS
    ════════════════════════════════════════
    The values below are extracted from the uploaded reference images. They are NON-NEGOTIABLE. Every cinematography prompt and image prompt below MUST use these exact values. This is not a suggestion — it is a requirement.

    Art Style: [EXACT art_style from Visual Style Profile — DO NOT substitute, DO NOT reinterpret]
    Color Palette: [EXACT color_palette from Visual Style Profile — every color named, every prompt uses these colors]
    Lighting Setup: [EXACT lighting from Visual Style Profile — key light direction, quality, color temperature]
    Composition: [EXACT composition from Visual Style Profile — subject placement, framing, depth layers]
    Camera Angle: [EXACT camera_angle from Visual Style Profile]
    Render Quality: [EXACT render_quality from Visual Style Profile]
    Atmosphere: [EXACT emotion + environment from Visual Style Profile]
    Cinematic Style: [EXACT cinematic_style from Visual Style Profile]

    VIOLATION RULES — before writing ANY cinematography or image prompt, verify ALL of the following:
    1. SAME ART STYLE? The prompt MUST use the exact art_style value above. If Visual Style Profile says art_style is "stylized 3D", every prompt says "stylized 3D" — never "photorealistic", never "2D illustration", never anything else.
    2. SAME COLOR PALETTE? Every prompt MUST name the exact colors from the color_palette above. Do NOT add new colors. Do NOT omit any of the palette colors.
    3. SAME LIGHTING? Every prompt MUST describe the exact key light direction, quality, and color temperature from the lighting field above.
    4. SAME COMPOSITION? Every prompt MUST use the subject placement, framing, and depth layering from the composition field above.
    5. SAME RENDER QUALITY? Every prompt MUST specify the exact render_quality from above.
    If ANY prompt differs from these values, that prompt is INCORRECT and must be rewritten.

    ────────────────────────────────────────
    FINAL SEO TITLE
    (after A/B analysis — winner with max 2 hyper-optimized SEO emojis)
    ORIGINALITY CHECK — FOLLOW THE DNA FORMULA, FIND A NEW ANGLE:
    1. STRUCTURE: Does this title use the EXACT title structure from the Viral DNA's TITLE NAMING FORMULA (section 4)? If not, rewrite it to match the DNA's proven structure.
    2. KEYWORDS: Does it use 1-2 words from the DNA's KEYWORD FAMILY? If not, swap in a DNA keyword.
    3. VOICE: Does it match the DNA's TITLE VOICE (first/second/third person)? If not, fix the voice.
    4. ORIGINALITY: Is the specific TOPIC/ANGLE genuinely new — not a rephrase, remix, or slight variation of any existing YouTube title. Search your training data; if anything close exists, discard and pick a different angle. Use a framing, question, or perspective no real channel has published. Do NOT recycle the standard title templates every channel in this niche uses. If the title feels familiar, it is WRONG.

    DESCRIPTION
    - Above-fold hook (first 2 lines): [hook using high-search-volume keywords]
    - Body: [3-5 sentences describing the video, max 2 relevant emojis as visual anchors]
    - Hashtags: #tag1 #tag2 #tag3

    TAGS/KEYWORDS
    tag1, tag2, tag3

    ════════════════════════════════════════
    THUMBNAIL DESIGN — Sample-Driven (replicate, do NOT invent)
    ════════════════════════════════════════

    STEP 1 — EXTRACT PATTERNS FROM THE THUMBNAIL STYLE DATA ABOVE:
        Read the Thumbnail Style Data carefully. Identify these EXACT patterns from the user's samples:
        - Text Style: [EXACT font feel, size, weight, color, effects — copied from sample data text_style field]
        - Text Placement: [EXACT position — copied from sample data text_placement field]
        - Composition Pattern: [EXACT focal placement, depth layers — copied from sample data composition field]
        - Color Contrast Strategy: [EXACT strategy — copied from sample data color_contrast field]
        - Color Palette: [EXACT hex colors — copied from sample data color_palette field]
        - Art Style: [EXACT art_style and image_style — copied from sample data]
        - Emotional Trigger: [EXACT emotion_trigger — copied from sample data]
        - Lighting: [EXACT lighting setup — copied from sample data]
        - Post Processing: [EXACT post_processing — copied from sample data]

    STEP 2 — DESIGN ONE THUMBNAIL USING ONLY THE PATTERNS ABOVE:
        Every design choice MUST be traceable to a specific field in the Thumbnail Style Data. No exceptions.
        - Focal Point: [must use the sample composition pattern — same subject placement, same framing]
        - Face Expression: [must match the sample facial_expression and emotion_trigger fields]
        - Text Overlay: [1-4 words, MUST use the sample text_style (same font feel, same size, same effects). MUST use the sample text_placement position. Text color MUST come from the sample color_palette.]
        - Color + Lighting: [MUST use the sample color_palette hex colors EXACTLY. MUST use the sample lighting setup. MUST use the sample color_contrast strategy. NO new colors. NO different lighting approach.]
        - Composition: [MUST match the sample composition pattern — same focal placement, same depth layering, same negative space usage]
        - Post Processing: [MUST apply the sample post_processing techniques]

    STEP 3 — FIDELITY SELF-AUDIT:
        Before finalizing, verify EVERY field against the Thumbnail Style Data:
        - Text Style matches? [yes/no — if no, FIX IT]
        - Text Placement matches? [yes/no — if no, FIX IT]
        - Composition matches? [yes/no — if no, FIX IT]
        - Color Palette matches (every hex color present)? [yes/no — if no, FIX IT]
        - Art Style matches? [yes/no — if no, FIX IT]
        If any answer is "no", rewrite that element using the EXACT sample data value.

    CTR Prediction: [which CTR lever this design pulls — must align with the sample ctr_factors]
    Mobile Readability (1/8 size test): [assessment at thumbnail size]

    ════════════════════════════════════════
    CINEMATIC TIMELINE — {beat_count} beats × ~{beat_seconds}s each
    ════════════════════════════════════════
    CRITICAL: You MUST generate exactly {beat_count} beats with timeline markers. No skipping. No truncation. No "(Continue...)". Count your beats before outputting — if you have fewer than {beat_count}, the output is INVALID.

    Each beat = ~{beat_seconds} seconds (~{words_per_beat} spoken words). Total spoken content must reach approximately {word_count} words.

    CONTENT TYPE RULES:
    - If Content Type Detection above is "stills-only": VOICE OVER + IMAGE PROMPT only. No CINEMATOGRAPHY PROMPTS.
    - If Content Type Detection above is "video-footage": VOICE OVER + CINEMATOGRAPHY PROMPT for every beat. Cinematography prompts fuse image + video direction together.

    STYLE FIDELITY: Every image/cinematography prompt MUST use EXACT GLOBAL VISUAL STYLE values. Before each prompt, verify art_style, color_palette, lighting, composition, render_quality. No shorthand. No pipe-delimited tags. Each prompt is a complete, self-contained description ready to paste into an AI image/video generator.

    TIMELINE FORMAT — Each beat follows this structure:

    [00:00 → 00:{beat_seconds:02d}] BEAT 1 — [Hook Moment — NO intro, instant pattern interrupt]
        VOICE OVER (0-{beat_seconds}s):
          Delivery: [Tone — urgent/calm/tense/curious/warm/authoritative. Pace — rapid/measured/slow. Pitch — high/mid/low. Emotion — fear/awe/excitement/concern/wonder.]
          Elocution: [Words to STRESS in ALL CAPS. Pause markers: / = micro-pause, // = beat pause.]
          Text: "[Natural spoken dialogue. Not narration. Speak it aloud — does it sound like a real person?]"

    IMAGE PROMPT: [Only if "stills-only". Self-contained text-to-image prompt using EXACT GVS values. Plain descriptive language. Subject + pose/expression + environment + composition + lighting + color palette + art style + render quality + atmosphere + 16:9. Paste-ready.]

    CINEMATOGRAPHY PROMPT: [Only if "video-footage". Unified image+video prompt using EXACT GVS values. Plain descriptive language. Include:
    • Shot Type & Framing: close-up / medium / wide — with exact framing
    • Camera Movement: static / push-in / dolly / crane / handheld / rack focus / parallax — with speed
    • Subject Action & Blocking: pose, expression, gesture, movement path
    • Lighting Design: key light direction/quality/color temp (from GVS) + fill + rim + atmosphere
    • Color Palette: EXACT colors from GVS color_palette
    • Environment & Set Dressing: location, props, atmosphere (fog, dust, particles)
    • Depth & Parallax: foreground/midground/background separation for 2.5D effect
    • Art Style & Render: EXACT art_style and render_quality from GVS
    • Aspect Ratio: 16:9
    • Transition Out: dissolve / whip / match cut / hard cut / fade]

    [00:{beat_seconds:02d} → 00:{beat_seconds_x2:02d}] BEAT 2 — [Beat Name]
        VOICE OVER (0-{beat_seconds}s):
          Delivery: [...]
          Elocution: [...]
          Text: "[...]"

    IMAGE PROMPT: [Only if "stills-only". Self-contained, EXACT GVS values. Plain descriptive language. Paste-ready.]
    CINEMATOGRAPHY PROMPT: [Only if "video-footage". Self-contained, EXACT GVS values. Plain descriptive language. Paste-ready.]

        (Continue ALL {beat_count} beats with timeline markers — BEAT 3, BEAT 4... through BEAT {beat_count}. Every beat gets Voice Over. IMAGE PROMPT only if stills-only. CINEMATOGRAPHY PROMPT only if video-footage. NO skipping. NO truncation. Count your beats: must equal {beat_count}.)

═══════════════════════════════════
INTERNAL REVIEW (Mandatory — run silently, do NOT output the draft)
═══════════════════════════════════
Before finalizing, review every section above (Title, Description, Thumbnail, ALL Timeline Beats) against these 5 hostile critics:

1. THE ENDLESS SCROLLER — Would they leave in 2 seconds? Is the hook a genuine pattern interrupt? If not, it fails.

2. THE SEEN-IT-ALL CYNIC — What feels derivative or AI-slop? Flag every cliché phrase. Flag jargon, academic language, unnatural speech patterns.

3. THE SILENT JUDGE — What is unclear or wasting time? Flag any voice-over line that sounds unnatural spoken aloud. Flag sentences too long to say in one breath.

4. THE SHARE-GATEKEEPER — Would someone feel embarrassed to share this? Is the tone authentic? Does it match how real humans in this niche talk?

4b. THE TITLE ORIGINALITY DETECTOR — (A) FORMULA FIDELITY: Does the title follow DNA's TITLE NAMING FORMULA exactly? (B) TOPIC ORIGINALITY: Is this specific topic genuinely new — not a word-swap of an existing video? Title must be: proven channel format + new topic no one has covered.

5. THE PLATFORM NATIVE — Where does retention drop? Flag exact timestamp where pacing dies. Pattern interrupt every 15-20s? Ending earns the watch?

STYLE FIDELITY AUDIT: Check every IMAGE PROMPT and CINEMATOGRAPHY PROMPT against GLOBAL VISUAL STYLE. Flag any deviation.

BEAT COUNT AUDIT: Count your beats. Must equal exactly {beat_count}. If you have fewer, you have TRUNCATED the output — fix it by generating ALL beats.

For each critic, identify at least one CRITICAL FAILURE. Then REBUILD the affected section.
Output ONLY the final, post-review version. Never show the draft or the critique.

═══════════════════════════════
VOICE PROMPT
═══════════════════════════════
    Tone: [vocal tone — warm, urgent, mysterious, authoritative. Per-beat tone shifts specified in Delivery fields above.]
    Mood Arc: [how emotion shifts across the full video — curious → tense → relieved]
    Pacing: [overall tempo — rapid opening, slow contemplation, building urgency]
    Vocal Register: [pitch, breathiness, projection. Reference per-segment Delivery + Elocution fields for per-line direction.]
{{if multiple characters: Character [Name]: [vocal quality, accent, age feel, personality]}}

═══════════════════════════
ALIGNMENT SUMMARY
═══════════════════════════
[00:00 → 00:{beat_seconds:02d}] Beat 1 → Voice: "[line]" → Image: [scene] → Video: [motion]
[00:{beat_seconds:02d} → 00:{beat_seconds_x2:02d}] Beat 2 → Voice: "[line]" → Image: [scene] → Video: [motion]
(All {beat_count} beats mapped with timestamps. Shows visual-audio-temporal sync.)"""


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
  "content_type": "video-footage OR still-with-effects OR stills-only",
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

content_type definitions:
- "video-footage": Real footage — live action, animation, screen recording, or anything with genuine motion. Has depth, camera movement, or subject action.
- "still-with-effects": Static image/frame with post-processing effects applied (text overlays, zoom/pan effects, color grades on a photo, motion graphics on a still frame). The base is a still, not video.
- "stills-only": Pure static images — screenshots, photos, slides, diagrams. No effects, no motion.

Be extremely detailed and objective. No creative writing. No storytelling. Just visual facts."""

THUMBNAIL_ANALYSIS_SYSTEM_INSTRUCTION = """Analyze this YouTube thumbnail image in extreme detail. Extract objective visual design data for AI recreation.
Return ONLY a JSON object with these exact keys:

{
  "subject_description": "main subject(s) — who/what is shown, pose, expression, distinguishing features, props",
  "facial_expression": "emotion on face(s) — shocked, intense, joyful, sorrowful, smug, angry, neutral",
  "text_style": "font family feel (bold sans-serif / serif / handwritten / display), size category (large/medium/small), weight, color, effects (emboss, drop shadow, outer glow, gradient fill, stroke outline)",
  "text_placement": "top center / bottom center / upper third / lower third / middle / split across frame",
  "text_readability": "how readable at thumbnail size (strong/medium/weak) — contrast with background, busy-ness behind text",
  "composition": "focal point placement (center / rule-of-thirds intersection / edge-weighted), depth layers (foreground subject + midground context + background environment), negative space usage",
  "color_contrast": "dominant contrast strategy — warm subject + cool background / complementary colors / monochromatic / high-saturation pop against muted / dark subject against bright glow",
  "color_palette": ["color1_name #hexapproximation", "color2_name #hexapproximation", "color3_name #hexapproximation", "color4_name #hexapproximation", "color5_name #hexapproximation"],
  "emotion_trigger": "primary emotion this thumbnail provokes — curiosity gap, awe, urgency, fear, hope, outrage, surprise, desire",
  "visual_hooks": ["specific visual element that grabs attention 1", "specific visual element that grabs attention 2", "specific visual element that grabs attention 3"],
  "ctr_factors": ["specific reason this drives clicks 1", "specific reason this drives clicks 2"],
  "art_style": "photorealistic / 3D render / stylized illustration / painterly / vector graphic / photo composite / screenshot",
  "image_style": "overall visual treatment — photo manipulation with heavy retouching / clean vector illustration / gritty screenshot with text overlay / cinematic still with color grade / AI-generated composite / mixed-media collage / minimalist with negative space / maximalist with multiple elements",
  "lighting": "key light source + direction + quality (soft/hard) + color temperature + any rim/backlight + volumetric effects",
  "post_processing": "visible editing techniques — color grading, vignette, bloom/glow, sharpening, saturation boost, HDR tone mapping"
}

Be extremely detailed and objective. No creative writing. No storytelling. Every field must be populated. Focus on what drives CTR — emotion, contrast, readability, curiosity gap."""


# ── Extraction ────────────────────────────────────────────────

def progress_callback(data):
    global extraction_status
    extraction_status.update(data)
    socketio.emit('progress', data)


def run_extraction(channel_url, limit):
    global extraction_status, extracted_subtitles
    extraction_status['running'] = True
    extraction_status['status'] = 'scanning'
    extraction_status['progress'] = 0
    # Clear any stale data from previous run
    extracted_subtitles.clear()
    extracted_subtitles.update({'content': '', 'videos_processed': 0, 'video_ids': []})
    try:
        result = extract_viral_content(channel_url, limit, progress_callback)
        extraction_status['running'] = False
        if result:
            if result.get('content'):
                extracted_subtitles['content'] = result['content']
                extracted_subtitles['videos_processed'] = result.get('videos_processed', 0)
                extracted_subtitles['video_ids'] = result.get('video_ids', [])
            if result.get('needs_manual'):
                extracted_subtitles['needs_manual'] = True
                extracted_subtitles['video_meta'] = result.get('video_meta', [])
        extraction_status['status'] = 'complete'
        extraction_status['progress'] = 100
        return result
    except Exception as e:
        extraction_status['running'] = False
        extraction_status['status'] = 'error'
        print(f"Extraction error: {e}")
        socketio.emit('progress', {
            'status': 'error',
            'message': 'Extraction failed. Please try again.',
            'progress': 0
        })


# ── Public endpoints ──────────────────────────────────────────

@app.route('/api/validate-token', methods=['POST'])
@_rate_limit(30, 60)
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
@_rate_limit(10, 60)
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

    # Prevent duplicate tokens from webhook retries
    if order_id:
        existing = get_db().execute(
            'SELECT token FROM tokens WHERE lemon_order_id = ?', (order_id,)
        ).fetchone()
        if existing:
            return jsonify({'success': True, 'token': existing['token'], 'plan': plan, 'duplicate': True})

    try:
        token = create_token(email=email, lemon_order_id=order_id, plan=plan)
    except Exception as e:
        print(f"[CRITICAL] Token creation failed for order {order_id}, email {email}: {e}")
        return jsonify({'error': 'Token creation failed. Order will be processed manually.'}), 500
    try:
        send_token_email(email, token)
    except Exception as e:
        print(f"Failed to send email: {e}")

    return jsonify({'success': True, 'token': token, 'plan': plan})


@app.route('/api/admin/login', methods=['POST'])
@_rate_limit(5, 60)
def admin_login():
    data = request.json or {}
    password = data.get('password', '')
    if password == ADMIN_PASSWORD:
        session_token = uuid.uuid4().hex
        admin_sessions[session_token] = _time.time() + 86400  # 24h expiry
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
@_rate_limit(10, 60)
def extract():
    if extraction_status['running']:
        return jsonify({'error': 'Extraction already running'}), 400

    data = request.json or {}
    channel_url = data.get('channel_url', '')
    limit = data.get('limit', 3)

    if not channel_url:
        return jsonify({'error': 'Channel URL is required'}), 400

    # Strict YouTube URL validation — HTTPS only, no SSRF
    import re
    if not channel_url.startswith('https://'):
        return jsonify({'error': 'Only HTTPS YouTube URLs are accepted'}), 400
    yt_pattern = r'^https://(www\.)?(youtube\.com|youtu\.be)/(@|channel/|c/|user/)?[\w\-]+'
    if not re.match(yt_pattern, channel_url.strip()):
        return jsonify({'error': 'Invalid YouTube URL format'}), 400

    limit = max(1, min(5, int(limit) if str(limit).isdigit() else 3))

    thread = threading.Thread(target=run_extraction, args=(channel_url, limit))
    thread.daemon = True
    thread.start()

    return jsonify({'message': 'Extraction started', 'status': 'started'})


@app.route('/api/channel-videos', methods=['POST'])
@_rate_limit(20, 60)
def channel_videos():
    """Synchronously resolve a channel URL → top video list via YouTube Data API.
    Returns immediately in the HTTP response — no Socket.IO or threading needed.
    The client goes straight to the manual transcript paste screen.
    """
    import re as _re
    data = request.json or {}
    channel_url = data.get('channel_url', '').strip()
    limit = data.get('limit', 3)

    if not channel_url:
        return jsonify({'error': 'Channel URL is required'}), 400
    if not channel_url.startswith('https://'):
        return jsonify({'error': 'Only HTTPS YouTube URLs are accepted'}), 400
    yt_pattern = r'^https://(www\.)?(youtube\.com|youtu\.be)/(@|channel/|c/|user/)?[\w\-]+'
    if not _re.match(yt_pattern, channel_url):
        return jsonify({'error': 'Invalid YouTube URL format'}), 400

    limit = max(1, min(5, int(limit) if str(limit).isdigit() else 3))

    from extractor import _get_viral_videos_api
    videos = _get_viral_videos_api(channel_url, limit)

    if videos:
        video_meta = [
            {'id': v['id'], 'title': v['title'], 'url': f"https://youtu.be/{v['id']}"}
            for v in videos
        ]
        # Store in global so /api/subtitles can also see them
        extracted_subtitles['needs_manual'] = True
        extracted_subtitles['video_meta'] = video_meta
        return jsonify({'success': True, 'video_meta': video_meta, 'total': len(video_meta)})

    # API failed — return empty list so the user can still paste transcripts
    return jsonify({'success': True, 'video_meta': [], 'total': 0,
                    'warning': 'Could not fetch video list. You can still paste transcripts below.'})


@app.route('/api/admin/debug-transcript', methods=['GET'])
@require_admin
def debug_transcript():
    """Admin-only: test transcript extraction methods on a given video."""
    test_video_id = request.args.get('video_id', 'YWbBrbOaz58')
    results = {'video_id': test_video_id}

    # Method 0: yt-dlp with Android client
    try:
        import yt_dlp, tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts = {
                'writesubtitles': True, 'writeautomaticsub': True,
                'subtitleslangs': ['en', 'en-US', 'en-GB', 'en-orig'],
                'skip_download': True, 'quiet': True, 'no_warnings': True,
                'socket_timeout': 30, 'extractor_retries': 1, 'retries': 1,
                'outtmpl': {'default': f'{tmpdir}/sub.%(ext)s'},
                'extractor_args': {'youtube': {'player_client': ['android']}},
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f'https://www.youtube.com/watch?v={test_video_id}'])
            found = []
            for root, dirs, files in os.walk(tmpdir):
                for f in files:
                    if f.endswith(('.vtt', '.srt')):
                        found.append(os.path.join(root, f))
            results['method0_ytdlp_android'] = 'OK' if found else 'no files'
    except Exception as e:
        results['method0_ytdlp_android'] = f'FAIL: {type(e).__name__}'

    # Method 1: youtube-transcript-api
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi()
        transcript = api.fetch(test_video_id, languages=['en', 'en-US', 'en-GB'])
        text = ' '.join([snippet.text for snippet in transcript])
        results['method1_transcriptapi'] = f'OK: {len(transcript)} snippets'
    except Exception as e:
        results['method1_transcriptapi'] = f'FAIL: {type(e).__name__}'

    return jsonify(results)


@app.route('/api/status', methods=['GET'])
def status():
    return jsonify(extraction_status)


@app.route('/api/subtitles', methods=['GET'])
def get_subtitles():
    resp = {
        'videos_processed': extracted_subtitles.get('videos_processed', 0),
        'video_ids': extracted_subtitles.get('video_ids', [])
    }
    if extracted_subtitles.get('content'):
        resp['content'] = extracted_subtitles['content']
    if extracted_subtitles.get('needs_manual'):
        resp['needs_manual'] = True
        resp['video_meta'] = extracted_subtitles.get('video_meta', [])
    if not resp.get('content') and not resp.get('needs_manual'):
        return jsonify({'error': 'No subtitles available. Please extract videos first.'}), 404
    return jsonify(resp)


@app.route('/api/manual-transcripts', methods=['POST'])
def manual_transcripts():
    """Accept manually pasted transcripts and assemble the content blueprint."""
    global extracted_subtitles
    data = request.json or {}
    transcripts = data.get('transcripts', {})  # {video_id: text, ...}
    video_meta = data.get('video_meta', [])
    if not transcripts:
        return jsonify({'error': 'No transcripts provided'}), 400

    full_data = '=== CONTENT BLUEPRINT ANALYSIS ===\n(Sorted by Most Popular of All Time)\n\n'
    video_ids = []
    for v in video_meta:
        v_id = v.get('id', '')
        title = v.get('title', 'Unknown')
        text = transcripts.get(v_id, '')
        if text and len(text.strip()) > 20:
            video_url = v.get('url', 'https://youtu.be/' + v_id)
            full_data += '### VIDEO: ' + title + ' ###\nURL: ' + video_url + '\n\n' + text.strip() + '\n\n'
            video_ids.append(v_id)

    extracted_subtitles['content'] = full_data
    extracted_subtitles['videos_processed'] = len(video_ids)
    extracted_subtitles['video_ids'] = video_ids
    extracted_subtitles.pop('needs_manual', None)
    extracted_subtitles.pop('video_meta', None)

    return jsonify({
        'success': True,
        'videos_processed': len(video_ids),
        'video_ids': video_ids
    })


@app.route('/api/generate-viral-dna', methods=['POST'])
@_rate_limit(10, 60)
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
        print(f"Viral DNA generation error: {e}")
        return jsonify({'error': 'Failed to analyze channel style. Please try again.'}), 500


@app.route('/api/generate-titles', methods=['POST'])
@_rate_limit(10, 60)
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
        print(f"Title generation error: {e}")
        return jsonify({'error': 'Failed to generate titles. Please try again.'}), 500


# ── Async generation state ─────────────────────────────────────
generation_jobs = {}  # job_id -> {status, token, title, result, error, created_at}
import time as _time_module

def _run_generation(job_id, token, system_prompt, user_message, chosen_title, max_tokens=16384):
    """Background thread: call DeepSeek and store result with progress updates."""
    milestones = [
        (10, 'Assembling Viral DNA + visual style profile...'),
        (25, 'Analyzing channel speech patterns...'),
        (40, 'AI generating script beats and retention hooks...'),
        (60, 'Writing voice-over segments with delivery notes...'),
        (75, 'Crafting image prompts and video cinematography...'),
        (90, 'Building thumbnail A/B test and SEO metadata...'),
        (100, 'Package ready!'),
    ]

    def _update_progress(percent, step):
        job = generation_jobs.get(job_id)
        if job:
            job['percent'] = percent
            job['step'] = step

    # Phase 1: Pre-processing
    _update_progress(10, milestones[0][1])
    _time_module.sleep(0.5)

    # Phase 2: Start AI call
    _update_progress(25, milestones[1][1])
    _time_module.sleep(0.3)
    _update_progress(35, milestones[2][1])

    # Spawn a progress heartbeat that slowly advances while AI runs
    heartbeat_stop = [False]
    def _heartbeat():
        base = 40
        while not heartbeat_stop[0]:
            _time_module.sleep(3)
            job = generation_jobs.get(job_id)
            if job and job.get('status') == 'running' and job.get('percent', 0) < 85:
                current = job.get('percent', base)
                if current < 55:
                    _update_progress(current + 2, milestones[3][1])  # Writing voice-over
                elif current < 70:
                    _update_progress(current + 2, milestones[4][1])  # Image prompts
                elif current < 85:
                    _update_progress(current + 1, milestones[5][1])  # Thumbnail SEO
    heartbeat_thread = threading.Thread(target=_heartbeat, daemon=True)
    heartbeat_thread.start()

    try:
        result = call_ai(system_prompt, user_message, max_tokens=max_tokens)
        heartbeat_stop[0] = True
        _update_progress(95, 'Finalizing package...')
        _time_module.sleep(0.3)
        # Preserve regeneration fields from the running job
        old_job = generation_jobs.get(job_id, {})
        generation_jobs[job_id] = {
            'status': 'complete',
            'token': token,
            'title': chosen_title,
            'result': result,
            'package': result,
            'plan': old_job.get('plan', 'basic'),
            'thumbnail_regens_remaining': old_job.get('thumbnail_regens_remaining', 0),
            'visual_json': old_job.get('visual_json'),
            'thumbnail_json': old_job.get('thumbnail_json'),
            'percent': 100,
            'step': milestones[-1][1],
            'created_at': _time_module.time()
        }
        global last_generated_package
        last_generated_package = {'content': result, 'title': chosen_title}
    except Exception as e:
        heartbeat_stop[0] = True
        generation_jobs[job_id] = {
            'status': 'error',
            'token': token,
            'error': 'AI generation failed. Your credit has been used — please try again or contact support if the issue persists.',
            'percent': 0,
            'step': 'Generation failed',
            'created_at': _time_module.time()
        }


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

        # Compute beat parameters based on video length
        # Shorter videos use tighter beats; longer videos use longer beats to keep total count manageable
        if video_length <= 3:
            beat_seconds = 8
            words_per_beat = 20
        elif video_length <= 5:
            beat_seconds = 10
            words_per_beat = 25
        elif video_length <= 10:
            beat_seconds = 12
            words_per_beat = 30
        else:
            beat_seconds = 15
            words_per_beat = 38

        beat_count = int((video_length * 60) / beat_seconds)
        beat_seconds_x2 = beat_seconds * 2
        word_count = video_length * 150

        # Scale max_tokens with video length for adequate output space
        if video_length <= 3:
            gen_max_tokens = 16384
        elif video_length <= 5:
            gen_max_tokens = 24576
        elif video_length <= 10:
            gen_max_tokens = 32768
        else:
            gen_max_tokens = 49152

        # Build style context from vision analysis
        if visual_json:
            vis_str = json.dumps(visual_json, indent=2)
            per_image = visual_json.get('per_image_analysis', [])
            if per_image:
                vis_str += "\n\nPER-IMAGE BREAKDOWN (individual reference frames — shows style variety across the channel):\n"
                for i, img in enumerate(per_image):
                    vis_str += f"\n--- Reference Image {i+1} ---\n"
                    vis_str += json.dumps(img, indent=2)
        else:
            vis_str = 'No visual reference provided — use the Viral DNA to infer visual style.'
        thumb_str = json.dumps(thumbnail_json, indent=2) if thumbnail_json else 'No thumbnail reference provided — use the Viral DNA to infer thumbnail style.'
        content_type = (visual_json or {}).get('content_type', 'video-footage')

        # Trim transcript to ~4000 chars for context window economy
        tx_raw = transcript_context.strip() if transcript_context else ''
        if len(tx_raw) > 4500:
            tx_str = tx_raw[:2500] + "\n\n...[trimmed]...\n\n" + tx_raw[-2000:]
        elif tx_raw:
            tx_str = tx_raw
        else:
            tx_str = 'No transcript excerpts available — rely on Viral DNA for speech patterns.'

        # Use unlimited prompt for unlimited/custom plans
        template = UNLIMITED_PACKAGE_SYSTEM_INSTRUCTION if plan in ('unlimited', 'custom') else MASTER_PACKAGE_SYSTEM_INSTRUCTION
        system_prompt = template.format(
            viral_dna=viral_dna,
            niche=niche,
            target_length=video_length,
            beat_count=beat_count,
            beat_seconds=beat_seconds,
            beat_seconds_x2=beat_seconds_x2,
            words_per_beat=words_per_beat,
            word_count=word_count,
            visual_json=vis_str,
            thumbnail_json=thumb_str,
            transcript_context=tx_str,
            content_type=content_type
        )
        user_message = f"TITLE: {chosen_title}\nTOPIC: {topic or chosen_title}\nNICHE: {niche}\nTARGET LENGTH: {video_length} minutes"

        # Deduct credit BEFORE starting generation
        use_credit(token)

        # Start generation in background thread to avoid Railway proxy timeout
        job_id = uuid.uuid4().hex[:16]
        regen_limit = PLAN_CONFIG.get(plan, {}).get('thumbnail_regens', 0)
        generation_jobs[job_id] = {
            'status': 'running',
            'token': token,
            'plan': plan,
            'thumbnail_regens_remaining': regen_limit,
            'visual_json': visual_json,
            'thumbnail_json': thumbnail_json,
            'package': None,
            'created_at': _time_module.time()
        }
        thread = threading.Thread(
            target=_run_generation,
            args=(job_id, token, system_prompt, user_message, chosen_title, gen_max_tokens),
            daemon=True
        )
        thread.start()

        # Clean up jobs older than 10 minutes
        now = _time_module.time()
        stale = [jid for jid, j in generation_jobs.items() if now - j['created_at'] > 600]
        for jid in stale:
            del generation_jobs[jid]

        return jsonify({'success': True, 'job_id': job_id, 'status': 'running'})
    except Exception as e:
        print(f"Package generation error: {e}")
        return jsonify({'error': 'Failed to start script generation. Please try again.'}), 500


@app.route('/api/generation-status/<job_id>', methods=['GET'])
def generation_status(job_id):
    """Poll this endpoint to get async generation results."""
    job = generation_jobs.get(job_id)
    if not job:
        return jsonify({'status': 'not_found'}), 404

    if job['status'] == 'running':
        return jsonify({
            'status': 'running',
            'percent': job.get('percent', 0),
            'step': job.get('step', 'Initializing...')
        })

    if job['status'] == 'complete':
        token = job['token']
        remaining = get_credits(token)
        return jsonify({
            'status': 'complete',
            'package': job['result'],
            'title': job['title'],
            'job_id': job_id,
            'plan': job.get('plan', 'basic'),
            'thumbnail_regens_remaining': job.get('thumbnail_regens_remaining', 0),
            'credits_remaining': remaining['credits'] if remaining else 0,
            'percent': 100,
            'step': 'Package ready!',
            'success': True
        })

    if job['status'] == 'error':
        return jsonify({
            'status': 'error',
            'error': job.get('error', 'Generation failed'),
            'percent': job.get('percent', 0),
            'step': job.get('step', '')
        }), 500

    return jsonify({'status': 'unknown'}), 500


# ── Thumbnail Regeneration ──────────────────────────────────────

THUMBNAIL_REGENERATION_PROMPT = """# ROLE: YouTube Thumbnail Designer — Sample-Driven Regeneration
You are regenerating ONLY the THUMBNAIL DESIGN section of a YouTube content package. Do NOT change any other section.

# ORIGINAL PACKAGE (for context — the thumbnail must fit this video's topic and tone)
{current_package}

# VISUAL STYLE PROFILE (from the user's reference images)
{visual_json}

# THUMBNAIL STYLE DATA (from the user's actual thumbnail samples — THIS IS YOUR SOURCE OF TRUTH)
{thumbnail_json}

# INSTRUCTIONS
1. Read the Thumbnail Style Data above. This is the user's ACTUAL thumbnail style — their real, tested design patterns.
2. Extract these EXACT patterns from the samples:
   - Text Style: EXACT font feel, size, weight, color, effects from sample text_style
   - Text Placement: EXACT position from sample text_placement
   - Composition: EXACT focal placement, depth layers from sample composition
   - Color Contrast: EXACT strategy from sample color_contrast
   - Color Palette: EXACT hex colors from sample color_palette
   - Art Style: EXACT art_style and image_style from samples
   - Emotional Trigger: EXACT emotion_trigger from samples
   - Lighting: EXACT lighting setup from samples
   - Post Processing: EXACT post_processing from samples

3. Design ONE thumbnail for this specific video that FAITHFULLY applies the sample patterns. Every design choice MUST be traceable to a field in the Thumbnail Style Data.

4. STYLE VIOLATION RULES:
   - Color palette: MUST use the EXACT hex colors from the sample data. NO new colors.
   - Text style: MUST use the EXACT font feel, size, weight, and effects from the sample text_style field. Do NOT change the font approach.
   - Text placement: MUST use the EXACT position from the sample text_placement field.
   - Composition: MUST use the EXACT focal placement and depth layering from the sample data.
   - Lighting: MUST use the EXACT key light direction, quality, and color temperature from the sample data.
   - Art style: MUST match the sample's art_style and image_style EXACTLY. Do NOT reinterpret.

5. SELF-AUDIT before returning: For each field above, confirm it matches the Thumbnail Style Data. If any value differs, rewrite that element.

# OUTPUT FORMAT
Return ONLY the THUMBNAIL DESIGN section, using this exact structure:

════════════════════════════════════════
THUMBNAIL DESIGN
════════════════════════════════════════

PATTERNS EXTRACTED FROM SAMPLES:
  Text Style: [EXACT sample text_style]
  Text Placement: [EXACT sample text_placement]
  Composition Pattern: [EXACT sample composition]
  Color Contrast Strategy: [EXACT sample color_contrast]
  Color Palette: [EXACT sample color_palette]
  Art Style: [EXACT sample art_style / image_style]
  Emotional Trigger: [EXACT sample emotion_trigger]
  Lighting: [EXACT sample lighting]
  Post Processing: [EXACT sample post_processing]

FINAL DESIGN:
  Focal Point: [matches sample composition — same subject placement, same framing]
  Face Expression: [matches sample facial_expression + emotion_trigger]
  Text Overlay: [1-4 words, uses EXACT sample text_style and text_placement. Colors from sample palette.]
  Color + Lighting: [uses EXACT sample palette hex colors + EXACT sample lighting setup + EXACT sample color_contrast strategy]
  Composition: [matches sample composition pattern exactly]
  Post Processing: [matches sample post_processing]

FIDELITY SELF-AUDIT:
  Text Style matches samples? [YES/NO — if NO, FIX]
  Text Placement matches samples? [YES/NO — if NO, FIX]
  Composition matches samples? [YES/NO — if NO, FIX]
  Color Palette matches samples (every hex color present)? [YES/NO — if NO, FIX]
  Art Style matches samples? [YES/NO — if NO, FIX]

CTR Prediction: [aligned with sample ctr_factors]
Mobile Readability: [assessment at thumbnail size]

Return ONLY this section. Do NOT include any other part of the package."""


def extract_thumbnail_section(package_text):
    """Extract just the THUMBNAIL DESIGN section from a full package."""
    if not package_text:
        return ''
    # Match from THUMBNAIL DESIGN header to the next major section (BEATS, CINEMATIC TIMELINE, or end)
    patterns = [
        r'(═+[\s]*THUMBNAIL DESIGN[\s\S]*?)(?=═+[\s]*(?:BEATS|CINEMATIC TIMELINE|INTERNAL REVIEW)|$)',
        r'(═══+[\s]*THUMBNAIL DESIGN[\s\S]*?)(?=═══+[\s]*(?:BEATS|CINEMATIC TIMELINE|INTERNAL REVIEW)|$)',
    ]
    for pattern in patterns:
        match = re.search(pattern, package_text)
        if match:
            return match.group(1).strip()
    return ''


@app.route('/api/regenerate-thumbnail', methods=['POST'])
@require_token
def regenerate_thumbnail():
    """Regenerate only the thumbnail section of a generated package. Plan-gated limits apply."""
    data = request.json or {}
    job_id = data.get('job_id', '')

    if not job_id:
        return jsonify({'error': 'job_id is required'}), 400

    job = generation_jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Generation job not found. It may have expired.'}), 404

    if job.get('status') != 'complete':
        return jsonify({'error': 'Package generation is not yet complete.'}), 400

    remaining = job.get('thumbnail_regens_remaining', 0)
    if remaining <= 0:
        plan = job.get('plan', 'basic')
        return jsonify({
            'error': 'No thumbnail regenerations remaining for your plan.',
            'regenerations_remaining': 0
        }), 402

    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    log_action(token, 'regenerate_thumbnail')

    try:
        current_package = job.get('package', '')
        vis_json = job.get('visual_json') or {}
        thumb_json = job.get('thumbnail_json') or {}

        regen_prompt = THUMBNAIL_REGENERATION_PROMPT.format(
            current_package=current_package[:8000],  # truncate to avoid token bloat
            visual_json=json.dumps(vis_json, indent=2),
            thumbnail_json=json.dumps(thumb_json, indent=2)
        )

        result = call_ai(regen_prompt, "Regenerate only the THUMBNAIL DESIGN section based on the sample data provided.", max_tokens=4096)

        # Extract just the thumbnail section from the result
        thumbnail_section = extract_thumbnail_section(result)
        if not thumbnail_section:
            thumbnail_section = result  # fallback: use raw result

        # Update the stored package — replace the old thumbnail section
        old_thumb_section = extract_thumbnail_section(current_package)
        if old_thumb_section and thumbnail_section:
            job['package'] = current_package.replace(old_thumb_section, thumbnail_section)
        else:
            job['package'] = current_package  # keep original if extraction failed

        # Update global last_generated_package for PDF download
        global last_generated_package
        last_generated_package = {'content': job['package'], 'title': job.get('title', '')}

        # Decrement remaining
        job['thumbnail_regens_remaining'] = remaining - 1

        return jsonify({
            'success': True,
            'thumbnail_section': thumbnail_section,
            'regenerations_remaining': job['thumbnail_regens_remaining']
        })

    except Exception as e:
        print(f"Thumbnail regeneration error: {e}")
        return jsonify({'error': 'Thumbnail regeneration failed. Please try again.'}), 500


@app.route('/api/download-package', methods=['GET'])
@require_token
def download_package():
    job_id = request.args.get('job_id', '')
    content = last_generated_package.get('content', '')
    title = last_generated_package.get('title', 'script')

    # Fallback: if the global is empty, try looking up by job_id
    if not content and job_id:
        job = generation_jobs.get(job_id, {})
        content = job.get('package', '') or job.get('result', '')
        title = job.get('title', 'script')

    if not content:
        return jsonify({'error': 'No package generated yet. Generate a script first.'}), 404

    safe_name = title[:50].replace(' ', '_').replace('/', '-').replace('\\', '-')
    filename = f"{safe_name}.pdf"

    try:
        pdf = FPDF(orientation='P', unit='mm', format='A4')
        pdf.set_margin(12)
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=12)
        pdf.set_font('Helvetica', size=8)

        for line in content.split('\n'):
            safe_line = line.encode('latin-1', errors='replace').decode('latin-1')
            if safe_line.strip():
                pdf.multi_cell(0, 4.0, text=safe_line, align='L')
            else:
                pdf.ln(4.0)

        buf = io.BytesIO()
        pdf.output(buf)
        buf.seek(0)
        return send_file(buf, as_attachment=True, download_name=filename, mimetype='application/pdf')
    except Exception as e:
        print(f"PDF generation error: {e}")
        return jsonify({'error': 'Failed to generate PDF. Please try again.'}), 500


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
    custom_limits = data.get('custom_limits', None)  # {max_videos, max_minutes}

    if not email:
        return jsonify({'error': 'Email is required'}), 400
    if plan not in PLAN_CONFIG:
        return jsonify({'error': f'Invalid plan. Choose: {", ".join(PLAN_CONFIG.keys())}'}), 400

    try:
        credits = max(1, min(9999, int(credits)))
    except (ValueError, TypeError):
        credits = 3

    token = create_token(email=email, credits=credits, plan=plan, custom_limits=custom_limits)
    try:
        send_token_email(email, token)
    except Exception as e:
        print(f"Failed to send email: {e}")

    return jsonify({
        'success': True,
        'token': token,
        'email': email,
        'credits': credits,
        'plan': plan,
        'custom_limits': custom_limits
    })


@app.route('/api/admin/plans', methods=['GET'])
@require_admin
def admin_list_plans():
    """Return all plans including hidden ones for admin reference."""
    return jsonify({
        'plans': {k: v for k, v in PLAN_CONFIG.items()},
        'hidden': list(HIDDEN_PLANS)
    })


@app.route('/api/admin/stats', methods=['GET'])
@require_admin
def admin_stats():
    """Dashboard stats: tokens, usage, feedback counts."""
    return jsonify(get_admin_stats())


@app.route('/api/admin/promo', methods=['GET', 'POST'])
@require_admin
def admin_promo():
    """GET: return current promo. POST: set new promo."""
    global promo_message
    if request.method == 'GET':
        return jsonify(promo_message)
    data = request.json or {}
    code = data.get('code', '').strip()
    message = data.get('message', '').strip()
    if not message:
        return jsonify({'error': 'Promo message is required'}), 400
    # Persist to DB first — if it fails, don't update in-memory state
    try:
        conn = get_db()
        conn.execute('CREATE TABLE IF NOT EXISTS promo (id INTEGER PRIMARY KEY, code TEXT, message TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
        conn.execute('INSERT INTO promo (code, message) VALUES (?, ?)', (code, message))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Promo DB write failed: {e}")
        return jsonify({'error': 'Failed to save promo. Please try again.'}), 500
    promo_message = {'code': code, 'text': message}
    return jsonify({'success': True, 'promo': promo_message})


@app.route('/api/promo', methods=['GET'])
def public_promo():
    """Public endpoint — returns current promo for the landing page marquee."""
    return jsonify(promo_message)


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

        # Aggregate content_type: video-footage if ANY frame has real motion, otherwise stills-only
        content_types = [r.get('content_type', 'video-footage') for r in results]
        if any(ct == 'video-footage' for ct in content_types):
            merged['content_type'] = 'video-footage'
        else:
            merged['content_type'] = 'stills-only'

        return jsonify({'visual_profile': merged, 'success': True})
    except Exception as e:
        print(f"Vision analysis error: {e}")
        return jsonify({'error': 'Image analysis failed. Please try again.'}), 500


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
        print(f"Thumbnail analysis error: {e}")
        return jsonify({'error': 'Thumbnail analysis failed. Please try again.'}), 500


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
        print(f"Auto-thumbnail error: {e}")
        return jsonify({'error': 'Thumbnail analysis failed. Please try again.'}), 500


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
    socketio.run(app, host='0.0.0.0', port=port)
