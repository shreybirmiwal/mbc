import React, { useState, useEffect } from 'react';
import './App.css';

const API_BASE_URL = 'http://localhost:5000';

function App() {
  const [apis, setApis] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [apiDetails, setApiDetails] = useState({});

  useEffect(() => {
    fetchApis();
  }, []);

  const fetchApis = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/admin/list-apis`);
      const data = await response.json();
      const apisList = data.apis || [];
      setApis(apisList);

      // Fetch detailed info for each API
      const detailsPromises = apisList.map(async (api) => {
        if (api.token?.address) {
          try {
            const endpoint = api.endpoint.replace(/^\//, ''); // Remove leading slash
            const infoResponse = await fetch(`${API_BASE_URL}/admin/api-info/${endpoint}`);
            if (infoResponse.ok) {
              const info = await infoResponse.json();
              return { endpoint: api.endpoint, info };
            }
          } catch (error) {
            console.error(`Error fetching info for ${api.endpoint}:`, error);
          }
        }
        return { endpoint: api.endpoint, info: null };
      });

      const details = await Promise.all(detailsPromises);
      const detailsMap = {};
      details.forEach(({ endpoint, info }) => {
        detailsMap[endpoint] = info;
      });
      setApiDetails(detailsMap);
    } catch (error) {
      console.error('Error fetching APIs:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateAPI = async (formData) => {
    try {
      const response = await fetch(`${API_BASE_URL}/admin/create-api`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });

      if (response.ok) {
        const result = await response.json();
        alert('API created successfully!');
        setShowCreateForm(false);
        fetchApis(); // Refresh the list
      } else {
        const error = await response.json();
        alert(`Error: ${error.error || 'Failed to create API'}`);
      }
    } catch (error) {
      console.error('Error creating API:', error);
      alert('Error creating API. Please try again.');
    }
  };

  if (loading) {
    return <div className="loading">Loading APIs...</div>;
  }

  return (
    <div className="app">
      <header className="header">
        <h1>API Marketplace</h1>
        <p>Token-based API access powered by x402 & Flaunch</p>
        <button
          className="create-button"
          onClick={() => setShowCreateForm(!showCreateForm)}
        >
          {showCreateForm ? 'Cancel' : '+ Create New API'}
        </button>
      </header>

      {showCreateForm && (
        <CreateAPIForm
          onSubmit={handleCreateAPI}
          onCancel={() => setShowCreateForm(false)}
        />
      )}

      <div className="apis-container">
        {apis.length === 0 ? (
          <div className="empty-state">
            <p>No APIs available. Create your first API!</p>
          </div>
        ) : (
          apis.map((api) => (
            <APICard
              key={api.endpoint}
              api={api}
              details={apiDetails[api.endpoint]}
            />
          ))
        )}
      </div>
    </div>
  );
}

function APICard({ api, details }) {
  const [expanded, setExpanded] = useState(false);
  const apiUrl = `${API_BASE_URL}${api.endpoint}`;
  const flaunchLink = api.token?.view_on_flaunch || details?.links?.flaunch;

  return (
    <div className="api-card">
      <div className="api-card-header">
        <div>
          <h2>{api.name}</h2>
          <p className="api-endpoint">{api.endpoint}</p>
          <p className="api-description">{api.description || 'No description'}</p>
        </div>
        <div className="api-status">
          <span className={`status-badge ${api.status}`}>
            {api.status}
          </span>
        </div>
      </div>

      {api.token && (
        <div className="api-token-info">
          <div className="token-details">
            <span className="token-symbol">{api.token.symbol}</span>
            {api.token.price_eth && (
              <span className="token-price">
                {parseFloat(api.token.price_eth).toFixed(8)} ETH
              </span>
            )}
          </div>
        </div>
      )}

      <div className="api-links">
        <a
          href={apiUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="link-button"
        >
          🔗 API Endpoint (x402)
        </a>
        {flaunchLink && (
          <a
            href={flaunchLink}
            target="_blank"
            rel="noopener noreferrer"
            className="link-button"
          >
            📊 View on Flaunch
          </a>
        )}
        <button
          className="toggle-button"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? '▼ Hide' : '▶ Show'} Price History
        </button>
      </div>

      {expanded && details && (
        <div className="price-history-section">
          <PriceChart priceHistory={details.price_history} />
          <div className="price-stats">
            {details.current_price && (
              <>
                <div className="stat">
                  <label>Current Price:</label>
                  <span>{parseFloat(details.current_price.price_eth || 0).toFixed(8)} ETH</span>
                </div>
                {details.current_price.price_change_24h_percentage !== undefined && (
                  <div className="stat">
                    <label>24h Change:</label>
                    <span className={details.current_price.price_change_24h_percentage >= 0 ? 'positive' : 'negative'}>
                      {details.current_price.price_change_24h_percentage.toFixed(2)}%
                    </span>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function PriceChart({ priceHistory }) {
  if (!priceHistory) {
    return <div className="no-chart-data">No price history available</div>;
  }

  // Use hourly data if available, otherwise daily, then minutely
  let chartData = [];
  if (priceHistory.hourly && priceHistory.hourly.length > 0) {
    chartData = priceHistory.hourly.slice(-24).map((point, index) => ({
      time: index,
      price: parseFloat(point.price || point.priceETH || 0),
      timestamp: point.timestamp || point.time || index
    }));
  } else if (priceHistory.daily && priceHistory.daily.length > 0) {
    chartData = priceHistory.daily.slice(-30).map((point, index) => ({
      time: index,
      price: parseFloat(point.price || point.priceETH || 0),
      timestamp: point.timestamp || point.time || index
    }));
  } else if (priceHistory.minutely && priceHistory.minutely.length > 0) {
    chartData = priceHistory.minutely.slice(-60).map((point, index) => ({
      time: index,
      price: parseFloat(point.price || point.priceETH || 0),
      timestamp: point.timestamp || point.time || index
    }));
  }

  if (chartData.length === 0) {
    return <div className="no-chart-data">No price history data available</div>;
  }

  // Simple line chart using SVG
  const maxPrice = Math.max(...chartData.map(d => d.price));
  const minPrice = Math.min(...chartData.map(d => d.price));
  const range = maxPrice - minPrice || 1;
  const width = 600;
  const height = 200;
  const padding = 40;

  const points = chartData.map((d, i) => {
    // Handle single point case to avoid division by zero
    const x = chartData.length === 1
      ? padding + (width - 2 * padding) / 2  // Center the single point
      : padding + (i / (chartData.length - 1)) * (width - 2 * padding);
    const y = padding + (height - 2 * padding) - ((d.price - minPrice) / range) * (height - 2 * padding);
    return `${x},${y}`;
  }).join(' ');

  return (
    <div className="price-chart">
      <h3>Price History</h3>
      <svg width={width} height={height} className="chart-svg">
        <defs>
          <linearGradient id="gradient" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#4f46e5" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#4f46e5" stopOpacity="0" />
          </linearGradient>
        </defs>
        <polyline
          points={points}
          fill="none"
          stroke="#4f46e5"
          strokeWidth="2"
        />
        <polygon
          points={`${padding},${height - padding} ${points} ${width - padding},${height - padding}`}
          fill="url(#gradient)"
        />
        <text x={padding} y={padding} fontSize="12" fill="#666">
          {maxPrice.toFixed(8)} ETH
        </text>
        <text x={padding} y={height - padding + 15} fontSize="12" fill="#666">
          {minPrice.toFixed(8)} ETH
        </text>
      </svg>
    </div>
  );
}

function CreateAPIForm({ onSubmit, onCancel }) {
  const [formData, setFormData] = useState({
    name: '',
    endpoint: '',
    target_url: '',
    method: 'GET',
    wallet_address: '',
    description: '',
    input_format: {},
    output_format: {}
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(formData);
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  return (
    <div className="create-form-container">
      <form className="create-form" onSubmit={handleSubmit}>
        <h2>Create New API</h2>

        <div className="form-group">
          <label>API Name *</label>
          <input
            type="text"
            name="name"
            value={formData.name}
            onChange={handleChange}
            required
            placeholder="e.g., Weather API"
          />
        </div>

        <div className="form-group">
          <label>Endpoint *</label>
          <input
            type="text"
            name="endpoint"
            value={formData.endpoint}
            onChange={handleChange}
            required
            placeholder="/weather"
          />
        </div>

        <div className="form-group">
          <label>Target URL *</label>
          <input
            type="url"
            name="target_url"
            value={formData.target_url}
            onChange={handleChange}
            required
            placeholder="https://api.example.com/weather"
          />
        </div>

        <div className="form-group">
          <label>Method *</label>
          <select
            name="method"
            value={formData.method}
            onChange={handleChange}
            required
          >
            <option value="GET">GET</option>
            <option value="POST">POST</option>
          </select>
        </div>

        <div className="form-group">
          <label>Wallet Address *</label>
          <input
            type="text"
            name="wallet_address"
            value={formData.wallet_address}
            onChange={handleChange}
            required
            placeholder="0x..."
          />
        </div>

        <div className="form-group">
          <label>Description</label>
          <textarea
            name="description"
            value={formData.description}
            onChange={handleChange}
            placeholder="Describe what this API does..."
            rows="3"
          />
        </div>

        <div className="form-actions">
          <button type="submit" className="submit-button">Create API</button>
          <button type="button" onClick={onCancel} className="cancel-button">Cancel</button>
        </div>
      </form>
    </div>
  );
}

export default App;
