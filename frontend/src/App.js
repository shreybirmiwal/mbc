import React, { useState, useEffect, useRef } from 'react';
import './App.css';

const API_BASE_URL = 'http://127.0.0.1:5000';
const DEFAULT_PRICE_MULTIPLIER = 10000;
const DEFAULT_STARTING_MARKET_CAP = '1000000';

// Spinning 3D Earth Globe Component
function AsciiGlobe() {
  const [frame, setFrame] = useState(0);
  const animationRef = useRef();

  useEffect(() => {
    let lastTime = 0;
    const targetFPS = 20;
    const frameInterval = 1000 / targetFPS;

    const animate = (currentTime) => {
      if (currentTime - lastTime >= frameInterval) {
        setFrame(prev => (prev + 2) % 360);
        lastTime = currentTime;
      }
      animationRef.current = requestAnimationFrame(animate);
    };
    animationRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationRef.current);
  }, []);

  const renderGlobe = () => {
    const width = 30;
    const height = 15;
    const radius = 6;

    const angleX = frame * Math.PI / 180;
    const angleY = frame * 0.3 * Math.PI / 180;

    const output = Array(height).fill(null).map(() => Array(width).fill(' '));
    const zbuffer = Array(height).fill(null).map(() => Array(width).fill(-Infinity));

    // Draw sphere
    for (let i = 0; i < height; i++) {
      for (let j = 0; j < width; j++) {
        const x = (j - width / 2) / 2;
        const y = (i - height / 2);
        const z2 = radius * radius - x * x - y * y;

        if (z2 >= 0) {
          const z = Math.sqrt(z2);

          // Rotate
          const rx = x;
          const ry = y * Math.cos(angleY) - z * Math.sin(angleY);
          const rz = y * Math.sin(angleY) + z * Math.cos(angleY);

          const rrx = rx * Math.cos(angleX) + rz * Math.sin(angleX);
          const rrz = -rx * Math.sin(angleX) + rz * Math.cos(angleX);

          // Simple continents pattern (rough Earth-like)
          const lat = Math.asin(ry / radius);
          const lon = Math.atan2(rrx, rrz);

          // Create landmasses pattern
          const pattern = Math.sin(lat * 3) * Math.cos(lon * 4) +
            Math.sin(lat * 5) * Math.sin(lon * 2) +
            Math.cos(lat * 2) * Math.sin(lon * 3);

          // Lighting
          const nx = rrx / radius;
          const ny = ry / radius;
          const nz = rrz / radius;
          const light = Math.max(0, nx * 0.7 + ny * 0.3 + nz * 0.6);

          const isLand = pattern > 0.3;
          let char;

          if (isLand) {
            // Land with shading
            if (light > 0.7) char = '#';
            else if (light > 0.5) char = '%';
            else if (light > 0.3) char = '*';
            else char = '+';
          } else {
            // Ocean with shading
            if (light > 0.7) char = '~';
            else if (light > 0.5) char = '-';
            else if (light > 0.3) char = '=';
            else char = '.';
          }

          if (rrz > zbuffer[i][j]) {
            zbuffer[i][j] = rrz;
            output[i][j] = char;
          }
        }
      }
    }

    return output.map(row => row.join('')).join('\n');
  };

  return (
    <pre className="ascii-globe">
      {/* {renderGlobe()} */}
    </pre>
  );
}

function App() {
  const [apis, setApis] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [apiDetails, setApiDetails] = useState({});
  const [time, setTime] = useState(new Date().toLocaleTimeString());

  // Real-time clock for the taskbar
  useEffect(() => {
    const timer = setInterval(() => setTime(new Date().toLocaleTimeString()), 1000);
    fetchApis();
    return () => clearInterval(timer);
  }, []);

  const fetchApis = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/admin/list-apis`);
      const data = await response.json();
      const apisList = data.apis || [];
      setApis(apisList);

      const detailsPromises = apisList.map(async (api) => {
        // Always try to fetch API info for updated pricing
        try {
          const endpoint = api.endpoint.replace(/^\//, '');
          const infoResponse = await fetch(`${API_BASE_URL}/admin/api-info/${endpoint}`);
          if (infoResponse.ok) {
            const info = await infoResponse.json();
            return { endpoint: api.endpoint, info };
          }
        } catch (error) {
          // API info might not be available if token not deployed yet, that's okay
          console.error(`Error fetching info for ${api.endpoint}:`, error);
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
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });

      if (response.ok) {
        await response.json();
        alert('>> SYSTEM MSG: UPLOAD SUCCESSFUL');
        setShowCreateForm(false);
        fetchApis();
      } else {
        const error = await response.json();
        alert(`>> ERROR: ${error.error || 'EXECUTION FAILED'}`);
      }
    } catch (error) {
      console.error('Error creating API:', error);
      alert('>> SYSTEM FATAL ERROR');
    }
  };

  if (loading) {
    return (
      <div className="app" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <h2>INITIALIZING BAZAAR...</h2>
          <p>>>> ESTABLISHING SECURE CONNECTION</p>
          <p>>>> DECRYPTING PACKETS</p>
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="main-header">
        <div className="ascii-art-banner">
          {/* <pre className="ascii-banner-text">
            {`                    %######*****************************************                                                     
                    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%##################*********                                    
                     %%*+=-=#%%%#+----+%%%%#----=%%%%%+-===*#%%%#%%%%%%%#%#%#%####%%%%%#####******                       
                     %*----*%%%%#=----#%%%%*----+%%%%%=----+%%%#=---*%%%*----+%%%%%#%%%%%%%%%%%%%%%%%###**               
                    %#=---+#%%%%+----=%%%%%=----+%%%%#=----+%%%#=---*%%%*----=%%%%#-----#%%%*-==++#%%%%%%%%%             
                  #%#=---=#%%%%#-----#%%%%#-----*%%%%#=----*%%%%=---*%%%*=---=%%%%%-----*%%%*-----+%%%%#=-*# ...         
                 %%#=---=#%%%%%=----+%%%%%+----=#%%%%#=---=*%%%%+---*%%%#=---=#%%%%=----+%%%#=----=#%%%%+-=*..           
                #%#=---=#%%%%%+=====#%%%%#=-===+%%%%%*=====#%%%%+===*%%%%+====#%%%%+-=--=%%%%+=---=#%%%%*=-+#            
              #%%*=====#%%%%%*=====*%##%%+=====*%%%%%*====+#%%%%+===*%%%%+====*%%%%#=====*%%%%=====+%%##%+-=+%%          
            %%%#=====+%%%%%%*=====+###%##+=====######=====+#####+===+####+====+####%+=====#%%%#=====*%#%%%+===#%%%       
         ##%%%*=====+%%%###*======+***##*+===+*%#####+++++*%####*+++*####*+++++#####*+++++#####++++++#####%+====*%%%#%   
     %##%%##*======+########++++++*#####%++++++%#####+++++*%#####+=+*###%*+===+%###%*+===+#####++==+*######+++++++#######
   %#########+++++++########*+====+%####%*+===+#####%*====+%%%%%*===*%%%%*===+*###%%+====+##%%+====+#%#%%#+==+==+#%#%%%%%
   %########%*++=+++*%#######+====+#%###%#+====#%%%%%*==++*%%%%%%##%#+++++++++++++#%*++++++*%%*+++++++++++++++++*#%#%%%# 
    ##########+=====+#%%%%%%%+=====*%%####+==+*%%%%%%%%%%%%%%%%%%%%#++++**+*******%%%+++*#+----+*++++++++++++++++        
    ##%######%#+=====*######%*====++#%*+++++*%%%%%%%%%%%%%%%%%%%#                 %%%  .#--+##++-#        +*+++++        
      %%%%%%%%%+=====++++++*%%*++* #%%%   %%%%%%%%%%%%%%%%%%%%                    %%%.  #:+*%%#+-+                       
      #%%%%%#*++++++++=: ..#%#%    %%%%%%%%%%%%%%%%%%%%%%%%%                      %%#. .++-=+++-=#                       
           +++      .......#%#%     %%%%%%%%%%%%%%%%%%%                           %%%....-*++++%#                        
                      ..   %%#%    #%%%%##%#%####                                 %%%  ..  %%%%                          
                           %%#%    %%%%%##                                        %%%    =-------==                      
              ...          %%##   #%%%%%%%#                                    ...%%%   --:::::::::-=                    
           ...             %%#%   %%%%%%%%#                                 ...   %%% --::-=-::-=-::--                   
         . ...             %%#%  #%%%%%%%%%                               . ...   %%% -::-=:-------::-                   
       .  .                %%#% #%%%%%%%%%%#                               .      %%% -::----------::-                   
      .                    %%#% %%%%%%%%%%%                            .          %%% --::=-:----=-:--                   
     . .                   %%#%#%%%%%%%                               .  .        %%%  =-::------::--                    
  .  .                     %%##%%%%%%%#                            .  .           %%%   =--::::::--=                     
....                       %%%%%%%%%%%#                          ....             %%%      ###+==                        
.  .                        %%%%#======-                         .  .              %%%      ##*+===                       
                           %%#%========                   =                       %%%   ==============                   
                           %%#%========                  ====                     %%% ====++======++===                  
                           %%%===========          #%%## ====-:::             -===*%%===+===--::--==++===                
    ---=====----           %*==---========****===-*#%%%%*+==+-::-*************=----**=====-:-====-:======                
   -------------           +===--=========+**+=--=%%%%%%%#*++****++***#%%#*#*=-----====+==:-======--======               
   -------------           *+=---=========*+=----%%#%%%%%%#+++++++**#%*%%*+==---------=+==:-======--==+===               
-----  ----------------=- =----  %#============*+:::---%%%%%%%%%#+++++++++==---::::-----:::::::--:-===-:-==+===                
-----------------------------------+%%+========+#-:::::--*%%%%%%%%=====++=++=-----===--:::::::::::-------===+===                 
--  =============------========= ---#%%*======+#%+::::--==%%%%%%%*++=+++++=++=====+++==--::::::::--=++=+++=====                  
---+=======================-::::-::::+**++===+***+-::-===+*%%%%%#*++++++++++*+++++++*++===-:::::-============         .          
-----====--------======-:::::::::::::--=++++++++++++++++********************************************************##   ...         
 ----------------------:::::::::::::::::=#########################################################################=...           
     ------------------::::::::-::-::::-=#########################################################################+..            
       +=======-=======-::::---::::---::+#########################################################################=              
          ++============---::::::::::--=##########################################################################               
               +======   :::-:::::::::     . ..                                                             .  .`}
          </pre> */}
        </div>
        <div className="header-content">
          {/* <AsciiGlobe /> */}
          <div className="header-text">
            <h1>BAZAAR // MARKETPLACE</h1>
            <div className="system-status">
              <span>STATUS: ONLINE</span>
              <span>ENCRYPTION: 256-BIT</span>
              <span>NODES: {apis.length}</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="apis-grid">
        {apis.length === 0 ? (
          <div className="console-window">
            <div className="window-header">SYSTEM_MSG</div>
            <div className="window-content">
              <p>>> NO DATA FOUND.</p>
              <p>>> INITIATE NEW PROTOCOL TO BEGIN.</p>
            </div>
          </div>
        ) : (
          apis.map((api, index) => (
            <ConsoleCard
              key={api.endpoint}
              api={api}
              details={apiDetails[api.endpoint]}
              index={index}
            />
          ))
        )}
      </div>

      {/* Taskbar */}
      <div className="taskbar">
        <div className="taskbar-items">
          <button className="start-btn" onClick={() => setShowCreateForm(true)}>[ + NEW_PROTOCOL ]</button>
          <span> > BAZAAR_OS_READY</span>
          <span> > MONITORING_TRAFFIC</span>
        </div>
        <div>{time}</div>
      </div>

      {showCreateForm && (
        <div className="modal-overlay">
          <CreateAPIForm
            onSubmit={handleCreateAPI}
            onCancel={() => setShowCreateForm(false)}
          />
        </div>
      )}
    </div>
  );
}

// Reusable Console Window Component
function ConsoleCard({ api, details, index }) {
  const fullUrl = `${API_BASE_URL}${api.endpoint}`;
  const tokenAddress = api.token?.address || details?.token_address;
  const tokenName = details?.api_name || api.name;

  const formatCurrency = (value) => {
    if (!value) return '$0.0000000000';
    return `$${value.toLocaleString(undefined, { minimumFractionDigits: 10, maximumFractionDigits: 10 })}`;
  };

  const handleCopy = (text, label) => {
    navigator.clipboard.writeText(text);
    alert(`>> ${label} COPIED TO CLIPBOARD`);
  };

  return (
    <div className="console-window">
      <div className="window-content">
        <div className="card-layout">
          {/* Left Side - Chart */}
          {tokenAddress && (
            <div className="chart-section">
              <div className="chart-frame">
                <iframe
                  src={`https://dexscreener.com/base/${tokenAddress}?embed=1&chartOnly=1&theme=dark&trades=0&info=0`}
                  title="DexScreener Chart"
                  className="dexscreener-chart-iframe"
                  frameBorder="0"
                />
              </div>
            </div>
          )}

          {/* Right Side - Info */}
          <div className="info-section">
            <h2 style={{ marginTop: 0, marginBottom: '1rem' }}>{tokenName}</h2>

            {/* Description */}
            {(details?.description || api.description) && (
              <div className="description-section">
                <div className="data-label">DESCRIPTION:</div>
                <div className="description-text">{details?.description || api.description}</div>
              </div>
            )}

            {/* Full URL Access Point */}
            <div className="access-point-container">
              <div className="data-label">ACCESS_POINT:</div>
              <div className="url-row">
                <span className="url-text">{fullUrl}</span>
                <button className="copy-btn" onClick={() => handleCopy(fullUrl, 'URL')}>
                  [COPY]
                </button>
              </div>
            </div>

            <div className="data-display">
              <div className="data-row">
                <span className="data-label">STATUS</span>
                <span className="data-value" style={{ color: api.status === 'active' || api.status === 'deployed' ? '#0f0' : 'red' }}>
                  [{api.status.toUpperCase()}]
                </span>
              </div>

              {/* API Price - show if available */}
              {(details?.pricing?.api_price_usd || api.pricing?.api_price_usd) && (
                <div className="data-row">
                  <span className="data-label">API_PRICE</span>
                  <span className="data-value">{formatCurrency(details?.pricing?.api_price_usd || api.pricing?.api_price_usd)}</span>
                </div>
              )}

              {api.token && (
                <>
                  <div className="data-row">
                    <span className="data-label">TOKEN_PRICE</span>
                    <span className="data-value">{formatCurrency(details?.pricing?.token_price_usd || api.pricing?.token_price_usd)}</span>
                  </div>

                  <div className="data-row">
                    <span className="data-label">CONTRACT</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <span className="data-value" style={{ fontSize: '0.8em' }}>
                        {tokenAddress ? `${tokenAddress.slice(0, 6)}...${tokenAddress.slice(-4)}` : 'NULL'}
                      </span>
                      {tokenAddress && (
                        <button className="copy-btn" onClick={() => handleCopy(tokenAddress, 'CONTRACT ADDRESS')}>
                          [COPY]
                        </button>
                      )}
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function CreateAPIForm({ onSubmit, onCancel }) {
  const [formData, setFormData] = useState({
    name: '', endpoint: '', target_url: '', method: 'GET',
    wallet_address: '', description: '',
    price_multiplier: DEFAULT_PRICE_MULTIPLIER,
    starting_market_cap: DEFAULT_STARTING_MARKET_CAP
  });

  const handleChange = (e) => setFormData({ ...formData, [e.target.name]: e.target.value });

  return (
    <div className="console-window" style={{ width: '500px', margin: 0 }}>
      <div className="window-header">
        <span>> BAZAAR // EXECUTE_NEW_PROTOCOL</span>
        <div className="window-controls" onClick={onCancel} style={{ cursor: 'pointer' }}>X</div>
      </div>
      <div className="window-content">
        <form onSubmit={(e) => { e.preventDefault(); onSubmit(formData); }} className="form-grid">

          <div>
            <label>>> NAME_ID:</label>
            <input name="name" onChange={handleChange} placeholder="Required..." required />
          </div>

          <div>
            <label>>> ENDPOINT_SLUG:</label>
            <input name="endpoint" onChange={handleChange} placeholder="/example" required />
          </div>

          <div>
            <label>>> TARGET_URL:</label>
            <input name="target_url" onChange={handleChange} type="url" required />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div>
              <label>>> METHOD:</label>
              <select name="method" onChange={handleChange}>
                <option value="GET">GET</option>
                <option value="POST">POST</option>
              </select>
            </div>
            <div>
              <label>>> CREATOR_WALLET:</label>
              <input name="wallet_address" onChange={handleChange} required />
            </div>
          </div>

          <div>
            <label>>> DATA_DESCRIPTION:</label>
            <textarea name="description" rows="3" onChange={handleChange}></textarea>
          </div>

          <div style={{ marginTop: '1rem', display: 'flex', justifyContent: 'space-between' }}>
            <button type="button" onClick={onCancel} style={{ borderColor: 'red', color: 'red' }}>[ ABORT ]</button>
            <button type="submit">[ INITIATE ]</button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default App;