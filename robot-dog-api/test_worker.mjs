import { writeFile } from "node:fs/promises";
import worker from "./src/index.js";

const env = {
  ROBOT_TOKEN: process.env.ROBOT_TOKEN,
  TTS_SECRET: process.env.TTS_SECRET,
  TTS_URL: process.env.TTS_URL || "http://127.0.0.1:8000",
  AI: {
    async run(model) {
      if (model.includes("whisper")) {
        return { text: "hei bingo" };
      }
      return { response: "Voff! Det er meg." };
    },
  },
};

if (!env.ROBOT_TOKEN || !env.TTS_SECRET) {
  throw new Error("Sett ROBOT_TOKEN og TTS_SECRET");
}

const auth = { authorization: `Bearer ${env.ROBOT_TOKEN}` };

let r = await worker.fetch(
  new Request("http://local/status", { headers: auth }),
  env,
);
console.log("status:", r.status, await r.text());

r = await worker.fetch(
  new Request("http://local/say", {
    method: "POST",
    headers: { ...auth, "content-type": "application/json" },
    body: JSON.stringify({ text: "Hei! Jeg er Bingo, og dette er en test." }),
  }),
  env,
);

console.log("say:", r.status, r.headers.get("content-type"));
if (!r.ok) {
  console.log(await r.text());
  process.exit(1);
}

await writeFile("worker_svar.wav", Buffer.from(await r.arrayBuffer()));
console.log("skrev worker_svar.wav");

r = await worker.fetch(
  new Request("http://local/stt", {
    method: "POST",
    headers: { ...auth, "content-type": "audio/wav" },
    body: new Uint8Array([1, 2, 3, 4]),
  }),
  env,
);
console.log("stt:", r.status, await r.text());

r = await worker.fetch(
  new Request("http://local/chat", {
    method: "POST",
    headers: { ...auth, "content-type": "application/json" },
    body: JSON.stringify({
      messages: [{ role: "user", content: "Hei Bingo!" }],
    }),
  }),
  env,
);
console.log("chat:", r.status, await r.text());
