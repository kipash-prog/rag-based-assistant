import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

const API_BASE = 'http://localhost:8000/api';

function App() {
  const [query, setQuery] = useState('');
  const [response, setResponse] = useState('');
  const [items, setItems] = useState([]);
  // Simplified: only Q&A flow
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const withLoading = async (fn) => {
    setLoading(true);
    try {
      await fn();
    } finally {
      setLoading(false);
    }
  };

  const handleQuerySubmit = async () => {
    await withLoading(async () => {
      try {
        setError('');
        const res = await axios.post(`${API_BASE}/query/`, { query });
        setResponse(res.data.response);
        setItems(res.data.items);
      } catch (e) {
        setError(e.response ? (e.response.data.error || 'Request failed') : e.message);
      }
    });
  };

  // Removed upload/management handlers for a pure Q&A interface

  return (
    <div className="app-root">
      <header className="app-header">
        <div className="container">
          <h1>Portfolio Assistant</h1>
          <p>Ask questions and manage your knowledge sources</p>
        </div>
      </header>

      <main className="container">
        {error && (
          <div className="toast toast-error">
            <span>{error}</span>
            <button className="toast-close" onClick={() => setError('')}>×</button>
          </div>
        )}

        <section className="card">
          <h2>Ask About My Portfolio</h2>
          <div className="form-row">
            <input
              className="input"
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask about projects, skills, experience..."
            />
            <button className="btn" onClick={handleQuerySubmit} disabled={loading}>
              {loading ? 'Thinking…' : 'Ask'}
            </button>
          </div>
          {response && (
            <div className="response-box">
              <h3>Response</h3>
              <p>{response}</p>
            </div>
          )}
        </section>

        {items && items.length > 0 && (
          <section className="card">
            <h2>Relevant Portfolio Items</h2>
            <div className="grid">
              {items.map((item, idx) => (
                <div key={idx} className="item-card">
                  <div className="item-card-header">
                    <h4 className="item-title">{item.title || 'Untitled'}</h4>
                    <span className={`badge badge-${item.source_type}`}>{item.source_type}</span>
                  </div>
                  <p className="item-snippet">{(item.content || '').substring(0, 300)}{(item.content || '').length > 300 ? '…' : ''}</p>
                  {item.source_url && (
                    <a
                      className="link"
                      href={item.source_url.startsWith('http') ? item.source_url : `http://localhost:8000/${item.source_url}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      View Source
                    </a>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Management sections removed for a focused Q&A experience */}
      </main>

      <footer className="app-footer">
        <div className="container">
          <span>© {new Date().getFullYear()} Portfolio Assistant</span>
        </div>
      </footer>
    </div>
  );
}

export default App;