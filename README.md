# soLAWtion 

사용자가 피해 상황을 입력하면 유사 판례를 자동으로 검색하고, 로컬 LLM이 판례를 분석하여 법률 참고 정보를 제공합니다.

---

## 시스템 구성

| 구성 요소 | 내용 |
|---|---|
| 백엔드 | FastAPI (Python) |
| LLM | Ollama - EXAONE 3.5 2.4b (로컬 추론) |
| 임베딩 | Ollama - bge-m3 (1024차원, 로컬) |
| 벡터 DB | SQLite (`precedents.db`) |
| 프론트엔드 | HTML/CSS/JS |
| 데이터 출처 | 법제처 국가법령정보 Open API |

---

## 파일 구조

```
solawtion/
├── README.md
├── .gitignore
├── requirements.txt
├── solawtion.py           # 백엔드 서버 (메인)
├── precedents.db          # 사전 구축된 판례 벡터 인덱스 (244건)
└── frontend/
    ├── index.html
    ├── templatemo-frost-style.css
    └── templatemo-frost-script.js
```

---

## 실행 방법

### 1. Ollama 설치 및 모델 다운로드

Ollama 설치 후:

```bash
ollama pull exaone3.5:2.4b # 판례 읽고 정리하는 LLM
ollama pull bge-m3         # 사용자 입력 임베딩
```

### 2. Ollama 서버 실행

```bash
ollama serve
```

### 3. Python 의존성 설치

```bash
pip install -r requirements.txt
```

### 4. 백엔드 서버 실행

```bash
python solawtion.py
```

### 5. ngrok으로 외부 노출 (별도 터미널)

```bash
ngrok http 8000
```

### 6. 프론트엔드 설정

`frontend/index.html` 557번째 줄의 `BACKEND_URL`을 본인 ngrok 주소로 변경:

```javascript
const BACKEND_URL = 'https://your-ngrok-url.ngrok-free.dev';
```

### 7. 프론트엔드 실행

`frontend/index.html`을 브라우저에서 열거나 로컬 서버로 서빙:

```bash
cd frontend
python -m http.server 3000
# 브라우저에서 http://localhost:3000 접속
```

---

### 8. 판례 검색

웹페이지에서 판례 검색 창에 사용자 상황 입력하면 판례와 요약본 찾아볼 수 있습니다.

