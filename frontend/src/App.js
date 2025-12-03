import React, { useState, useEffect } from 'react';
import './App.css';

const API_BASE_URL = 'http://127.0.0.1:5000';

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
        await response.json(); // Consume response
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
  const apiUrl = `${API_BASE_URL}${api.endpoint}`;
  const flaunchLink = api.token?.view_on_flaunch || details?.links?.flaunch;
  const tokenAddress = api.token?.address || details?.token_address;

  // Extract pricing from details (simplified structure)
  const tokenPriceUsd = details?.pricing?.token_price_usd || api.pricing?.token_price_usd || 0;
  const apiPriceUsd = details?.pricing?.api_price_usd || api.pricing?.api_price_usd || 0;
  const priceMultiplier = details?.pricing?.price_multiplier || api.pricing?.price_multiplier || 0;
  const volume24h = details?.pricing?.volume_24h_usd || api.pricing?.volume_24h_usd || 0;
  const volume7d = details?.pricing?.volume_7d_usd || api.pricing?.volume_7d_usd || 0;
  
  const tokenSymbol = api.token?.symbol || details?.symbol || 'N/A';
  const tokenName = details?.api_name || api.name;

  // Format numbers
  const formatCurrency = (value) => {
    if (value === 0) return '$0.00';
    if (value < 0.000001) return `$${value.toFixed(10)}`;
    if (value < 0.01) return `$${value.toFixed(8)}`;
    if (value < 1) return `$${value.toFixed(4)}`;
    if (value < 1000) return `$${value.toFixed(2)}`;
    if (value < 1000000) return `$${(value / 1000).toFixed(2)}K`;
    if (value < 1000000000) return `$${(value / 1000000).toFixed(2)}M`;
    return `$${(value / 1000000000).toFixed(2)}B`;
  };

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
        <div className="token-metrics">
          <div className="token-header">
            <div className="token-name-symbol">
              <h3>{tokenName}</h3>
              <span className="token-symbol">{tokenSymbol}</span>
            </div>
            {flaunchLink && (
              <a
                href={flaunchLink}
                target="_blank"
                rel="noopener noreferrer"
                className="flaunch-link"
              >
                View on Flaunch →
              </a>
            )}
          </div>

          {/* Pricing Section - API Price */}
          <div className="pricing-section">
            <div className="price-highlight">
              <label>💰 API Price per Call</label>
              <span className="api-price">{formatCurrency(apiPriceUsd)}</span>
            </div>
            <div className="price-transform">
              <span className="transform-text">
                Token: {formatCurrency(tokenPriceUsd)} × {priceMultiplier}
              </span>
            </div>
          </div>

          <div className="metrics-grid">
            <div className="metric">
              <label>24h Volume</label>
              <span className="metric-value">{formatCurrency(volume24h)}</span>
            </div>
            <div className="metric">
              <label>7d Volume</label>
              <span className="metric-value">{formatCurrency(volume7d)}</span>
            </div>
            <div className="metric">
              <label>Contract Address</label>
              <span className="metric-value contract-address">
                {tokenAddress ? `${tokenAddress.slice(0, 6)}...${tokenAddress.slice(-4)}` : 'N/A'}
              </span>
            </div>
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
      </div>
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
    price_multiplier: 10000,
    starting_market_cap: '1000000',
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

        <div className="form-group">
          <label>Price Multiplier (Optional)</label>
          <input
            type="number"
            name="price_multiplier"
            value={formData.price_multiplier}
            onChange={handleChange}
            placeholder="10000"
          />
          <small className="form-help">Token price × multiplier = API price. Default: 10000</small>
        </div>

        <div className="form-group">
          <label>Starting Market Cap (Optional)</label>
          <input
            type="text"
            name="starting_market_cap"
            value={formData.starting_market_cap}
            onChange={handleChange}
            placeholder="1000000"
          />
          <small className="form-help">In wei. 1,000,000 wei ≈ $1 USD. Default: 1000000</small>
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
