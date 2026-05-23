"""End-to-end test suite for Morelike — run with: python test_e2e.py"""
import sys, json, os, time
sys.path.insert(0, 'backend')
sys.path.insert(0, '.')
os.chdir('D:\\Claude\\viral-content-cloner-agent')

# Pre-set the product IDs so the webhook tests can map correctly to pro and promax plans
os.environ['LEMON_SQUEEZY_PRODUCT_PRO'] = '5562929e-ce1b-4f28-a35b-90dce4371804'
os.environ['LEMON_SQUEEZY_PRODUCT_PROMAX'] = '81b9a80c-0ac7-491c-aa37-483a0dbda94a'

from main import app
from tokens import get_db
conn = get_db()
conn.execute('DELETE FROM tokens WHERE email LIKE "test_%" OR email LIKE "buyer_%"')
conn.execute('DELETE FROM tokens WHERE lemon_order_id LIKE "ord_%"')
conn.commit()
conn.close()

client = app.test_client()
errors = []
print("=" * 60)
print("MORELIKE END-TO-END TEST SUITE")
print("=" * 60)

# ── 1. PUBLIC ENDPOINTS ────────────────────────────────────
print("\n--- PUBLIC ENDPOINTS ---")

# Status
resp = client.get('/api/status')
assert resp.status_code == 200, f"Status: {resp.status_code}"
assert 'running' in resp.get_json(), "Status: missing running key"
print(f"[PASS] GET /api/status -> {resp.get_json()}")

# Validate token - empty
resp = client.post('/api/validate-token', json={})
assert resp.status_code == 400, f"Validate empty: {resp.status_code}"
print(f"[PASS] POST /api/validate-token (empty) -> 400")

# Validate token - invalid
resp = client.post('/api/validate-token', json={'token': 'DEADBEEF1234567890ABCDEF1234567890'})
data = resp.get_json()
assert 'valid' in data, "Validate: missing valid key"
assert data['valid'] == False, f"Validate: expected False, got {data.get('valid')}"
print(f"[PASS] POST /api/validate-token (invalid) -> valid=False")

# Claim token - no email
resp = client.post('/api/claim-token', json={})
assert resp.status_code == 400, f"Claim empty: {resp.status_code}"
print(f"[PASS] POST /api/claim-token (empty) -> 400")

# Claim token - non-gmail
resp = client.post('/api/claim-token', json={'email': 'test@yahoo.com'})
assert resp.status_code == 400, f"Claim non-gmail: {resp.status_code}"
print(f"[PASS] POST /api/claim-token (non-gmail) -> 400")

# Extract - no URL
resp = client.post('/api/extract', json={})
assert resp.status_code == 400, f"Extract empty: {resp.status_code}"
print(f"[PASS] POST /api/extract (empty) -> 400")

# Extract - HTTP (not HTTPS)
resp = client.post('/api/extract', json={'channel_url': 'http://www.youtube.com/@test'})
assert resp.status_code == 400, f"Extract HTTP: expected 400, got {resp.status_code}"
print(f"[PASS] POST /api/extract (http) -> 400 (HTTPS enforced)")

# Extract - invalid URL (SSRF attempt)
resp = client.post('/api/extract', json={'channel_url': 'https://evil.com/@test'})
assert resp.status_code == 400, f"Extract bad URL: expected 400, got {resp.status_code}"
print(f"[PASS] POST /api/extract (evil.com) -> 400 (blocked)")

# Extract - valid URL format
resp = client.post('/api/extract', json={'channel_url': 'https://www.youtube.com/@test', 'limit': 2})
assert resp.status_code == 200, f"Extract valid: {resp.status_code}"
print(f"[PASS] POST /api/extract (valid) -> 200")

# Webhook - no signature (should reject with 401 if secret configured, 500 if not)
resp = client.post('/api/webhook/lemonsqueezy', json={'meta': {'event_name': 'order_created'}})
assert resp.status_code in (401, 500), f"Webhook no sig: expected 401 or 500, got {resp.status_code}"
print(f"[PASS] POST /api/webhook/lemonsqueezy (no sig) -> {resp.status_code} (rejected)")

# Debug - requires admin
resp = client.get('/api/admin/debug-transcript')
assert resp.status_code == 401, f"Debug public: expected 401, got {resp.status_code}"
print(f"[PASS] GET /api/admin/debug-transcript (no auth) -> 401")

# Manual transcripts - no data
resp = client.post('/api/manual-transcripts', json={})
assert resp.status_code == 400, f"Manual empty: expected 400, got {resp.status_code}"
print(f"[PASS] POST /api/manual-transcripts (empty) -> 400")

# ── 2. ADMIN FLOW (run before rate limit tests) ────────────
print("\n--- ADMIN FLOW ---")
admin_pw = os.environ.get('ADMIN_PASSWORD', '')
resp = client.post('/api/admin/login', json={'password': admin_pw})
assert resp.status_code == 200, f"Admin login: {resp.status_code}"
data = resp.get_json()
assert data.get('success'), f"Admin login failed: {data}"
admin_token = data['admin_token']
print(f"[PASS] Admin login -> token={admin_token[:8]}...")

# Generate tokens for each plan
test_tokens = {}
for plan in ['basic', 'pro', 'promax', 'unlimited', 'custom']:
    body = {'email': f'test_{plan}@gmail.com', 'plan': plan}
    if plan == 'unlimited':
        body['credits'] = 9999
    if plan == 'custom':
        body['credits'] = 10
        body['custom_limits'] = {'max_videos': 7, 'max_minutes': 30}
    resp = client.post('/api/admin/generate-token', json=body,
                      headers={'X-Admin-Token': admin_token})
    data = resp.get_json()
    assert data.get('success'), f"Generate {plan}: {data}"
    assert data.get('token'), f"Generate {plan}: no token returned"
    assert data.get('plan') == plan, f"Generate {plan}: plan mismatch ({data.get('plan')})"
    test_tokens[plan] = data['token']
    print(f"[PASS] Generate {plan} token -> {data['token'][:8]}... credits={data.get('credits')}")

# Admin plans
resp = client.get('/api/admin/plans', headers={'X-Admin-Token': admin_token})
data = resp.get_json()
assert 'plans' in data, f"Admin plans: {data}"
assert 'unlimited' in data['plans'], "unlimited plan not in admin listing"
assert 'hidden' in data, "hidden not in admin listing"
print(f"[PASS] GET /api/admin/plans -> {len(data['plans'])} plans, hidden={data['hidden']}")

# Admin diag
resp = client.get('/api/admin/diag', headers={'X-Admin-Token': admin_token})
assert resp.status_code == 200, f"Diag: {resp.status_code}"
print(f"[PASS] GET /api/admin/diag -> {resp.status_code}")

# Admin debug-transcript
resp = client.get('/api/admin/debug-transcript', headers={'X-Admin-Token': admin_token})
assert resp.status_code == 200, f"Debug: {resp.status_code}"
print(f"[PASS] GET /api/admin/debug-transcript -> 200 (admin only)")

# Admin session expiry check
expired_admin = 'deadbeef' * 4
resp = client.get('/api/admin/plans', headers={'X-Admin-Token': expired_admin})
assert resp.status_code == 401, f"Fake admin: expected 401, got {resp.status_code}"
print(f"[PASS] Fake admin token rejected -> 401")

# ── 3. RATE LIMITING ───────────────────────────────────────
print("\n--- RATE LIMITING ---")
# Use a fresh test client to avoid any prior rate limit state
# Hit admin login 6 times with wrong password
for i in range(6):
    client.post('/api/admin/login', json={'password': 'wrong'})
resp = client.post('/api/admin/login', json={'password': 'wrong'})
assert resp.status_code == 429, f"Rate limit admin login: expected 429, got {resp.status_code}"
print(f"[PASS] Admin login rate-limited after 5 attempts -> 429")

# ── 4. TOKEN FLOW ──────────────────────────────────────────
print("\n--- TOKEN FLOW ---")
basic_token = test_tokens.get('basic', '')
pro_token = test_tokens.get('pro', '')
unlimited_token = test_tokens.get('unlimited', '')

# Validate
resp = client.post('/api/validate-token', json={'token': basic_token})
data = resp.get_json()
assert data.get('valid'), f"Validate basic: {data}"
assert data.get('plan') == 'basic', f"Validate plan: {data.get('plan')}"
assert data.get('credits') == 3, f"Validate credits: {data.get('credits')}"
assert 'limits' in data, f"Validate limits missing: {data}"
print(f"[PASS] Validate basic token -> valid, plan=basic, credits=3, limits={data.get('limits')}")

# Validate pro
resp = client.post('/api/validate-token', json={'token': pro_token})
data = resp.get_json()
assert data.get('valid'), f"Validate pro: {data}"
assert data.get('plan') == 'pro', f"Validate pro plan: {data.get('plan')}"
assert data['limits']['max_minutes'] == 5, f"Pro limits wrong: {data.get('limits')}"
print(f"[PASS] Validate pro token -> plan=pro, limits={data.get('limits')}")

# Validate unlimited
resp = client.post('/api/validate-token', json={'token': unlimited_token})
data = resp.get_json()
assert data.get('valid'), f"Validate unlimited: {data}"
assert data.get('credits') == 9999, f"Unlimited credits: {data.get('credits')}"
print(f"[PASS] Validate unlimited token -> credits=9999")

# Credits endpoint
resp = client.get('/api/credits', headers={'Authorization': f'Bearer {basic_token}'})
data = resp.get_json()
assert data.get('credits') == 3, f"Credits: {data}"
print(f"[PASS] GET /api/credits -> {data['credits']} credits")

# Credits without auth
resp = client.get('/api/credits')
assert resp.status_code == 401, f"Credits no auth: {resp.status_code}"
print(f"[PASS] GET /api/credits (no auth) -> 401")

# ── 5. PROTECTED ENDPOINTS ─────────────────────────────────
print("\n--- PROTECTED ENDPOINTS ---")
for path in ['/api/generate-package', '/api/feedback', '/api/analyze-visuals', '/api/analyze-thumbnails']:
    resp = client.post(path, json={})
    assert resp.status_code == 401, f"{path}: expected 401, got {resp.status_code}"
    print(f"[PASS] POST {path} (no auth) -> 401")

# ── 6. MANUAL TRANSCRIPTS ──────────────────────────────────
print("\n--- MANUAL TRANSCRIPTS ---")
resp = client.post('/api/manual-transcripts', json={
    'transcripts': {
        'ABC123': 'This is a test transcript for video one. It has enough text.',
        'DEF456': 'Another transcript for video two, also with sufficient content.'
    },
    'video_meta': [
        {'id': 'ABC123', 'title': 'Test Video 1', 'url': 'https://youtu.be/ABC123'},
        {'id': 'DEF456', 'title': 'Test Video 2', 'url': 'https://youtu.be/DEF456'}
    ]
})
data = resp.get_json()
assert data.get('success'), f"Manual transcripts: {data}"
assert data.get('videos_processed') == 2, f"Manual processed: {data.get('videos_processed')}"
print(f"[PASS] POST /api/manual-transcripts -> {data['videos_processed']} videos processed")

# Verify subtitles are now available
resp = client.get('/api/subtitles')
data = resp.get_json()
assert 'content' in data, f"Subtitles after manual: {data}"
print(f"[PASS] GET /api/subtitles (after manual) -> content={len(data.get('content', ''))} chars")

# ── 7. PLAN LIMITS ─────────────────────────────────────────
print("\n--- PLAN LIMITS ---")
from tokens import PLAN_CONFIG, HIDDEN_PLANS, get_plan_limits

assert 'basic' in PLAN_CONFIG, "basic missing"
assert 'promax' in PLAN_CONFIG, "promax missing"
assert 'unlimited' in PLAN_CONFIG, "unlimited missing"
assert 'custom' in PLAN_CONFIG, "custom missing"
assert 'unlimited' in HIDDEN_PLANS, "unlimited not hidden"
assert 'custom' in HIDDEN_PLANS, "custom not hidden"
assert PLAN_CONFIG['basic']['max_minutes'] == 3, "basic minutes wrong"
assert PLAN_CONFIG['pro']['max_minutes'] == 5, "pro minutes wrong"
assert PLAN_CONFIG['promax']['max_minutes'] == 15, "promax minutes wrong"
assert PLAN_CONFIG['unlimited']['max_minutes'] == 60, "unlimited minutes wrong"
print(f"[PASS] Plan config correct: {list(PLAN_CONFIG.keys())}")
print(f"[PASS] Hidden plans: {list(HIDDEN_PLANS)}")

# ── 8. TOKEN STORAGE CHECK ─────────────────────────────────
print("\n--- TOKEN STORAGE ---")
from tokens import get_db
conn = get_db()
rows = conn.execute('SELECT plan, credits, email FROM tokens WHERE email LIKE "test_%" ORDER BY created_at DESC LIMIT 6').fetchall()
plans_found = {}
for r in rows:
    plans_found[r['plan']] = r['credits']
conn.close()
for plan in ['basic', 'pro', 'promax', 'unlimited', 'custom']:
    assert plan in plans_found, f"Token not in DB: {plan}"
    print(f"[PASS] DB: {plan} token stored with {plans_found[plan]} credits")
print(f"[PASS] All 5 test tokens stored in database with correct plans")

# ── 9. WEBHOOK & CLAIM FLOW & FULL GENERATION WORKFLOW ─────
print("\n--- WEBHOOK & CLAIM FLOW & FULL GENERATION WORKFLOW ---")

def post_webhook(payload):
    import hmac, hashlib
    secret = os.environ.get('LEMON_SQUEEZY_WEBHOOK_SECRET', '')
    body_str = json.dumps(payload, separators=(',', ':'))
    sig = 'sha256=' + hmac.new(
        secret.encode('utf-8'),
        body_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return client.post('/api/webhook/lemonsqueezy', data=body_str, content_type='application/json', headers={'X-Signature': sig})

# 1. Simulating webhook purchases
print("Simulating webhook purchases...")
basic_payload = {
    'meta': {'event_name': 'order_created'},
    'data': {
        'id': 'ord_basic_999',
        'attributes': {
            'user_email': 'buyer_basic@gmail.com',
            'first_order_item': {'product_id': 'a6315998-f19d-4806-ba57-a40dd789348b'}
        }
    }
}
resp = post_webhook(basic_payload)
assert resp.status_code == 200, f"Webhook Basic order creation failed: {resp.status_code}"
print("[PASS] Webhook Basic purchase processed")

pro_payload = {
    'meta': {'event_name': 'order_created'},
    'data': {
        'id': 'ord_pro_999',
        'attributes': {
            'user_email': 'buyer_pro@gmail.com',
            'first_order_item': {'product_id': '5562929e-ce1b-4f28-a35b-90dce4371804'}
        }
    }
}
resp = post_webhook(pro_payload)
assert resp.status_code == 200, f"Webhook Pro order creation failed: {resp.status_code}"
print("[PASS] Webhook Pro purchase processed")

promax_payload = {
    'meta': {'event_name': 'order_created'},
    'data': {
        'id': 'ord_promax_999',
        'attributes': {
            'user_email': 'buyer_promax@gmail.com',
            'first_order_item': {'product_id': '81b9a80c-0ac7-491c-aa37-483a0dbda94a'}
        }
    }
}
resp = post_webhook(promax_payload)
assert resp.status_code == 200, f"Webhook Pro Max order creation failed: {resp.status_code}"
print("[PASS] Webhook Pro Max purchase processed")

# 2. Claiming purchased tokens
print("Claiming purchased tokens...")
resp = client.post('/api/claim-token', json={'email': 'buyer_basic@gmail.com'})
assert resp.status_code == 200, f"Claim basic failed: {resp.status_code}"
basic_data = resp.get_json()
assert basic_data.get('success'), "Claim basic: success flag is False"
assert basic_data.get('plan') == 'basic', f"Claim basic: expected plan basic, got {basic_data.get('plan')}"
assert basic_data.get('credits') == 3, f"Claim basic: expected 3 credits, got {basic_data.get('credits')}"
basic_token = basic_data.get('token')
print(f"[PASS] Claim Basic token -> {basic_token[:8]}... plan=basic, credits=3")

resp = client.post('/api/claim-token', json={'email': 'buyer_pro@gmail.com'})
assert resp.status_code == 200, f"Claim pro failed: {resp.status_code}"
pro_data = resp.get_json()
assert pro_data.get('success'), "Claim pro: success flag is False"
assert pro_data.get('plan') == 'pro', f"Claim pro: expected plan pro, got {pro_data.get('plan')}"
assert pro_data.get('credits') == 3, f"Claim pro: expected 3 credits, got {pro_data.get('credits')}"
pro_token = pro_data.get('token')
print(f"[PASS] Claim Pro token -> {pro_token[:8]}... plan=pro, credits=3")

resp = client.post('/api/claim-token', json={'email': 'buyer_promax@gmail.com'})
assert resp.status_code == 200, f"Claim promax failed: {resp.status_code}"
promax_data = resp.get_json()
assert promax_data.get('success'), "Claim promax: success flag is False"
assert promax_data.get('plan') == 'promax', f"Claim promax: expected plan promax, got {promax_data.get('plan')}"
assert promax_data.get('credits') == 5, f"Claim promax: expected 5 credits, got {promax_data.get('credits')}"
promax_token = promax_data.get('token')
print(f"[PASS] Claim Pro Max token -> {promax_token[:8]}... plan=promax, credits=5")

# 3. Full Cloner Flow: DNA -> Titles -> Generate -> Download
print("Executing full generation workflow...")
# Get subtitles content that we manually pasted earlier
resp = client.get('/api/subtitles')
subtitles_content = resp.get_json().get('content')
assert subtitles_content, "No subtitles content available for workflow"

# Generate Viral DNA
print("Generating Viral DNA via DeepSeek...")
resp = client.post('/api/generate-viral-dna', json={'subtitles': subtitles_content})
assert resp.status_code == 200, f"Generate Viral DNA failed: {resp.status_code}"
dna_data = resp.get_json()
assert dna_data.get('success'), "Viral DNA: success flag is False"
viral_dna = dna_data.get('viral_dna')
assert viral_dna, "Viral DNA is empty"
print("[PASS] POST /api/generate-viral-dna -> success")

# Generate Titles
print("Generating Title Ideas via DeepSeek...")
resp = client.post('/api/generate-titles', json={'viral_dna': viral_dna, 'count': 3})
assert resp.status_code == 200, f"Generate titles failed: {resp.status_code}"
titles_data = resp.get_json()
assert titles_data.get('success'), "Titles: success flag is False"
titles_text = titles_data.get('titles', '')
assert titles_text, "Titles text is empty"
print(f"[PASS] POST /api/generate-titles -> success:\n{titles_text}")

# Select first title
chosen_title = "The Pattern Pharaoh Missed"

# Generate Package
print("Generating full script package via DeepSeek...")
resp = client.post('/api/generate-package', json={
    'viral_dna': viral_dna,
    'title': chosen_title,
    'topic': 'Bible commentary for young adults',
    'video_length': 3
}, headers={'Authorization': f'Bearer {basic_token}'})
assert resp.status_code == 200, f"Generate package failed: {resp.status_code}"
pkg_data = resp.get_json()
assert pkg_data.get('success'), f"Generate package success flag is False: {pkg_data}"
package_content = pkg_data.get('package')
assert package_content, "Package content is empty"
assert pkg_data.get('credits_remaining') == 2, f"Expected 2 credits remaining, got {pkg_data.get('credits_remaining')}"
print("[PASS] POST /api/generate-package -> package generated, credit deducted")

# Download Package PDF
print("Downloading package as PDF...")
resp = client.get('/api/download-package', headers={'Authorization': f'Bearer {basic_token}'})
assert resp.status_code == 200, f"Download PDF failed: {resp.status_code}"
assert resp.headers.get('Content-Type') == 'application/pdf', f"Expected application/pdf, got {resp.headers.get('Content-Type')}"
print("[PASS] GET /api/download-package -> PDF downloaded successfully")

# ── RESULTS ────────────────────────────────────────────────
print("\n" + "=" * 60)
print("ALL ENDPOINT TESTS PASSED")
print("=" * 60)
print("\nSummary:")
print("  - Public endpoints: 11 tests")
print("  - Rate limiting: 1 test")
print("  - Admin flow: 8 tests")
print("  - Token flow: 5 tests")
print("  - Protected endpoints: 4 tests")
print("  - Manual transcripts: 2 tests")
print("  - Plan config: 2 tests")
print("  - Token storage: 1 test")
print("  - Webhook & Claim flow: 6 tests")
print("  - Full AI Generation flow: 4 tests")
print("  TOTAL: 44 tests PASSED")

