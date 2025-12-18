import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import './App.css';

function App() {
    const [activeTab, setActiveTab] = useState('text');
    const [text, setText] = useState('');
    const [file, setFile] = useState(null);
    const [summary, setSummary] = useState('');
    const [question, setQuestion] = useState('');
    const [chatHistory, setChatHistory] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [stats, setStats] = useState(null);
    const [maxWords, setMaxWords] = useState('');
    const [minWords, setMinWords] = useState('');
    const [progress, setProgress] = useState({ stage: '', progress: 0, message: '' });
    const chatEndRef = useRef(null);
    const progressIntervalRef = useRef(null);

    // Scroll to bottom of chat
    const scrollToBottom = () => {
        chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [chatHistory]);

    // Start polling for progress
    const startProgressPolling = () => {
        setProgress({ stage: '', progress: 0, message: 'Starting...' });
        progressIntervalRef.current = setInterval(async () => {
            try {
                const response = await axios.get('/api/progress');
                setProgress(response.data);
                if (response.data.progress >= 100) {
                    stopProgressPolling();
                }
            } catch (err) {
                console.error('Error fetching progress:', err);
            }
        }, 300);
    };

    // Stop polling for progress
    const stopProgressPolling = () => {
        if (progressIntervalRef.current) {
            clearInterval(progressIntervalRef.current);
            progressIntervalRef.current = null;
        }
    };

    // Cleanup on unmount
    useEffect(() => {
        return () => stopProgressPolling();
    }, []);

    const handleTextSummarize = async () => {
        if (!text.trim()) {
            setError('Please enter some text to summarize');
            return;
        }

        setLoading(true);
        setError('');
        setSummary('');
        setStats(null);
        startProgressPolling();

        try {
            const response = await axios.post('/api/summarize-text', {
                text,
                max_words: maxWords || null,
                min_words: minWords || null
            });
            setSummary(response.data.summary);
            setStats({
                original: response.data.original_length,
                summary: response.data.summary_length
            });
        } catch (err) {
            setError(err.response?.data?.error || 'Error summarizing text');
        } finally {
            stopProgressPolling();
            setProgress({ stage: '', progress: 0, message: '' });
            setLoading(false);
        }
    };

    const handlePdfSummarize = async () => {
        if (!file) {
            setError('Please select a PDF file');
            return;
        }

        setLoading(true);
        setError('');
        setSummary('');
        setStats(null);
        startProgressPolling();

        const formData = new FormData();
        formData.append('file', file);
        if (maxWords) formData.append('max_words', maxWords);
        if (minWords) formData.append('min_words', minWords);

        try {
            const response = await axios.post('/api/summarize-pdf', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            });
            setSummary(response.data.summary);
            setStats({
                original: response.data.original_length,
                summary: response.data.summary_length
            });
        } catch (err) {
            setError(err.response?.data?.error || 'Error summarizing PDF');
        } finally {
            stopProgressPolling();
            setProgress({ stage: '', progress: 0, message: '' });
            setLoading(false);
        }
    };

    const handleAskQuestion = async () => {
        if (!question.trim()) {
            setError('Please enter a question');
            return;
        }

        if (!summary) {
            setError('Please summarize some content first');
            return;
        }

        const userQuestion = question;
        setQuestion('');
        setLoading(true);
        setError('');
        startProgressPolling();

        // Add user message immediately
        setChatHistory(prev => [...prev, { role: 'user', content: userQuestion }]);

        try {
            const response = await axios.post('/api/answer-question', { question: userQuestion });
            // Add assistant response
            setChatHistory(prev => [...prev, { role: 'assistant', content: response.data.answer }]);
        } catch (err) {
            setError(err.response?.data?.error || 'Error answering question');
            // Remove the user question if there was an error
            setChatHistory(prev => prev.slice(0, -1));
        } finally {
            stopProgressPolling();
            setProgress({ stage: '', progress: 0, message: '' });
            setLoading(false);
        }
    };

    const handleClearChat = async () => {
        try {
            await axios.post('/api/clear-chat');
            setChatHistory([]);
        } catch (err) {
            console.error('Error clearing chat:', err);
        }
    };

    const handleDownloadPdf = async () => {
        if (!summary) {
            setError('No summary to download');
            return;
        }

        try {
            const response = await axios.post('/api/download-summary',
                { summary },
                { responseType: 'blob' }
            );

            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', 'summary.pdf');
            document.body.appendChild(link);
            link.click();
            link.remove();
        } catch (err) {
            setError('Error downloading PDF');
        }
    };

    const handleFileChange = (e) => {
        const selectedFile = e.target.files[0];
        if (selectedFile && selectedFile.type === 'application/pdf') {
            setFile(selectedFile);
            setError('');
        } else {
            setFile(null);
            setError('Please select a valid PDF file');
        }
    };

    return (
        <div className="App">
            <div className="container">
                <header className="header">
                    <h1>Smart Summarizer</h1>
                    <p>AI-powered text and PDF summarization with Q&A</p>
                </header>

                <div className="tabs">
                    <button
                        className={`tab ${activeTab === 'text' ? 'active' : ''}`}
                        onClick={() => setActiveTab('text')}
                    >
                        Text Input
                    </button>
                    <button
                        className={`tab ${activeTab === 'pdf' ? 'active' : ''}`}
                        onClick={() => setActiveTab('pdf')}
                    >
                        PDF Upload
                    </button>
                </div>

                <div className="content">
                    {activeTab === 'text' ? (
                        <div className="input-section">
                            <textarea
                                className="text-input"
                                placeholder="Paste your text here..."
                                value={text}
                                onChange={(e) => setText(e.target.value)}
                                rows={10}
                            />
                            <div className="word-count-info">
                                {text.trim() && (
                                    <span className="word-count-badge">
                                        Input: {text.trim().split(/\s+/).length} words
                                    </span>
                                )}
                            </div>
                            <div className="word-controls">
                                <div className="word-control-group">
                                    <label htmlFor="min-words">Min Words (default: 25% of input):</label>
                                    <input
                                        id="min-words"
                                        type="number"
                                        min="20"
                                        max="1000"
                                        value={minWords}
                                        onChange={(e) => setMinWords(e.target.value)}
                                        placeholder="Auto"
                                        className="word-input"
                                    />
                                </div>
                                <div className="word-control-group">
                                    <label htmlFor="max-words">Max Words (default: 50% of input):</label>
                                    <input
                                        id="max-words"
                                        type="number"
                                        min="50"
                                        max="1000"
                                        value={maxWords}
                                        onChange={(e) => setMaxWords(e.target.value)}
                                        placeholder="Auto"
                                        className="word-input"
                                    />
                                </div>
                            </div>
                            <button
                                className="btn btn-primary"
                                onClick={handleTextSummarize}
                                disabled={loading}
                            >
                                {loading ? 'Summarizing...' : 'Summarize Text'}
                            </button>
                            {loading && progress.message && (
                                <div className="progress-container">
                                    <div className="progress-bar">
                                        <div
                                            className="progress-fill"
                                            style={{ width: `${progress.progress}%` }}
                                        ></div>
                                    </div>
                                    <div className="progress-text">
                                        <span>{progress.message}</span>
                                        <span>{progress.progress}%</span>
                                    </div>
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="input-section">
                            <div className="file-input-wrapper">
                                <input
                                    type="file"
                                    id="pdf-input"
                                    accept=".pdf"
                                    onChange={handleFileChange}
                                    className="file-input"
                                />
                                <label htmlFor="pdf-input" className="file-label">
                                    {file ? file.name : 'Choose PDF file'}
                                </label>
                            </div>
                            <div className="word-controls">
                                <div className="word-control-group">
                                    <label htmlFor="min-words-pdf">Min Words (default: 25% of input):</label>
                                    <input
                                        id="min-words-pdf"
                                        type="number"
                                        min="20"
                                        max="1000"
                                        value={minWords}
                                        onChange={(e) => setMinWords(e.target.value)}
                                        placeholder="Auto"
                                        className="word-input"
                                    />
                                </div>
                                <div className="word-control-group">
                                    <label htmlFor="max-words-pdf">Max Words (default: 50% of input):</label>
                                    <input
                                        id="max-words-pdf"
                                        type="number"
                                        min="50"
                                        max="1000"
                                        value={maxWords}
                                        onChange={(e) => setMaxWords(e.target.value)}
                                        placeholder="Auto"
                                        className="word-input"
                                    />
                                </div>
                            </div>
                            <button
                                className="btn btn-primary"
                                onClick={handlePdfSummarize}
                                disabled={loading || !file}
                            >
                                {loading ? 'Summarizing...' : 'Summarize PDF'}
                            </button>
                            {loading && progress.message && (
                                <div className="progress-container">
                                    <div className="progress-bar">
                                        <div
                                            className="progress-fill"
                                            style={{ width: `${progress.progress}%` }}
                                        ></div>
                                    </div>
                                    <div className="progress-text">
                                        <span>{progress.message}</span>
                                        <span>{progress.progress}%</span>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {error && (
                        <div className="error-message">
                            {error}
                        </div>
                    )}

                    {summary && (
                        <div className="result-section">
                            <div className="result-header">
                                <h2>Summary</h2>
                                {stats && (
                                    <span className="stats">
                                        {stats.original} words → {stats.summary} words
                                        ({Math.round((stats.summary / stats.original) * 100)}% of original)
                                    </span>
                                )}
                            </div>
                            <div className="summary-box">
                                {summary}
                            </div>
                            <button
                                className="btn btn-secondary"
                                onClick={handleDownloadPdf}
                            >
                                Download as PDF
                            </button>
                        </div>
                    )}

                    {summary && (
                        <div className="chat-section">
                            <div className="chat-header">
                                <h2>Chat with your Document</h2>
                                {chatHistory.length > 0 && (
                                    <button className="btn-clear" onClick={handleClearChat}>
                                        Clear Chat
                                    </button>
                                )}
                            </div>

                            <div className="chat-container">
                                {chatHistory.length === 0 ? (
                                    <div className="chat-empty">
                                        <p>Ask me anything about the document!</p>
                                        <p className="chat-hint">I'll provide detailed answers based on the content you summarized.</p>
                                    </div>
                                ) : (
                                    <div className="chat-messages">
                                        {chatHistory.map((msg, index) => (
                                            <div key={index} className={`chat-message ${msg.role}`}>
                                                <div className="message-avatar">
                                                    {msg.role === 'user' ? 'U' : 'A'}
                                                </div>
                                                <div className="message-content">
                                                    <div className="message-role">
                                                        {msg.role === 'user' ? 'You' : 'Assistant'}
                                                    </div>
                                                    <div className="message-text">{msg.content}</div>
                                                </div>
                                            </div>
                                        ))}
                                        {loading && (
                                            <div className="chat-message assistant">
                                                <div className="message-avatar">A</div>
                                                <div className="message-content">
                                                    <div className="message-role">Assistant</div>
                                                    <div className="message-text typing">
                                                        <span className="dot"></span>
                                                        <span className="dot"></span>
                                                        <span className="dot"></span>
                                                    </div>
                                                    {progress.message && (
                                                        <div className="typing-status">{progress.message}</div>
                                                    )}
                                                </div>
                                            </div>
                                        )}
                                        <div ref={chatEndRef} />
                                    </div>
                                )}
                            </div>

                            <div className="chat-input-container">
                                <input
                                    type="text"
                                    className="chat-input"
                                    placeholder="Type your question..."
                                    value={question}
                                    onChange={(e) => setQuestion(e.target.value)}
                                    onKeyPress={(e) => e.key === 'Enter' && !loading && handleAskQuestion()}
                                    disabled={loading}
                                />
                                <button
                                    className="btn-send"
                                    onClick={handleAskQuestion}
                                    disabled={loading || !question.trim()}
                                >
                                    {loading ? '...' : 'Send'}
                                </button>
                            </div>
                        </div>
                    )}
                </div>

                <footer className="footer">
                    <p>Powered by Transformers (DistilBART + Flan-T5) • No API keys required</p>
                </footer>
            </div>
        </div>
    );
}

export default App;
