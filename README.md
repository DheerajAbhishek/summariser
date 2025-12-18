# Smart Summarizer

An AI-powered text and PDF summarization application with Q&A capabilities. Built with React frontend and Python Flask backend using local transformer models - **no API keys required**.

![Smart Summarizer](https://img.shields.io/badge/AI-Summarizer-667eea)
![Python](https://img.shields.io/badge/Python-3.8+-blue)
![React](https://img.shields.io/badge/React-18-61dafb)
![License](https://img.shields.io/badge/License-MIT-green)

## Features

- **Text Summarization** - Paste any text and get an abstractive summary
- **PDF Summarization** - Upload PDF files and extract summarized content
- **Q&A Chat Interface** - Ask questions about your content with ChatGPT-like responses
- **Customizable Length** - Control min/max words for summaries
- **Download as PDF** - Export your summaries as PDF files
- **Real-time Progress** - See processing progress with live updates
- **No API Keys** - Uses local SLM models (DistilBART & Flan-T5)

## Tech Stack

### Frontend
- React 18
- Axios for API calls
- Modern CSS with animations

### Backend
- Flask 3.0
- Transformers (Hugging Face)
- PyPDF2 for PDF extraction
- ReportLab for PDF generation

### AI Models
- **Summarization**: `sshleifer/distilbart-cnn-12-6` - Fast, efficient abstractive summarization
- **Q&A**: `google/flan-t5-base` - Generative question answering

## Installation

### Prerequisites
- Python 3.8+
- Node.js 16+
- npm or yarn

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
.\venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install
```

## Running the Application

### Start Backend Server

```bash
cd backend
.\venv\Scripts\activate  # Windows
python app.py
```

The backend will run on `http://localhost:5000`

### Start Frontend

```bash
cd frontend
npm start
```

The frontend will run on `http://localhost:3000`

## Usage

1. **Summarize Text**
   - Select the "Text Input" tab
   - Paste your text in the textarea
   - Optionally set min/max word limits
   - Click "Summarize Text"

2. **Summarize PDF**
   - Select the "PDF Upload" tab
   - Click to upload a PDF file
   - Optionally set min/max word limits
   - Click "Summarize PDF"

3. **Ask Questions**
   - After summarizing content, scroll to the Q&A section
   - Type your question in the chat input
   - Get detailed, contextual answers based on your document

4. **Download Summary**
   - Click "Download Summary as PDF" to export

## Project Structure

```
summariser/
├── backend/
│   ├── app.py              # Flask server & API endpoints
│   ├── requirements.txt    # Python dependencies
│   └── venv/               # Virtual environment
├── frontend/
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── App.js          # Main React component
│   │   ├── App.css         # Styles
│   │   └── index.js        # Entry point
│   └── package.json
└── README.md
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/summarize-text` | POST | Summarize text content |
| `/api/summarize-pdf` | POST | Summarize PDF file |
| `/api/answer-question` | POST | Answer questions about content |
| `/api/download-summary` | POST | Generate PDF download |
| `/api/clear-chat` | POST | Clear conversation history |
| `/api/progress` | GET | Get processing progress |
| `/api/health` | GET | Health check |

## Configuration

### Word Count Settings
- **Min Words**: Minimum words in summary (default: 25% of input)
- **Max Words**: Maximum words in summary (default: 50% of input, capped at 1500)

## Troubleshooting

### "Numpy is not available" Error
```bash
cd backend
.\venv\Scripts\pip.exe install --force-reinstall "numpy<2.0"
```

### Models Taking Too Long to Load
First run downloads models (~500MB). Subsequent runs use cached models.

### Port Already in Use
Change port in `app.py` or kill existing process:
```bash
# Windows
netstat -ano | findstr :5000
taskkill /PID <PID> /F
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License.

## Acknowledgments

- [Hugging Face Transformers](https://huggingface.co/transformers/)
- [DistilBART](https://huggingface.co/sshleifer/distilbart-cnn-12-6)
- [Flan-T5](https://huggingface.co/google/flan-t5-base)
