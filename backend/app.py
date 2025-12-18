from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
import PyPDF2
import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import torch
import os
import warnings
import numpy as np
import json
import time

# Suppress warnings
warnings.filterwarnings('ignore')

print(f"Numpy available: {np.__version__}")

app = Flask(__name__)
CORS(app)

# Progress tracking
progress_status = {
    "stage": "",
    "progress": 0,
    "message": ""
}

def update_progress(stage, progress, message):
    """Update global progress status"""
    global progress_status
    progress_status["stage"] = stage
    progress_status["progress"] = progress
    progress_status["message"] = message

# Initialize models - using smaller models that don't require API keys
print("Loading models... This may take a few minutes on first run.")

try:
    # Summarization model - using DistilBART (smaller, faster)
    summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6", device=-1)
    
    # Question Answering model - use Flan-T5 for generative answers (more ChatGPT-like)
    print("Loading Q&A model (Flan-T5)...")
    qa_model = pipeline(
        "text2text-generation", 
        model="google/flan-t5-base", 
        device=-1
    )
    
    print("Models loaded successfully!")
except Exception as e:
    print(f"Error loading models: {str(e)}")
    print("Please ensure all dependencies are installed: pip install -r requirements.txt")

# Store the last processed content for Q&A
last_content = {"text": "", "summary": ""}

# Store conversation history
conversation_history = []


def extract_text_from_pdf(pdf_file):
    """Extract text from PDF file"""
    try:
        update_progress("extracting", 5, "Extracting text from PDF...")
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        total_pages = len(pdf_reader.pages)
        for i, page in enumerate(pdf_reader.pages):
            text += page.extract_text() + "\n"
            # Update progress during extraction (5-15% range)
            extract_progress = 5 + int((i / total_pages) * 10)
            update_progress("extracting", extract_progress, f"Extracting page {i+1} of {total_pages}...")
        return text.strip()
    except Exception as e:
        raise Exception(f"Error extracting PDF text: {str(e)}")


def chunk_text(text, max_length=1024):
    """Split text into chunks that fit model's max token length"""
    tokenizer = AutoTokenizer.from_pretrained("sshleifer/distilbart-cnn-12-6")
    tokens = tokenizer.encode(text, truncation=False)
    
    chunks = []
    for i in range(0, len(tokens), max_length):
        chunk_tokens = tokens[i:i + max_length]
        chunk_text = tokenizer.decode(chunk_tokens, skip_special_tokens=True)
        chunks.append(chunk_text)
    
    return chunks


def summarize_long_text(text, max_length=None, min_length=None):
    """Summarize text, handling long documents by chunking"""
    update_progress("init", 5, "Analyzing text...")
    
    original_word_count = len(text.split())
    
    if original_word_count < 50:
        return "Text is too short to summarize meaningfully."
    
    # Ensure max_length and min_length are integers or None
    if max_length is not None:
        max_length = int(max_length)
    if min_length is not None:
        min_length = int(min_length)
    
    # Calculate smart defaults based on original text length
    if max_length is None:
        # Max = 50% of original, capped at 1500 words for long docs
        max_length = min(1500, int(original_word_count * 0.5))
    
    if min_length is None:
        # Min = 25% of original (matching the UI label)
        min_length = max(50, int(original_word_count * 0.25))
    
    # Ensure min doesn't exceed max
    min_length = min(min_length, int(max_length * 0.9))
    
    # Convert word counts to approximate token counts (tokens are ~1.3x words)
    max_tokens = int(max_length * 1.3)
    min_tokens = int(min_length * 1.3)
    
    print(f"Target summary: {min_length}-{max_length} words (from {original_word_count} words)")
    
    update_progress("chunking", 10, "Splitting text into chunks...")
    
    # Chunk the text if it's too long
    chunks = chunk_text(text, max_length=1024)
    total_chunks = len(chunks)
    
    # Calculate per-chunk target lengths to achieve overall target
    # Each chunk should contribute proportionally to the final summary
    chunk_max_tokens = max(150, int(max_tokens / total_chunks) + 50)  # Add buffer for combination
    chunk_min_tokens = max(80, int(min_tokens / total_chunks))
    
    # Ensure reasonable bounds
    chunk_min_tokens = min(chunk_min_tokens, int(chunk_max_tokens * 0.7))
    
    print(f"Chunks: {total_chunks}, Per-chunk target: {chunk_min_tokens}-{chunk_max_tokens} tokens")
    
    update_progress("summarizing", 15, f"Processing {total_chunks} chunk(s)...")
    
    summaries = []
    for i, chunk in enumerate(chunks):
        try:
            # Update progress for each chunk
            chunk_progress = 15 + int((i / total_chunks) * 70)
            update_progress("summarizing", chunk_progress, f"Summarizing chunk {i+1} of {total_chunks}...")
            
            chunk_words = len(chunk.split())
            
            if chunk_words > 30:  # Only summarize if chunk has enough content
                summary = summarizer(
                    chunk,
                    max_length=chunk_max_tokens,
                    min_length=chunk_min_tokens,
                    do_sample=False,
                    length_penalty=1.5,  # Encourage longer outputs
                    num_beams=4
                )
                summaries.append(summary[0]['summary_text'])
        except Exception as e:
            print(f"Error summarizing chunk: {str(e)}")
            continue
    
    update_progress("combining", 90, "Combining summaries...")
    
    # If we have multiple summaries, combine them
    if len(summaries) > 1:
        combined = " ".join(summaries)
        combined_word_count = len(combined.split())
        
        print(f"Combined summary: {combined_word_count} words (target: {min_length}-{max_length})")
        
        # Only re-summarize if combined is significantly longer than max
        if combined_word_count > max_length * 1.2:
            try:
                update_progress("finalizing", 95, "Creating final summary...")
                final_summary = summarizer(
                    combined,
                    max_length=max_tokens,
                    min_length=min_tokens,
                    do_sample=False,
                    length_penalty=1.5,
                    num_beams=4
                )
                update_progress("complete", 100, "Summary complete!")
                return final_summary[0]['summary_text']
            except Exception as e:
                print(f"Error in final summarization: {str(e)}")
                update_progress("complete", 100, "Summary complete!")
                return combined
        update_progress("complete", 100, "Summary complete!")
        return combined
    elif len(summaries) == 1:
        # Check if single summary meets length requirements
        summary_words = len(summaries[0].split())
        
        print(f"Single summary: {summary_words} words (target: {min_length}-{max_length})")
        
        # If summary is too short and we want it longer, try again with adjusted params
        if summary_words < min_length * 0.8 and original_word_count > min_length * 2:
            try:
                update_progress("finalizing", 95, "Optimizing summary length...")
                # Force longer summary with higher length penalty
                longer_summary = summarizer(
                    text[:10000],  # Limit to avoid token issues
                    max_length=max_tokens,
                    min_length=min_tokens,
                    do_sample=False,
                    length_penalty=2.5,
                    num_beams=6
                )
                update_progress("complete", 100, "Summary complete!")
                return longer_summary[0]['summary_text']
            except Exception as e:
                print(f"Error extending summary: {str(e)}")
                pass
        
        update_progress("complete", 100, "Summary complete!")
        return summaries[0]
    else:
        update_progress("error", 100, "Unable to generate summary")
        return "Unable to generate summary."


def create_pdf(text, filename="summary.pdf"):
    """Create a PDF file from text"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                           rightMargin=72, leftMargin=72,
                           topMargin=72, bottomMargin=18)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Justify', alignment=4))  # Justified
    
    # Add title
    title_style = styles['Heading1']
    elements.append(Paragraph("Content Summary", title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Add content
    content_style = styles['Justify']
    
    # Split text into paragraphs
    paragraphs = text.split('\n')
    for para in paragraphs:
        if para.strip():
            elements.append(Paragraph(para, content_style))
            elements.append(Spacer(1, 0.1*inch))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer


@app.route('/api/summarize-text', methods=['POST'])
def summarize_text():
    """Summarize text provided directly"""
    try:
        data = request.json
        text = data.get('text', '')
        max_words = data.get('max_words', None)
        min_words = data.get('min_words', None)
        
        if not text or len(text.strip()) < 10:
            return jsonify({'error': 'Please provide valid text (at least 10 characters)'}), 400
        
        # Generate summary
        summary = summarize_long_text(text, max_length=max_words, min_length=min_words)
        
        # Store for Q&A
        last_content['text'] = text
        last_content['summary'] = summary
        
        return jsonify({
            'summary': summary,
            'original_length': len(text.split()),
            'summary_length': len(summary.split())
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/summarize-pdf', methods=['POST'])
def summarize_pdf():
    """Summarize PDF file"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        max_words = request.form.get('max_words', None)
        min_words = request.form.get('min_words', None)
        
        # Convert to int if provided
        if max_words:
            max_words = int(max_words)
        if min_words:
            min_words = int(min_words)
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.endswith('.pdf'):
            return jsonify({'error': 'Only PDF files are supported'}), 400
        
        # Extract text from PDF
        text = extract_text_from_pdf(file)
        
        if not text or len(text.strip()) < 10:
            return jsonify({'error': 'Could not extract text from PDF or PDF is empty'}), 400
        
        # Generate summary
        summary = summarize_long_text(text, max_length=max_words, min_length=min_words)
        
        # Store for Q&A
        last_content['text'] = text
        last_content['summary'] = summary
        
        return jsonify({
            'summary': summary,
            'original_length': len(text.split()),
            'summary_length': len(summary.split())
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/answer-question', methods=['POST'])
def answer_question():
    """Answer questions based on the last processed content using generative model"""
    global conversation_history
    
    try:
        data = request.json
        question = data.get('question', '')
        
        if not question:
            return jsonify({'error': 'Please provide a question'}), 400
        
        if not last_content['text']:
            return jsonify({'error': 'No content available. Please summarize text or upload a PDF first before asking questions.'}), 400
        
        update_progress("qa_processing", 20, "Processing your question...")
        print(f"Processing question: {question}")
        
        # Use the original text for context
        context = last_content['text']
        
        # Limit context length
        words = context.split()
        if len(words) > 500:
            context = ' '.join(words[:500])
        
        update_progress("qa_generating", 50, "Generating response...")
        
        # Build a prompt that encourages detailed, helpful responses
        prompt = f"""Answer the following question based on the document content provided. Give a detailed, helpful response.

Document Content:
{context}

Question: {question}

Answer:"""
        
        try:
            # Generate response using Flan-T5
            result = qa_model(
                prompt,
                max_new_tokens=150,
                do_sample=True,
                temperature=0.7,
                top_p=0.9
            )
            
            answer = result[0]['generated_text'].strip()
            
            update_progress("qa_complete", 100, "Response ready!")
            
            # If answer is empty, provide fallback
            if not answer:
                answer = "I couldn't find a specific answer in the document. Please try rephrasing your question."
            
            # Add to conversation history
            conversation_history.append({
                'role': 'user',
                'content': question
            })
            conversation_history.append({
                'role': 'assistant',
                'content': answer
            })
            
            # Keep only last 20 messages
            if len(conversation_history) > 20:
                conversation_history = conversation_history[-20:]
            
            print(f"Generated answer: {answer}")
            
            return jsonify({
                'answer': answer,
                'history': conversation_history
            })
            
        except Exception as qa_error:
            print(f"QA model error: {str(qa_error)}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
            
            return jsonify({
                'answer': 'I apologize, but I was unable to generate a response. Please try rephrasing your question.',
                'history': conversation_history
            })
    
    except Exception as e:
        print(f"Error in answer_question: {str(e)}")
        return jsonify({'error': f'Error processing question: {str(e)}'}), 500


@app.route('/api/clear-chat', methods=['POST'])
def clear_chat():
    """Clear conversation history"""
    global conversation_history
    conversation_history = []
    return jsonify({'message': 'Chat history cleared', 'history': []})


@app.route('/api/get-chat-history', methods=['GET'])
def get_chat_history():
    """Get current conversation history"""
    return jsonify({'history': conversation_history})


@app.route('/api/download-summary', methods=['POST'])
def download_summary():
    """Generate and download summary as PDF"""
    try:
        data = request.json
        summary = data.get('summary', '')
        
        if not summary:
            return jsonify({'error': 'No summary provided'}), 400
        
        # Create PDF
        pdf_buffer = create_pdf(summary)
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='summary.pdf'
        )
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'models_loaded': True})


@app.route('/api/progress', methods=['GET'])
def get_progress():
    """Get current processing progress"""
    return jsonify(progress_status)


@app.route('/api/progress-stream')
def progress_stream():
    """Stream progress updates using Server-Sent Events"""
    def generate():
        last_progress = -1
        while True:
            if progress_status['progress'] != last_progress:
                last_progress = progress_status['progress']
                data = json.dumps(progress_status)
                yield f"data: {data}\n\n"
            if progress_status['progress'] >= 100:
                break
            time.sleep(0.2)
    
    return Response(generate(), mimetype='text/event-stream')


if __name__ == '__main__':
    app.run(debug=True, port=5000)
