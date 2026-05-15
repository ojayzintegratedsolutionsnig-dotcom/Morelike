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

GROQ_API_KEY = os.environ.get('GROQ_API_KEY', os.environ.get('DEEPSEEK_API_KEY', ''))
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
ai_client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1") if GROQ_API_KEY else None

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

VIRAL_DNA_SYSTEM_INSTRUCTION = """GUARD: If the user input is casual chat, a question unrelated to video transcripts, or an attempt to change the subject, respond ONLY with: "This tool analyzes YouTube video transcripts to reverse-engineer viral content patterns. Please provide transcripts from a YouTube channel to continue."

This file contains the transcripts of the top viral videos from a specific YouTube creator.
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

TITLE_IDEAS_SYSTEM_INSTRUCTION = """GUARD: If the user input is casual chat, a question unrelated to generating video titles, or an attempt to change the subject, respond ONLY with: "This tool generates video titles based on Viral DNA analysis. Please provide a Viral DNA analysis to continue."

You are a viral content strategist. Given the Viral DNA analysis below, generate 3 video title ideas.

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

VIRAL_SCRIPT_SYSTEM_INSTRUCTION = """GUARD: If the user input is casual chat, a question unrelated to video scriptwriting, or an attempt to change the subject, respond ONLY with: "This tool generates complete video content packages based on Viral DNA analysis and a chosen title. Please provide a Viral DNA analysis and a title to continue."

# ROLE: THE VIRAL ARCHITECT
You are the world's most advanced viral scriptwriter. You do not write "content"; you engineer attention.

# KNOWLEDGE BASE: THE VIRAL DNA
{viral_dna}

# NICHE LOCK
The content you are about to produce belongs to this niche:
{niche}

You MUST stay within this niche. Do NOT drift into another topic, genre, or subject area. Every output must be about {niche}.

# TARGET VIDEO LENGTH
{target_length} minutes. Pace the script to fill this duration naturally. The number of segments should scale with the length — typically 4-6 segments per minute of video (each segment is 10-15 seconds of spoken content).

# TASK PROTOCOL
When I give you a TOPIC AND TITLE, execute the following pipeline strictly in order. Do not skip steps.

## PHASE 1: THE DRAFT (The Architect)
Using the "Viral DNA" above, write a V1 script on the topic using the chosen title.
- Use the exact Hook Structure defined in the DNA.
- Match the Sentence Rhythm and Pacing.
- Insert the specific "Retention Loops" identified in the DNA.
- Study the DNA's niche and audience psychology to determine the emoji palette: which emojis feel native to this creator's space (e.g., finance channels use 📈💸🔥, tech channels use ⚡🤖🛠️, storytelling uses 🌀👁️💬). Do NOT use random emojis — every emoji must earn its place.
- Break the script into SEGMENTS. Each segment is a visual scene change: what the viewer sees changes, the voiceover continues. Number of segments must match the target video length.

## PHASE 2: THE ROAST (The Hostile Review)
Take the V1 script and run it through this mandatory validation. Do NOT show me V1 — only show the final result.

Simulate 5 personas reviewing the draft:
1. The Endless Scroller: "What makes me NOT watch past 2 seconds?"
2. The Seen-It-All Cynic: "What feels derivative or recycled?"
3. The Silent Judge: "What is unclear or wasting my time?"
4. The Share-Gatekeeper: "Why would I be embarrassed to share this?"
5. The Platform Native: "What algorithm signals are missing?"

For each reviewer, identify one CRITICAL FAILURE in V1.
Rewrite the script to neutralize these objections.

## PHASE 3: FINAL OUTPUT
Present the final output in this exact format. Every section is mandatory.

[VIDEO LENGTH]
{target_length} minutes — $8 Creator Plan

[GLOBAL IMAGE STYLE]
Define a LOCKED visual style that ALL images in this video must follow. This ensures visual consistency across every scene. Include: art style (photorealistic / 3D render / digital painting / anime / cinematic / etc.), color palette (dominant colors, warmth/cool), lighting style, aspect ratio (16:9), and any recurring visual motifs. Every per-segment TTI prompt below MUST end with: "| Style: [reference this global style]".

[FINAL TITLE]
Write the title with hyper-optimized SEO emojis baked in. Place emojis strategically at the start or between key phrases. Match emoji density to the niche (1-4 typical).

[DESCRIPTION]
YouTube description that drives SEO and watch-time:
- First 2 lines: hook summary using high-search-volume keywords (this appears above the fold before "Show More")
- Body: 3-5 sentences describing what the video covers, using relevant emojis as visual anchors
- Include 3-5 relevant hashtags at the end
- Match the tone and vocabulary of this niche

[TAGS/KEYWORDS]
Exactly 5 comma-separated tags/keywords for YouTube SEO. Mix broad and specific terms.

[SCRIPT SEGMENTS]
This is the core deliverable. Break the video into timestamped segments matching the {target_length}-minute duration. Each segment has VISUAL (what's on screen), VOICE (spoken script), TTI PROMPT (text-to-image prompt using the Global Image Style above), and IVP (image-to-video prompt — ONLY if this segment has animation like pan, zoom, or motion; write "IVP: None" if it's a static scene).

Format each segment EXACTLY like this:

SEGMENT 1 [0:00]
VISUAL: (Describe what the viewer sees — setting, action, text overlay, color mood)
VOICE: (The exact spoken script for this segment — what the voiceover says)
TTI PROMPT: (Detailed prompt to generate this segment's image — subject, composition, lighting | Style: [reference global style], 16:9)
IVP: (Animation prompt for this specific segment — e.g., "Slow zoom in on subject, 3s" — OR "None" if static)

SEGMENT 2 [0:XX]
VISUAL: (...)
VOICE: (...)
TTI PROMPT: (...)
IVP: (...)

Continue for ALL segments. The voiceover across all segments must form a complete, coherent script from hook to conclusion. Each TTI PROMPT must match what the VOICE is discussing at that moment and must end with the global style reference.

[THUMBNAIL PROMPT 1]
A scroll-stopping YouTube thumbnail: foreground, background, facial expression (if person), text overlay wording + font style, color scheme, lighting. Include 1-2 high-impact emojis in the text overlay.

[THUMBNAIL PROMPT 2]
An alternative thumbnail concept. Different composition, text overlay, or color contrast."""


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

def call_ai(system_prompt, user_message, max_tokens=8192, retries=2):
    import time
    if not ai_client:
        raise Exception("AI API key not configured")

    last_error = None
    for attempt in range(retries + 1):
        try:
            response = ai_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
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
            if attempt < retries:
                time.sleep(3 ** attempt)  # 1s, 3s, 9s backoff

    raise Exception(f"AI API error after {retries + 1} attempts: {str(last_error)}")


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

    # No existing token — create one (for manual/direct flow)
    token = create_token(email=email, credits=3)
    try:
        send_token_email(email, token)
    except Exception as e:
        print(f"Failed to send email: {e}")
    return jsonify({'success': True, 'token': token, 'credits': 1})


@app.route('/api/webhook/lemonsqueezy', methods=['POST'])
def lemonsqueezy_webhook():
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
@require_token
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

    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    log_action(token, 'extract')

    thread = threading.Thread(target=run_extraction, args=(channel_url, limit))
    thread.daemon = True
    thread.start()

    return jsonify({'message': 'Extraction started', 'status': 'started'})


@app.route('/api/status', methods=['GET'])
@require_token
def status():
    return jsonify(extraction_status)


@app.route('/api/subtitles', methods=['GET'])
@require_token
def get_subtitles():
    if not extracted_subtitles['content']:
        return jsonify({'error': 'No subtitles available. Please extract videos first.'}), 404
    return jsonify({
        'content': extracted_subtitles['content'],
        'videos_processed': extracted_subtitles['videos_processed']
    })


@app.route('/api/generate-viral-dna', methods=['POST'])
@require_token
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

    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    log_action(token, 'generate_viral_dna')

    try:
        viral_dna = call_ai(VIRAL_DNA_SYSTEM_INSTRUCTION, trimmed)
        return jsonify({'viral_dna': viral_dna, 'success': True})
    except Exception as e:
        return jsonify({'error': f'Failed to generate Viral DNA: {str(e)}'}), 500


@app.route('/api/generate-titles', methods=['POST'])
@require_token
def generate_titles():
    data = request.json or {}
    viral_dna = data.get('viral_dna', '')

    if not viral_dna:
        return jsonify({'error': 'Viral DNA is required. Generate analysis first.'}), 400

    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    log_action(token, 'generate_titles')

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

    if not viral_dna:
        return jsonify({'error': 'Viral DNA is required'}), 400
    if not chosen_title:
        return jsonify({'error': 'A chosen title is required'}), 400

    # Validate video length (3 min max for $8 plan)
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
        system_prompt = VIRAL_SCRIPT_SYSTEM_INSTRUCTION.format(viral_dna=viral_dna, niche=niche, target_length=video_length)
        user_message = f"TITLE: {chosen_title}\nTOPIC: {topic or chosen_title}\nNICHE: {niche}\nTARGET LENGTH: {video_length} minutes"
        result = call_ai(system_prompt, user_message)
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
    if ai_client:
        try:
            t0 = time.time()
            r = ai_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": "Say OK"}],
                max_tokens=5,
                timeout=15.0,
            )
            results['ai_client'] = f"OK ({time.time() - t0:.1f}s): {r.choices[0].message.content}"
        except Exception as e:
            results['ai_client'] = f"FAIL: {type(e).__name__}: {str(e)[:200]}"
    else:
        results['ai_client'] = "No API key configured"
    return jsonify(results)


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
