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

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
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

VIRAL_DNA_SYSTEM_INSTRUCTION = """This file contains the transcripts of the top viral videos from a specific creator.
I want you to reverse-engineer their "Viral Algorithm."

Do NOT summarize the content. I don't care about the topic.
Focus 100% on the SYNTAX and PSYCHOLOGY.

Create a "Structural Style Guide" that includes:

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
- Create a blank "Fill-in-the-Blanks" script template that follows their exact pacing structure, which I can use for ANY topic."""

TITLE_IDEAS_SYSTEM_INSTRUCTION = """You are a viral content strategist. Given the Viral DNA analysis below, generate 5 video title ideas that follow the same style, hooks, and audience psychology as the analyzed channel.

The Viral DNA is:
{viral_dna}

Generate exactly 3 titles. Each title must:
- Feel like it could be a real video from this creator's niche
- Use the hook patterns identified in the DNA
- Be specific enough to spark curiosity
- Avoid clickbait cliches that the original creator wouldn't use

Return EXACTLY in this format (no extra text):

1. [First title]
2. [Second title]
3. [Third title]
4. [Fourth title]
5. [Fifth title]"""

VIRAL_SCRIPT_SYSTEM_INSTRUCTION = """# ROLE: THE VIRAL ARCHITECT
You are the world's most advanced viral scriptwriter. You do not write "content"; you engineer attention.

# KNOWLEDGE BASE: THE VIRAL DNA
{viral_dna}

# TASK PROTOCOL
When I give you a TOPIC AND TITLE, you will execute the following pipeline strictly in order. Do not skip steps.

## PHASE 1: THE DRAFT (The Architect)
Using the "Viral DNA" above, write a V1 script on the topic using the chosen title.
- Use the exact Hook Structure defined in the DNA.
- Match the Sentence Rhythm and Pacing.
- Insert the specific "Retention Loops" identified in the DNA.

## PHASE 2: THE ROAST (The Hostile Review)
Now, take that V1 script and run it through this mandatory validation protocol. Do not show me the V1 script yet. Only show me the final result.

Simulate these 5 specific personas reviewing the draft:
1. The Endless Scroller: "What makes me NOT watch past 2 seconds?"
2. The Seen-It-All Cynic: "What feels derivative or recycled?"
3. The Silent Judge: "What is unclear or wasting my time?"
4. The Share-Gatekeeper: "Why would I be embarrassed to share this?"
5. The Platform Native: "What algorithm signals are missing?"

For each reviewer, identify one CRITICAL FAILURE in the V1 draft.
Rewrite the script to neutralize these objections.

## PHASE 3: FINAL OUTPUT
Present the final, approved output in this exact format:

[FINAL TITLE]
(The chosen title)

[VISUAL HOOK]
(Describe the first 3 seconds visually — what the viewer sees that stops them from scrolling)

[THE SCRIPT]
(The full polished script with timestamp markers like [0:00], [0:30], [1:00], etc., and visual cues in [brackets])

[THUMBNAIL CONCEPT]
(Describe a scroll-stopping thumbnail: what's in the foreground, background, facial expression, text overlay, colors)

[TEXT-TO-IMAGE PROMPT]
(A detailed prompt ready to paste into Midjourney / DALL-E / Stable Diffusion to generate the thumbnail image)

[VOICEOVER PROMPT]
(A performance direction prompt for AI voiceover tools like ElevenLabs: tone, pacing, emotional register, any character notes)

[VIRALITY CHECKLIST]
- Hook Strategy Used: [Explain]
- Retention Loop Used: [Explain]
- Why the Cynic will watch this: [Explain]"""


# ── OpenAI helpers ────────────────────────────────────────────

def call_openai(system_prompt, user_message, max_tokens=8192):
    if not openai_client:
        raise Exception("OpenAI API key not configured")
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        temperature=1.0,
        max_tokens=max_tokens
    )
    return response.choices[0].message.content


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

    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    log_action(token, 'generate_viral_dna')

    try:
        viral_dna = call_openai(VIRAL_DNA_SYSTEM_INSTRUCTION, subtitles)
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
        system_prompt = TITLE_IDEAS_SYSTEM_INSTRUCTION.format(viral_dna=viral_dna)
        result = call_openai(system_prompt, "Generate 5 title ideas based on the Viral DNA.")
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

    if not viral_dna:
        return jsonify({'error': 'Viral DNA is required'}), 400
    if not chosen_title:
        return jsonify({'error': 'A chosen title is required'}), 400

    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    creds = get_credits(token)
    if not creds or creds['credits'] <= 0:
        return jsonify({'error': 'No credits remaining. Purchase more to continue.'}), 402

    log_action(token, 'generate_package')

    try:
        system_prompt = VIRAL_SCRIPT_SYSTEM_INSTRUCTION.format(viral_dna=viral_dna)
        user_message = f"TITLE: {chosen_title}\nTOPIC: {topic or chosen_title}"
        result = call_openai(system_prompt, user_message)
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
    socketio.run(app, debug=True, port=port, allow_unsafe_werkzeug=True)
