#!/usr/bin/env python3
"""fleet_vector_store.py — T-025 core (round-74 V-19 confirmed).
The fleet's collective brain, v1:
- numpy char-n-gram embeddings (deterministic, offline, no downloads)
- add + dedup gate (round-63: similarity < THRESHOLD = novel)
- search (nearest write-ups) for dispatch injection
- V-11: injection context-hash carried into receipts
- V-10 amendment 1: probe-pool treatment — known-answer checks at build
- V-18 standard: reports raw_in / duplicates / NOVEL out
Nothing binds until khalid signs."""
import hashlib, json, os, sys, time
import numpy as np

THRESHOLD = 0.85          # similarity >= this = duplicate (round-63 gate)
NGRAM = 3                 # char n-gram size
DIM = 256                 # embedding dim
SEED = 42

class VectorStore:
    def __init__(self, path=None):
        self.docs = []          # [{sha, text, topic, ts, receipt}]
        self.mat = np.zeros((0, DIM), dtype=np.float32)
        self.stats = {"raw_in": 0, "duplicates": 0, "novel": 0}
        self.path = path
        if path and os.path.exists(path):
            self._load(path)

    # ---- embedding: word-level hashing w/ stopword downweight (offline,
    # deterministic, verifiable). Char n-grams FAILED the probe-pool check:
    # common words (task, verified, receipt, ledger) dominated similarity,
    # collapsing different write-ups to 0.92-0.94. Word-level + stopword
    # removal separates genuine dup from genuine novel (calibrated 2026-08-15).
    # Retrieval precision was still 0/3 (V-20b): queries matched on shared
    # vocabulary, not meaning -> IDF weighting (rare words matter more).
    STOPWORDS = frozenset("the a an and or but of to in on for with at by from as is are was were be been being this that these those it its has have had not no so if then than too very just can will would should could may might do does did".split())
    def _idf(self, word):
        """Inverse document frequency: rare words dominate retrieval."""
        n = max(len(self.docs), 1)
        df = sum(1 for d in self.docs if word in d["text"].lower().split())
        return 1.0 + (n / (df + 1.0))
    def embed(self, text):
        v = np.zeros(DIM, dtype=np.float32)
        # split on ANY non-alphanumeric: "banana-spend" -> banana, spend
        words = self._tokens(text)
        for i in range(len(words)):
            for g in {words[i], (words[i - 1] + "_" + words[i]) if i else words[i]}:
                h = int(hashlib.md5(g.encode()).hexdigest(), 16)
                v[h % DIM] += self._idf(g.split("_")[-1])
        n = np.linalg.norm(v)
        return v / n if n > 0 else v

    def sim(self, a, b):
        va, vb = self.embed(a), self.embed(b)
        return float(np.dot(va, vb))

    # ---- round-63 dedup gate: novel only if below threshold vs ALL existing ----
    def add(self, text, topic, receipt, ts=None, force=False):
        self.stats["raw_in"] += 1
        if not force:
            for d in self.docs:
                if self.sim(text, d["text"]) >= THRESHOLD:
                    self.stats["duplicates"] += 1
                    return {"status": "duplicate", "sha": d["sha"],
                            "sim": round(self.sim(text, d["text"]), 3)}
        sha = hashlib.sha256(text.encode()).hexdigest()
        doc = {"sha": sha, "text": text, "topic": topic, "receipt": receipt,
               "ts": ts or int(time.time())}
        self.docs.append(doc)
        self.mat = np.vstack([self.mat, self.embed(text)])
        self.stats["novel"] += 1
        if self.path:
            self._save()
        return {"status": "novel", "sha": sha, "index": len(self.docs) - 1}

    # ---- retrieval: nearest write-ups to a task description (injection source) ----
    def search(self, query, k=3):
        if not self.docs:
            return []
        vq = self.embed(query)
        sims = self.mat @ vq
        q_tokens = set(self._tokens(query))
        out = []
        for i, d in enumerate(self.docs):
            s = float(sims[i])
            # hybrid: topic-token overlap bonus, IDF-weighted — "sign consent"
            # must prefer the rarer, more specific topic (consent > sign)
            t_tokens = set(self._tokens(d["topic"]))
            overlap = sum(self._idf(t) for t in q_tokens & t_tokens)
            denom = sum(self._idf(t) for t in t_tokens) or 1.0
            bonus = 0.6 * overlap / denom
            # exact full-topic match in query tokens is the canonical key:
            # "banana spend" must beat any partial overlap, period
            if t_tokens and t_tokens <= q_tokens:
                bonus += 0.5
            out.append({"sha": d["sha"], "topic": d["topic"],
                        "text": d["text"], "sim": round(s + bonus, 3)})
        out.sort(key=lambda x: x["sim"], reverse=True)
        return out[:k]

    # ---- tokenizer shared by embed + search (split on any non-alnum) ----
    @staticmethod
    def _tokens(text):
        import re as _re
        return [w for w in _re.split(r"[^a-z0-9]+", text.lower())
                if w and w not in VectorStore.STOPWORDS]

    # ---- V-11: injection context-hash (what the brick was given) ----
    def injection_hash(self, hits):
        payload = json.dumps([h["sha"] for h in hits], sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:24]

    # ---- V-10 amendment 1: probe-pool known-answer checks at build ----
    @staticmethod
    def probe_pool_check():
        s = VectorStore()
        a = s.add("brick alive on vast probe verify", "probe", "r1")
        b = s.add("brick alive on vast probe verify", "probe", "r2")     # dup
        c = s.add("token router lane queue dispatch", "router", "r3")    # novel
        hits = s.search("probe verify alive")
        ok = (b["status"] == "duplicate" and c["status"] == "novel"
              and hits and hits[0]["topic"] == "probe")
        return ok, s.stats, [h["topic"] for h in hits]

    # ---- persistence ----
    def _save(self):
        with open(self.path, "w") as f:
            json.dump({"docs": self.docs, "stats": self.stats}, f)

    def _load(self, path):
        with open(path) as f:
            d = json.load(f)
        self.docs = d["docs"]; self.stats = d["stats"]
        if self.docs:
            self.mat = np.vstack([self.embed(x["text"]) for x in self.docs])

def report(store, label):
    s = store.stats
    novel_hr = round(s["novel"] * 3600.0 / max(1, s["raw_in"]), 1)
    print(f"[{label}] raw_in={s['raw_in']} duplicates={s['duplicates']} "
          f"NOVEL={s['novel']} (novel/hr={novel_hr})")

if __name__ == "__main__":
    # build-time probe-pool check (V-10 amendment 1) — known-answer similarity
    ok, stats, topics = VectorStore.probe_pool_check()
    print("PROBE-POOL CHECK:", "PASS" if ok else "FAIL", "|", stats, "| hits:", topics)
    if not ok:
        sys.exit(1)
    print("vector store v1 ready — deterministic, offline, dedup-gated")
