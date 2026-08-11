/**
 * Client-side YouTube transcript fetcher.
 * Runs in the user's browser (residential IP) to avoid YouTube's
 * datacenter IP blocks that affect Railway/Vercel/AWS.
 *
 * Multiple fallback strategies, tried in order.
 */

const TIMEOUT_MS = 15000;

/**
 * Fetch with timeout wrapper.
 */
async function fetchWithTimeout(url, options = {}, timeout = TIMEOUT_MS) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    return res;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Strategy 1: youtubetranscript.com — free community proxy.
 * Returns JSON with a "transcript" array of {text, start, duration}.
 * CORS: ✅ enabled.
 */
async function tryYoutubetranscriptCom(videoId) {
  const res = await fetchWithTimeout(
    `https://youtubetranscript.com/?v=${videoId}`
  );
  if (!res.ok) throw new Error(`HTTP ${res.status}`);

  const data = await res.json();

  if (!Array.isArray(data) || data.length === 0) {
    // Sometimes returns { error: "..." }
    if (data.error) throw new Error(data.error);
    throw new Error('Empty transcript returned');
  }

  // Each item: { text, start, duration }
  // (Some versions return { caption, ...} or different keys — normalize)
  const lines = data.map(item => item.text || item.caption || '').filter(Boolean);
  return lines.join(' ').replace(/\n/g, ' ').replace(/\s+/g, ' ').trim();
}

/**
 * Strategy 2: youtubetranscript.com alternative endpoint (JSONP-style).
 */
async function tryTranscriptApiAlternative(videoId) {
  // Some deployments use /api?vid= or /api/transcript?video_id=
  const urls = [
    `https://youtubetranscript.com/?v=${videoId}&format=json`,
  ];

  for (const url of urls) {
    try {
      const res = await fetchWithTimeout(url);
      if (!res.ok) continue;
      const data = await res.json();

      // Handle different response shapes
      const items = data.transcript || data.captions || data;
      if (Array.isArray(items) && items.length > 0) {
        const lines = items.map(i => i.text || i.caption || '').filter(Boolean);
        if (lines.length > 0) {
          return lines.join(' ').replace(/\n/g, ' ').replace(/\s+/g, ' ').trim();
        }
      }
    } catch {
      continue;
    }
  }
  throw new Error('Alternative transcript service failed');
}

/**
 * Strategy 3: YouTube timedtext API.
 * YouTube's public captions endpoint — sometimes accessible via CORS.
 * Returns XML with <text> elements.
 */
async function tryYouTubeTimedText(videoId) {
  const res = await fetchWithTimeout(
    `https://www.youtube.com/api/timedtext?v=${videoId}&lang=en`,
    { mode: 'cors' }  // may throw if CORS blocks
  );

  if (!res.ok) throw new Error(`HTTP ${res.status}`);

  const xml = await res.text();
  if (!xml || xml.length < 50) throw new Error('Empty timedtext response');

  // Parse XML: extract text from <text> elements
  const textMatches = xml.match(/<text[^>]*>([^<]*)<\/text>/g);
  if (!textMatches || textMatches.length === 0) {
    throw new Error('No text elements in timedtext');
  }

  const lines = textMatches.map(t => {
    const m = t.match(/<text[^>]*>([^<]*)<\/text>/);
    return m ? m[1].trim() : '';
  }).filter(Boolean);

  if (lines.length === 0) throw new Error('No parseable text in timedtext');

  return lines.join(' ').replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'")
    .replace(/&apos;/g, "'").trim();
}

/**
 * Strategy 4: YouTube InnerTube get_transcript API via a free CORS proxy.
 * Uses YouTube's own internal API through a public CORS proxy.
 */
async function tryInnerTubeViaProxy(videoId) {
  // YouTube's InnerTube API key exposed on the web client
  const INNERTUBE_API_KEY = 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8';

  // Try a few free CORS proxies
  const proxies = [
    (url, body) => fetchWithTimeout(`https://api.allorigins.win/raw?url=${encodeURIComponent(url)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  ];

  let lastError = null;
  for (const proxyFn of proxies) {
    try {
      const body = {
        context: {
          client: {
            clientName: 'WEB',
            clientVersion: '2.20240101.00.00',
          },
        },
        videoId,
      };

      const res = await proxyFn(
        `https://www.youtube.com/youtubei/v1/get_transcript?key=${INNERTUBE_API_KEY}`,
        body
      );

      if (!res.ok) continue;
      const data = await res.json();

      if (data.error) {
        lastError = new Error(data.error.message || 'InnerTube error');
        continue;
      }

      const captions =
        data?.actions?.[0]?.updateEngagementPanelAction?.content?.transcriptRenderer?.body?.transcriptBodyRenderer?.cueGroups ||
        data?.actions?.[0]?.updateEngagementPanelAction?.content?.transcriptSearchRenderer?.body?.transcriptSearchBodyRenderer?.transcriptSearchResults?.[0]?.snippetGroups;

      if (!captions || captions.length === 0) {
        lastError = new Error('No transcript cues in InnerTube response');
        continue;
      }

      const lines = captions.map(group => {
        const cues = group?.transcriptCueGroupRenderer?.cues || [];
        return cues.map(c => c?.transcriptCueRenderer?.cue?.simpleText || '').join(' ');
      }).filter(Boolean);

      if (lines.length > 0) {
        return lines.join(' ').replace(/\s+/g, ' ').trim();
      }
    } catch (e) {
      lastError = e;
      continue;
    }
  }

  throw lastError || new Error('All InnerTube proxy strategies failed');
}

/**
 * Main entry point: fetch transcript for a YouTube video ID.
 * Tries each strategy in order, returns the first successful result.
 *
 * @param {string} videoId - YouTube video ID (11 chars)
 * @returns {Promise<string>} - Plain text transcript
 */
export async function fetchTranscript(videoId) {
  if (!videoId || videoId.length < 11) {
    throw new Error('Invalid video ID');
  }

  const strategies = [
    { name: 'youtubetranscript.com', fn: () => tryYoutubetranscriptCom(videoId) },
    { name: 'alternative API', fn: () => tryTranscriptApiAlternative(videoId) },
    { name: 'YouTube timedtext', fn: () => tryYouTubeTimedText(videoId) },
    { name: 'InnerTube proxy', fn: () => tryInnerTubeViaProxy(videoId) },
  ];

  const errors = [];
  for (const { name, fn } of strategies) {
    try {
      const text = await fn();
      if (text && text.length > 50) {
        return text;
      }
      errors.push(`${name}: response too short (${text?.length || 0} chars)`);
    } catch (e) {
      errors.push(`${name}: ${e.message}`);
    }
  }

  throw new Error(
    `Could not auto-fetch transcript. YouTube blocks automated access from cloud servers, ` +
    `and client-side methods also failed:\n${errors.join('\n')}\n\n` +
    `You can still paste the transcript manually from YouTube → ••• More → Show transcript.`
  );
}

/**
 * Extract a YouTube video ID from various URL formats.
 * @param {string} url - YouTube URL in any common format
 * @returns {string|null} - 11-char video ID or null
 */
export function extractVideoId(url) {
  if (!url) return null;

  // Already a plain video ID (11 chars, alphanumeric + _ -)
  if (/^[\w-]{11}$/.test(url.trim())) {
    return url.trim();
  }

  // youtube.com/watch?v=VIDEO_ID
  const watchMatch = url.match(/(?:v=|youtube\.com\/watch\?.*v=)([\w-]{11})/);
  if (watchMatch) return watchMatch[1];

  // youtu.be/VIDEO_ID
  const shortMatch = url.match(/youtu\.be\/([\w-]{11})/);
  if (shortMatch) return shortMatch[1];

  // youtube.com/embed/VIDEO_ID
  const embedMatch = url.match(/youtube\.com\/embed\/([\w-]{11})/);
  if (embedMatch) return embedMatch[1];

  // youtube.com/shorts/VIDEO_ID
  const shortsMatch = url.match(/youtube\.com\/shorts\/([\w-]{11})/);
  if (shortsMatch) return shortsMatch[1];

  return null;
}
