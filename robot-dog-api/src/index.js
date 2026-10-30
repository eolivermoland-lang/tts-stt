function toBase64(bytes) {
  let binary = "";
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
  }
  return btoa(binary);
}

const DEFAULT_MODEL = "@cf/google/gemma-4-26b-a4b-it";
const DEFAULT_SYSTEM =
  "Du er Bingo, en nysgjerrig robothund. Svar kort, morsomt og på norsk. Maks én kort setning, cirka 12 ord. Ikke bruk emoji.";

function clamp(value, low, high, fallback) {
  const number = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(number)) return fallback;
  return Math.max(low, Math.min(high, number));
}

function cleanMessages(messages) {
  if (!Array.isArray(messages)) return [];
  return messages
    .slice(-30)
    .filter((message) => message && typeof message === "object")
    .map((message) => ({
      role: ["user", "assistant", "system"].includes(message.role)
        ? message.role
        : "user",
      content:
        typeof message.content === "string"
          ? message.content.slice(0, 4000)
          : "",
    }))
    .filter((message) => message.content.trim().length > 0);
}

function messageText(out) {
  const content = out?.choices?.[0]?.message?.content;
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((part) => (typeof part === "string" ? part : part?.text || ""))
      .join("");
  }
  return out?.response || out?.result?.response || "";
}

async function ttsRequest(env, path, init = {}) {
  if (!env.TTS_URL) {
    return Response.json(
      { error: "TTS_URL er ikke satt i Workeren" },
      { status: 500 },
    );
  }

  const base = env.TTS_URL.replace(/\/$/, "");
  return fetch(`${base}${path}`, {
    ...init,
    headers: {
      "x-api-key": env.TTS_SECRET,
      ...(init.headers || {}),
    },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.headers.get("authorization") !== `Bearer ${env.ROBOT_TOKEN}`) {
      return new Response("unauthorized", { status: 401 });
    }

    try {
      if (url.pathname === "/status") {
        return Response.json({
          ok: true,
          service: "robot-dog-api",
          tts_configured: Boolean(env.TTS_URL),
          time: new Date().toISOString(),
        });
      }

      // 1) Lyd -> tekst
      if (url.pathname === "/stt" && request.method === "POST") {
        const buf = await request.arrayBuffer();
        if (buf.byteLength === 0) {
          return Response.json({ error: "tom lyd" }, { status: 400 });
        }

        const language = url.searchParams.get("language") || "no";
        const audio = toBase64(new Uint8Array(buf));
        const out = await env.AI.run("@cf/openai/whisper-large-v3-turbo", {
          audio,
          language,
          task: "transcribe",
          vad_filter: true,
        });

        return Response.json({ text: (out.text || "").trim() });
      }

      // 2) Tekst -> svar
      if (url.pathname === "/chat" && request.method === "POST") {
        const raw = await request.json().catch(() => ({}));
        const messages = cleanMessages(raw.messages);
        const system =
          typeof raw.system === "string" && raw.system.trim()
            ? raw.system.trim().slice(0, 4000)
            : DEFAULT_SYSTEM;
        const model =
          typeof raw.model === "string" &&
          /^@cf\/[a-zA-Z0-9._/-]+$/.test(raw.model)
            ? raw.model
            : DEFAULT_MODEL;
        const maxTokens = Math.round(
          clamp(
            raw.max_completion_tokens ?? raw.max_tokens,
            16,
            512,
            80,
          ),
        );
        const temperature = clamp(raw.temperature, 0, 2, 0.8);

        const input = {
          messages: [{ role: "system", content: system }, ...messages],
          temperature,
        };

        if (model.includes("gemma")) {
          // Gemma 4 har reasoning paa som standard. Uten dette kan svaret
          // bli tomt naar tokenbudsjettet er lite.
          input.max_completion_tokens = maxTokens;
          input.chat_template_kwargs = { enable_thinking: false };
        } else {
          input.max_tokens = maxTokens;
        }

        const out = await env.AI.run(model, input);
        return Response.json({ text: messageText(out).trim() });
      }

      // 3) Tekst -> lyd med din egen stemme
      if (url.pathname === "/say" && request.method === "POST") {
        const raw = await request.json().catch(() => ({}));
        const text = typeof raw.text === "string" ? raw.text.trim() : "";
        if (!text) {
          return Response.json({ error: "mangler text" }, { status: 400 });
        }
        if (text.length > 400) {
          return Response.json(
            { error: "teksten er for lang (maks 400 tegn)" },
            { status: 400 },
          );
        }

        const payload = { text };
        for (const key of [
          "voice",
          "exaggeration",
          "cfg_weight",
          "temperature",
          "repetition_penalty",
          "top_p",
          "lang_code",
          "max_tokens",
        ]) {
          if (raw[key] !== undefined && raw[key] !== null) {
            payload[key] = raw[key];
          }
        }

        const r = await ttsRequest(env, "/say", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (!r.ok) {
          return new Response(await r.text(), { status: 502 });
        }

        return new Response(r.body, {
          headers: {
            "content-type": "audio/wav",
            "cache-control": "no-store",
          },
        });
      }

      // 4) Stemmeprofiler fra den lokale TTS-serveren
      if (url.pathname === "/voices" && request.method === "GET") {
        const r = await ttsRequest(env, "/voices");
        if (!r.ok) {
          return new Response(await r.text(), { status: 502 });
        }
        return new Response(r.body, {
          headers: {
            "content-type": "application/json",
            "cache-control": "no-store",
          },
        });
      }

      if (
        url.pathname === "/voices/reload" &&
        request.method === "POST"
      ) {
        const r = await ttsRequest(env, "/voices/reload", {
          method: "POST",
        });
        if (!r.ok) {
          return new Response(await r.text(), { status: 502 });
        }
        return new Response(r.body, {
          headers: {
            "content-type": "application/json",
            "cache-control": "no-store",
          },
        });
      }

      return new Response("not found", { status: 404 });
    } catch (err) {
      return Response.json({ error: err.message }, { status: 500 });
    }
  },
};
