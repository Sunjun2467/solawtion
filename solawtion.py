"""
soLAWtion AI 백엔드 (의미 기반 검색 + 로컬 Ollama 분석)
사전 준비:
  1. ollama pull exaone3.5:2.4b
  2. ollama pull bge-m3
  3. python build_index.py 로 precedents.db 생성
  4. Ollama 앱 실행 (또는 ollama serve)
실행: python solawtion.py
"""

# 설정
PORT          = 8000
DB_PATH       = "precedents.db"

# Ollama 분석 (LLM)
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL    = "exaone3.5:2.4b"
NUM_CTX         = 16384

# Ollama 임베딩
OLLAMA_EMB_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL    = "bge-m3"

from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
import sqlite3
import numpy as np


def ollama_chat(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"num_ctx": NUM_CTX},
    }
    res = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=600)
    res.raise_for_status()
    return res.json()["message"]["content"]


# ─────────────────────────────────────────
# 판례 인덱스 메모리 로드 (서버 시작 시 1회)
# ─────────────────────────────────────────
_conn = sqlite3.connect(DB_PATH)
_rows = _conn.execute(
    "SELECT prec_id, crime, court, case_number, date, name, link, body, embedding FROM precedents"
).fetchall()
EMBEDDINGS = np.stack([np.frombuffer(r[8], dtype=np.float32) for r in _rows])
EMBEDDINGS /= np.linalg.norm(EMBEDDINGS, axis=1, keepdims=True)
METAS = [dict(zip(["prec_id","crime","court","case_number","date","name","link","body"], r[:8])) for r in _rows]
print(f"📚 판례 인덱스 로드: {len(METAS)}개")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=False,
    allow_methods=["*"], allow_headers=["*"],
)

# ─────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────
def semantic_search(situation: str, top_k: int = 3):
    res = requests.post(OLLAMA_EMB_URL, json={
        "model": EMBED_MODEL, "prompt": situation[:3000],
    }, timeout=60)
    res.raise_for_status()
    q = np.array(res.json()["embedding"], dtype=np.float32)
    q /= np.linalg.norm(q)
    sims = EMBEDDINGS @ q
    order = np.argsort(-sims)
    # 사건번호 중복 제거하며 top_k 채우기
    hits, seen = [], set()
    for i in order:
        cn = METAS[i]["case_number"]
        if cn in seen:
            continue
        seen.add(cn)
        hits.append((METAS[i], float(sims[i])))
        if len(hits) >= top_k:
            break
    return hits


def absolutize(link: str) -> str:
    if not link:
        return ""
    return link if link.startswith("http") else "https://www.law.go.kr" + link

def format_date(raw_date: str) -> str:
    if len(raw_date) == 8:
        return f"{raw_date[:4]}.{raw_date[4:6]}.{raw_date[6:]}"
    return raw_date

# ─────────────────────────────────────────
# 엔드포인트
# ─────────────────────────────────────────
@app.get("/")
async def root():
    return {"status": "ok", "endpoints": ["/search", "/analyze"], "index_size": len(METAS)}


@app.get("/search")
async def search_endpoint(query: str = ""):
    if not query:
        raise HTTPException(400, "query 필요")
    hits = semantic_search(query, top_k=5)
    return {
        "items": [
            {
                "case_number": m["case_number"],
                "court": m["court"],
                "date": format_date(m["date"]),
                "name": m["name"],
                "link": absolutize(m["link"]),
                "similarity": round(s, 3),
            }
            for m, s in hits
        ]
    }


@app.post("/analyze")
async def analyze_endpoint(situation: str = Form(...)):
    # 1. 의미 기반 검색
    hits = semantic_search(situation, top_k=3)
    print(f"🔍 유사 판례: {[(m['case_number'], round(s,3)) for m, s in hits]}")

    # 2. 본문 (DB에 저장됨)
    prec_texts = []
    for meta, score in hits:
        header = (
            f"[참고 판례 정보 (유사도: {score:.3f})]\n"
            f"- 법원명: {meta['court']}\n"
            f"- 사건번호: {meta['case_number']}\n"
            f"- 선고일자: {meta['date']}\n"
            f"- 사건명: {meta['name']}\n"
        )
        prec_texts.append(f"{header}[판결문 본문]\n{meta['body'][:5000]}")
    combined = "\n\n---\n\n".join(prec_texts) if prec_texts else "(관련 판례 없음)"

    # 3. Ollama 분석
    prompt = f"""당신은 한국 형사법 전문 AI입니다. 관련 판례를 분석하여 답변해주세요.

[사용자 상황]
{situation}

[관련 판례]
{combined}

위 판례들을 참고하여 다음을 알려주세요: (판례가 없으면 없다고 말하고 절대 없는 말 지어내지 마세요)
1. 유사 판례 요약 
   ※ 주의: 제공된 판례를 요약할 때 아래 가이드라인을 반드시 엄격히 지켜주세요.
   - 제목 양식: ① [법원명] [사건번호] ([선고일자] 선고)
   - 제공된 판례를 모두 빠짐없이 요약하세요. ①, ②, ③ 순서로 번호 매기세요.
   - 포함할 내용:
     1) [실제 사건 내용]: 이 판례의 원인이 된 실제 사건의 구체적인 '사실관계와 상황(예:실제 닉네임, 어떤 욕설을 어떻게 했는지 등)'을 스토리 형태로 요약해 주세요. 추상적인 법률 용어로만 뭉뚱그리지 마세요.
     2) [법원의 판단 취지]: 해당 상황에 대해 법원이 왜 유죄나 무죄를 선고했는지 핵심 판단 이유를 설명해 주세요.

※ 이 답변은 법률 참고용이며 정식 법률 상담을 대체하지 않습니다."""

    try:
        analysis_text = ollama_chat(prompt)
    except Exception as e:
        print(f"🚨 [에러 발생] AI 분석 실패: {e}")
        raise HTTPException(status_code=502, detail=f"AI 분석 실패: {e} (Ollama 실행 중인지 확인: ollama serve)")

    return {
        "analysis": analysis_text,
        "precedents": [
            {
                "case_number": meta["case_number"],
                "court": meta["court"],
                "date": format_date(meta["date"]),
                "name": meta["name"],
                "link": absolutize(meta["link"]),
                "similarity": round(score, 3),
            }
            for meta, score in hits
        ],
    }


if __name__ == "__main__":
    import uvicorn
    print(f"✅ http://localhost:{PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")