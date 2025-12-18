# Technical Documentation - Smart Summarizer

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT (Browser)                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    React Frontend                        │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐              │    │
│  │  │ Text Tab │  │ PDF Tab  │  │ Chat UI  │              │    │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘              │    │
│  │       │             │             │                     │    │
│  │       └─────────────┴─────────────┘                     │    │
│  │                     │                                   │    │
│  │              ┌──────┴──────┐                            │    │
│  │              │   Axios     │                            │    │
│  │              │ HTTP Client │                            │    │
│  │              └──────┬──────┘                            │    │
│  └─────────────────────┼───────────────────────────────────┘    │
└────────────────────────┼────────────────────────────────────────┘
                         │ REST API (JSON)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     SERVER (localhost:5000)                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Flask Backend                         │    │
│  │                                                          │    │
│  │  ┌────────────────┐  ┌────────────────┐                 │    │
│  │  │  Summarization │  │   Q&A Engine   │                 │    │
│  │  │    Pipeline    │  │   (Flan-T5)    │                 │    │
│  │  │  (DistilBART)  │  │                │                 │    │
│  │  └───────┬────────┘  └───────┬────────┘                 │    │
│  │          │                   │                          │    │
│  │  ┌───────┴───────────────────┴────────┐                 │    │
│  │  │      Hugging Face Transformers     │                 │    │
│  │  └───────┬───────────────────┬────────┘                 │    │
│  │          │                   │                          │    │
│  │  ┌───────┴────────┐  ┌───────┴────────┐                 │    │
│  │  │    PyPDF2      │  │   ReportLab    │                 │    │
│  │  │ (PDF Extract)  │  │ (PDF Generate) │                 │    │
│  │  └────────────────┘  └────────────────┘                 │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Frontend (React)

#### State Management
```javascript
// Core application state
const [activeTab, setActiveTab] = useState('text');      // Tab navigation
const [text, setText] = useState('');                     // Input text
const [file, setFile] = useState(null);                   // PDF file
const [summary, setSummary] = useState('');               // Generated summary
const [chatHistory, setChatHistory] = useState([]);       // Q&A conversation
const [loading, setLoading] = useState(false);            // Loading state
const [progress, setProgress] = useState({...});          // Progress tracking
```

#### Progress Polling System
The frontend implements a polling mechanism to track backend progress:

```javascript
const startProgressPolling = () => {
  progressIntervalRef.current = setInterval(async () => {
    const response = await axios.get('/api/progress');
    setProgress(response.data);
    if (response.data.progress >= 100) {
      stopProgressPolling();
    }
  }, 300);  // Poll every 300ms
};
```

#### API Integration
- **Axios** configured with proxy to `localhost:5000`
- Multipart form data for PDF uploads
- JSON payloads for text summarization and Q&A

### 2. Backend (Flask)

#### Model Initialization
```python
# Summarization: DistilBART - 306M parameters
summarizer = pipeline(
    "summarization", 
    model="sshleifer/distilbart-cnn-12-6", 
    device=-1  # CPU
)

# Q&A: Flan-T5 Base - 250M parameters
qa_model = pipeline(
    "text2text-generation", 
    model="google/flan-t5-base", 
    device=-1  # CPU
)
```

#### Text Chunking Algorithm
Long documents are split into chunks that fit the model's token limit:

```python
def chunk_text(text, max_length=1024):
    tokenizer = AutoTokenizer.from_pretrained("sshleifer/distilbart-cnn-12-6")
    tokens = tokenizer.encode(text, truncation=False)
    
    chunks = []
    for i in range(0, len(tokens), max_length):
        chunk_tokens = tokens[i:i + max_length]
        chunk_text = tokenizer.decode(chunk_tokens, skip_special_tokens=True)
        chunks.append(chunk_text)
    
    return chunks
```

#### Summarization Pipeline

```
Input Text (N words)
        │
        ▼
┌───────────────────┐
│  Chunk Text       │  Split into 1024-token chunks
│  (if needed)      │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  Per-Chunk        │  Each chunk summarized independently
│  Summarization    │  Target: proportional to overall target
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  Combine          │  Join all chunk summaries
│  Summaries        │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  Final Pass       │  Re-summarize if over max length
│  (if needed)      │
└─────────┬─────────┘
          │
          ▼
    Output Summary
```

#### Length Control Parameters
```python
# Default calculations
max_length = min(1500, int(original_word_count * 0.5))  # 50% of input, max 1500
min_length = max(50, int(original_word_count * 0.25))   # 25% of input, min 50

# Token conversion (words → tokens)
max_tokens = int(max_length * 1.3)  # ~1.3 tokens per word
min_tokens = int(min_length * 1.3)

# Per-chunk allocation
chunk_max_tokens = max(150, int(max_tokens / total_chunks) + 50)
chunk_min_tokens = max(80, int(min_tokens / total_chunks))
```

### 3. Q&A System

#### Prompt Engineering
```python
prompt = f"""Answer the following question based on the document content provided. 
Give a detailed, helpful response.

Document Content:
{context}

Question: {question}

Answer:"""
```

#### Generation Parameters
```python
result = qa_model(
    prompt,
    max_new_tokens=150,    # Maximum response length
    do_sample=True,        # Enable sampling for diversity
    temperature=0.7,       # Creativity vs determinism balance
    top_p=0.9              # Nucleus sampling threshold
)
```

#### Context Management
- Original document stored in `last_content` dictionary
- Context truncated to 500 words for model input
- Conversation history maintained (last 20 messages)

## API Endpoints

### POST `/api/summarize-text`
**Request:**
```json
{
  "text": "Long text to summarize...",
  "max_words": 500,
  "min_words": 100
}
```

**Response:**
```json
{
  "summary": "Summarized text...",
  "original_length": 3952,
  "summary_length": 450
}
```

### POST `/api/summarize-pdf`
**Request:** `multipart/form-data`
- `file`: PDF file
- `max_words`: (optional) integer
- `min_words`: (optional) integer

**Response:** Same as `/api/summarize-text`

### POST `/api/answer-question`
**Request:**
```json
{
  "question": "What is the main topic?"
}
```

**Response:**
```json
{
  "answer": "The main topic is...",
  "history": [
    {"role": "user", "content": "What is the main topic?"},
    {"role": "assistant", "content": "The main topic is..."}
  ]
}
```

### GET `/api/progress`
**Response:**
```json
{
  "stage": "summarizing",
  "progress": 45,
  "message": "Summarizing chunk 2 of 4..."
}
```

### POST `/api/download-summary`
**Request:**
```json
{
  "summary": "Summary text to convert to PDF"
}
```

**Response:** Binary PDF file (`application/pdf`)

## Models Deep Dive

### DistilBART (Summarization)

| Property | Value |
|----------|-------|
| Model | `sshleifer/distilbart-cnn-12-6` |
| Architecture | Encoder-Decoder Transformer |
| Parameters | 306M |
| Trained On | CNN/DailyMail dataset |
| Max Input | 1024 tokens |
| Task | Abstractive Summarization |

**Why DistilBART?**
- 40% smaller than BART-large
- 2x faster inference
- Maintains 95% of BART's quality
- Optimized for news article summarization

### Flan-T5 (Question Answering)

| Property | Value |
|----------|-------|
| Model | `google/flan-t5-base` |
| Architecture | Encoder-Decoder T5 |
| Parameters | 250M |
| Trained On | 1800+ NLP tasks |
| Max Input | 512 tokens |
| Task | Text-to-Text Generation |

**Why Flan-T5?**
- Instruction-tuned for diverse tasks
- Generates natural, conversational responses
- Better than extractive QA for open-ended questions
- Handles follow-up questions well

## Performance Considerations

### Memory Usage
```
Idle:           ~200MB
Models Loaded:  ~2.5GB
Processing:     ~3-4GB peak
```

### Processing Time (Typical)
```
Text (500 words):    2-5 seconds
Text (3000 words):   15-30 seconds
PDF (10 pages):      20-45 seconds
Q&A Response:        3-8 seconds
```

### Optimization Strategies
1. **Chunking** - Process large documents in parallel-ready chunks
2. **CPU Inference** - `device=-1` for broader compatibility
3. **Caching** - Models cached after first download
4. **Progress Tracking** - Non-blocking progress updates

## Error Handling

### Backend Error Categories
```python
# Validation Errors (400)
- Empty/short text
- Invalid PDF file
- No content available for Q&A

# Processing Errors (500)
- Model inference failures
- PDF extraction failures
- Memory errors
```

### Frontend Error Display
```javascript
{error && (
  <div className="error-message">
    {error}
  </div>
)}
```

## Security Considerations

1. **No External APIs** - All processing local
2. **No Data Persistence** - Content cleared on restart
3. **CORS Configured** - Only allows configured origins
4. **File Validation** - Only PDF files accepted
5. **Input Sanitization** - Text length limits enforced

## Dependencies

### Backend (`requirements.txt`)
```
flask==3.0.0
flask-cors==4.0.0
transformers==4.36.0
torch==2.1.0
PyPDF2==3.0.1
reportlab==4.0.7
numpy<2.0
```

### Frontend (`package.json`)
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "axios": "^1.6.0"
  }
}
```

## Future Enhancements

1. **GPU Support** - CUDA acceleration for faster inference
2. **Model Selection** - Allow users to choose different models
3. **Batch Processing** - Multiple PDFs at once
4. **Export Formats** - DOCX, TXT, HTML exports
5. **Highlighting** - Show which parts of text contributed to summary
6. **Fine-tuning** - Domain-specific model adaptation
7. **WebSocket** - Real-time progress via WebSocket instead of polling
8. **Docker** - Containerized deployment
