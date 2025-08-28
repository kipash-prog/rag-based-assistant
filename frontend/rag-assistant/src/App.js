import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [query, setQuery] = useState('');
  const [response, setResponse] = useState('');
  const [items, setItems] = useState([]);
  const [file, setFile] = useState(null);
  const [url, setUrl] = useState('');
  const [title, setTitle] = useState('');
  const [sourceType, setSourceType] = useState('website');
  const [filename, setFilename] = useState('');
  const [error, setError] = useState('');

  const handleQuerySubmit = async () => {
    try {
      setError('');
      const res = await axios.post('http://localhost:8000/api/query/', { query });
      setResponse(res.data.response);
      setItems(res.data.items);
    } catch (error) {
      setError(error.response ? error.response.data.error : error.message);
    }
  };

  const handlePDFUpload = async () => {
    try {
      setError('');
      const formData = new FormData();
      formData.append('file', file);
      formData.append('title', title);
      formData.append('metadata', JSON.stringify({ About_me: file.name }));
      const res = await axios.post('http://localhost:8000/api/upload-pdf/', formData);
      alert(res.data.message);
    } catch (error) {
      setError(error.response ? error.response.data.error : error.message);
    }
  };

  const handleWebContentSubmit = async () => {
    try {
      setError('');
      const res = await axios.post('http://localhost:8000/api/add-web-content/', {
        url,
        title,
        source_type: sourceType,
        metadata: { platform: sourceType === 'social_media' ? 'Social Media' : 'Website' }
      });
      alert(res.data.message);
    } catch (error) {
      setError(error.response ? error.response.data.error : error.message);
    }
  };

  const handleExistingPDFSubmit = async () => {
    try {
      setError('');
      const res = await axios.post('http://localhost:8000/api/add-existing-pdf/', {
        filename,
        title,
        metadata: { About_me: filename }
      });
      alert(res.data.message);
    } catch (error) {
      setError(error.response ? error.response.data.error : error.message);
    }
  };

  return (
    <div className="App">
      <h1>My Portfolio Assistant</h1>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      <h2>Ask About My Portfolio</h2>
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Ask about my work..."
      />
      <button onClick={handleQuerySubmit}>Ask</button>
      <h3>Response</h3>
      <p>{response}</p>
      <h3>Relevant Portfolio Items</h3>
      <ul>
        {items.map((item, index) => (
          <li key={index}>
            <strong>{item.title}</strong> ({item.source_type}):
            <p>{item.content.substring(0, 200)}...</p>
            {item.source_url && (
              <a href={item.source_url.startsWith('http') ? item.source_url : `http://localhost:8000/${item.source_url}`} 
                 target="_blank" 
                 rel="noopener noreferrer">
                View Source
              </a>
            )}
          </li>
        ))}
      </ul>

      <h2>Upload PDF</h2>
      <input
        type="text"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="PDF Title"
      />
      <input type="file" accept=".pdf" onChange={(e) => setFile(e.target.files[0])} />
      <button onClick={handlePDFUpload}>Upload PDF</button>

      <h2>Add Existing PDF</h2>
      <input
        type="text"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="PDF Title"
      />
      <input
        type="text"
        value={filename}
        onChange={(e) => setFilename(e.target.value)}
        placeholder="PDF Filename (e.g., AboutMe.pdf)"
      />
      <button onClick={handleExistingPDFSubmit}>Add Existing PDF</button>

      <h2>Add Web Content</h2>
      <input
        type="text"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Content Title"
      />
      <input
        type="text"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="Enter URL (e.g., LinkedIn or website)"
      />
      <select value={sourceType} onChange={(e) => setSourceType(e.target.value)}>
        <option value="website">Website</option>
        <option value="social_media">Social Media</option>
      </select>
      <button onClick={handleWebContentSubmit}>Add Web Content</button>
    </div>
  );
}

export default App;