import React, { useState, useRef, useEffect } from 'react';
import './WorkflowBuilder.css';

const API_BASE_URL = ''; // Use proxy - requests will be forwarded to backend

function WorkflowBuilder() {
  const [apis, setApis] = useState([]);
  const [nodes, setNodes] = useState([]);
  const [connections, setConnections] = useState([]);
  const [selectedNode, setSelectedNode] = useState(null);
  const [draggingNode, setDraggingNode] = useState(null);
  const [connecting, setConnecting] = useState(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const canvasRef = useRef(null);
  const [apiDetails, setApiDetails] = useState({});
  const [apiSchemas, setApiSchemas] = useState({});
  const [editingNode, setEditingNode] = useState(null);
  const [editingConnection, setEditingConnection] = useState(null);
  const [executionResults, setExecutionResults] = useState(null);
  const [executing, setExecuting] = useState(false);
  const [showDeployModal, setShowDeployModal] = useState(false);
  const [deploymentResult, setDeploymentResult] = useState(null);

  useEffect(() => {
    fetchApis();
  }, []);

  const fetchApis = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/admin/list-apis`);

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const text = await response.text();
      if (!text) {
        console.error('Empty response from server');
        return;
      }

      const data = JSON.parse(text);
      const apisList = data.apis || [];
      setApis(apisList);

      // Fetch pricing details for each API
      const detailsPromises = apisList.map(async (api) => {
        try {
          const endpoint = api.endpoint.replace(/^\//, '');

          // Fetch API info
          const infoResponse = await fetch(`${API_BASE_URL}/admin/api-info/${endpoint}`);
          let info = null;
          if (infoResponse.ok) {
            info = await infoResponse.json();
          }

          // Fetch API schema
          const schemaResponse = await fetch(`${API_BASE_URL}/admin/api-schema/${endpoint}`);
          let schema = null;
          if (schemaResponse.ok) {
            schema = await schemaResponse.json();
          }

          return { endpoint: api.endpoint, info, schema };
        } catch (error) {
          console.error(`Error fetching info for ${api.endpoint}:`, error);
        }
        return { endpoint: api.endpoint, info: null, schema: null };
      });

      const details = await Promise.all(detailsPromises);
      const detailsMap = {};
      const schemasMap = {};
      details.forEach(({ endpoint, info, schema }) => {
        detailsMap[endpoint] = info;
        schemasMap[endpoint] = schema;
      });
      setApiDetails(detailsMap);
      setApiSchemas(schemasMap);
    } catch (error) {
      console.error('Error fetching APIs:', error);
    }
  };

  const addNodeToCanvas = (api) => {
    const schema = apiSchemas[api.endpoint] || {};

    // Extract input parameters from schema
    const inputParams = [];
    if (schema.input_format) {
      if (schema.input_format.query_params) {
        Object.keys(schema.input_format.query_params).forEach(param => {
          inputParams.push(param);
        });
      }
      if (schema.input_format.body) {
        if (typeof schema.input_format.body === 'object' && schema.input_format.body.properties) {
          Object.keys(schema.input_format.body.properties).forEach(param => {
            inputParams.push(param);
          });
        }
      }
    }

    // Extract output fields from schema
    const outputParams = [];
    if (schema.output_format) {
      if (typeof schema.output_format === 'object' && schema.output_format.properties) {
        Object.keys(schema.output_format.properties).forEach(param => {
          outputParams.push(param);
        });
      }
    }

    // Default to generic input/output if no schema
    if (inputParams.length === 0) inputParams.push('input');
    if (outputParams.length === 0) outputParams.push('output');

    const newNode = {
      id: `node-${Date.now()}`,
      api: api,
      position: {
        x: 100 + (nodes.length * 50) % 400,
        y: 100 + Math.floor(nodes.length / 5) * 200
      },
      inputs: inputParams,
      outputs: outputParams,
      parameters: {} // User-configured parameters
    };
    setNodes([...nodes, newNode]);
  };

  const handleNodeMouseDown = (e, nodeId) => {
    if (e.button !== 0) return; // Only left mouse button
    e.stopPropagation();

    const node = nodes.find(n => n.id === nodeId);
    if (!node) return;

    const rect = e.currentTarget.getBoundingClientRect();
    setDragOffset({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top
    });
    setDraggingNode(nodeId);
    setSelectedNode(nodeId);
  };

  const handleCanvasMouseMove = (e) => {
    if (draggingNode) {
      const canvas = canvasRef.current;
      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left - dragOffset.x;
      const y = e.clientY - rect.top - dragOffset.y;

      setNodes(nodes.map(node =>
        node.id === draggingNode
          ? { ...node, position: { x, y } }
          : node
      ));
    }
  };

  const handleCanvasMouseUp = () => {
    setDraggingNode(null);
  };

  const handleNodeClick = (nodeId, type) => {
    // type is 'output' or 'input'
    if (type === 'output') {
      if (connecting) {
        // Can't connect output to output, cancel
        setConnecting(null);
      } else {
        // Start a connection from this node's output
        setConnecting({ nodeId, type: 'output' });
      }
    } else if (type === 'input') {
      if (connecting && connecting.nodeId !== nodeId && connecting.type === 'output') {
        // Complete the connection
        const newConnection = {
          id: `conn-${Date.now()}`,
          from: { nodeId: connecting.nodeId },
          to: { nodeId },
          fieldMappings: [] // Will be configured later
        };
        setConnections([...connections, newConnection]);
        setConnecting(null);

        // Auto-open mapping modal
        setEditingConnection(newConnection.id);
      }
    }
  };

  const removeNode = (nodeId) => {
    setNodes(nodes.filter(n => n.id !== nodeId));
    setConnections(connections.filter(c =>
      c.from.nodeId !== nodeId && c.to.nodeId !== nodeId
    ));
    if (selectedNode === nodeId) {
      setSelectedNode(null);
    }
  };

  const removeConnection = (connId) => {
    setConnections(connections.filter(c => c.id !== connId));
    if (editingConnection === connId) {
      setEditingConnection(null);
    }
  };

  const updateConnectionMappings = (connId, mappings) => {
    setConnections(connections.map(conn =>
      conn.id === connId
        ? { ...conn, fieldMappings: mappings }
        : conn
    ));
  };

  const calculateTotalPrice = () => {
    let total = 0;
    nodes.forEach(node => {
      const details = apiDetails[node.api.endpoint];
      const price = details?.pricing?.api_price_usd || 0;
      total += price;
    });
    return total;
  };

  const getNodePosition = (nodeId) => {
    const node = nodes.find(n => n.id === nodeId);
    return node ? node.position : { x: 0, y: 0 };
  };

  const formatCurrency = (value) => {
    if (!value) return '$0.0000000000';
    return `$${value.toLocaleString(undefined, { minimumFractionDigits: 10, maximumFractionDigits: 10 })}`;
  };

  const clearCanvas = () => {
    if (window.confirm('>> CONFIRM: CLEAR ALL NODES AND CONNECTIONS?')) {
      setNodes([]);
      setConnections([]);
      setSelectedNode(null);
    }
  };

  const deployWorkflow = () => {
    if (nodes.length === 0) {
      alert('>> ERROR: NO NODES IN WORKFLOW');
      return;
    }

    // Check that all connections have field mappings
    const unmappedConnections = connections.filter(c => !c.fieldMappings || c.fieldMappings.length === 0);
    if (unmappedConnections.length > 0) {
      alert(`>> WARNING: ${unmappedConnections.length} connection(s) need field mappings!\n>> Click orange connection lines to configure.`);
      return;
    }

    setShowDeployModal(true);
  };

  const executeWorkflow = async () => {
    if (nodes.length === 0) {
      alert('>> ERROR: NO NODES IN WORKFLOW');
      return;
    }

    setExecuting(true);
    setExecutionResults(null);

    try {
      const workflowData = {
        nodes: nodes.map(n => ({
          id: n.id,
          endpoint: n.api.endpoint,
          inputs: n.parameters || {}
        })),
        connections: connections.map(c => ({
          from: { nodeId: c.from.nodeId },
          to: { nodeId: c.to.nodeId },
          fieldMappings: c.fieldMappings || []
        }))
      };

      const response = await fetch(`${API_BASE_URL}/admin/execute-workflow`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(workflowData)
      });

      const result = await response.json();

      if (result.success) {
        setExecutionResults(result);
        alert(`>> WORKFLOW EXECUTED SUCCESSFULLY\n>> NODES: ${result.nodes_executed}\n>> TOTAL COST: ${formatCurrency(result.total_cost)}`);
      } else {
        alert(`>> WORKFLOW EXECUTION FAILED\n>> ERROR: ${result.error}`);
        setExecutionResults(result);
      }
    } catch (error) {
      console.error('Error executing workflow:', error);
      alert(`>> EXECUTION ERROR: ${error.message}`);
    } finally {
      setExecuting(false);
    }
  };

  const updateNodeParameters = (nodeId, parameters) => {
    setNodes(nodes.map(node =>
      node.id === nodeId
        ? { ...node, parameters }
        : node
    ));
  };

  return (
    <div className="workflow-builder">
      <div className="workflow-header">
        <h2>API WORKFLOW BUILDER // CHAIN CONSTRUCTOR</h2>
        <div className="workflow-stats">
          <span>NODES: {nodes.length}</span>
          <span>CONNECTIONS: {connections.length}</span>
          <span>TOTAL COST: {formatCurrency(calculateTotalPrice())}</span>
        </div>
      </div>

      <div className="workflow-container">
        {/* API Palette */}
        <div className="api-palette">
          <div className="palette-header">AVAILABLE APIS</div>
          <div className="palette-content">
            {apis.length === 0 ? (
              <div className="palette-empty">
                <p>&gt;&gt; NO APIS AVAILABLE</p>
              </div>
            ) : (
              apis.map((api, index) => {
                const details = apiDetails[api.endpoint];
                const price = details?.pricing?.api_price_usd || 0;
                return (
                  <div
                    key={index}
                    className="palette-item"
                    onClick={() => addNodeToCanvas(api)}
                  >
                    <div className="palette-item-name">{details?.api_name || api.name}</div>
                    <div className="palette-item-price">{formatCurrency(price)}</div>
                    <div className="palette-item-hint">[CLICK TO ADD]</div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Canvas */}
        <div
          className="workflow-canvas"
          ref={canvasRef}
          onMouseMove={handleCanvasMouseMove}
          onMouseUp={handleCanvasMouseUp}
          onMouseLeave={handleCanvasMouseUp}
        >
          {/* Render connections */}
          <svg className="connections-layer">
            {connections.map(conn => {
              const fromNode = getNodePosition(conn.from.nodeId);
              const toNode = getNodePosition(conn.to.nodeId);

              const x1 = fromNode.x + 280; // Right side of node
              const y1 = fromNode.y + 70; // Middle of node
              const x2 = toNode.x; // Left side of node
              const y2 = toNode.y + 70;

              // Calculate midpoint for interaction
              const midX = (x1 + x2) / 2;
              const midY = (y1 + y2) / 2;

              const hasMapping = conn.fieldMappings && conn.fieldMappings.length > 0;

              return (
                <g key={conn.id}>
                  <line
                    x1={x1}
                    y1={y1}
                    x2={x2}
                    y2={y2}
                    stroke={hasMapping ? "var(--terminal-green)" : "#ffaa00"}
                    strokeWidth="2"
                    strokeDasharray="5,5"
                    style={{ cursor: 'pointer' }}
                    onClick={() => setEditingConnection(conn.id)}
                  />
                  {/* Configure button */}
                  <circle
                    cx={midX}
                    cy={midY}
                    r="12"
                    fill={hasMapping ? "var(--terminal-green)" : "#ffaa00"}
                    onClick={() => setEditingConnection(conn.id)}
                    style={{ cursor: 'pointer' }}
                  />
                  <text
                    x={midX}
                    y={midY + 4}
                    fill="#000"
                    fontSize="11"
                    textAnchor="middle"
                    style={{ pointerEvents: 'none', fontWeight: 'bold' }}
                  >
                    {hasMapping ? '✓' : '?'}
                  </text>
                </g>
              );
            })}

            {/* Connection being drawn */}
            {connecting && (
              <line
                x1={getNodePosition(connecting.nodeId).x + 280}
                y1={getNodePosition(connecting.nodeId).y + 70}
                x2={getNodePosition(connecting.nodeId).x + 320}
                y2={getNodePosition(connecting.nodeId).y + 70}
                stroke="var(--terminal-green)"
                strokeWidth="2"
                strokeDasharray="5,5"
                opacity="0.5"
              />
            )}
          </svg>

          {/* Render nodes */}
          {nodes.map(node => {
            const details = apiDetails[node.api.endpoint];
            const price = details?.pricing?.api_price_usd || 0;
            const isSelected = selectedNode === node.id;

            return (
              <div
                key={node.id}
                className={`workflow-node ${isSelected ? 'selected' : ''}`}
                style={{
                  left: `${node.position.x}px`,
                  top: `${node.position.y}px`,
                }}
                onMouseDown={(e) => handleNodeMouseDown(e, node.id)}
              >
                <div className="node-header">
                  <span>{details?.api_name || node.api.name}</span>
                  <button
                    className="node-remove"
                    onClick={(e) => {
                      e.stopPropagation();
                      removeNode(node.id);
                    }}
                  >
                    X
                  </button>
                </div>

                <div className="node-body">
                  <div className="node-info">
                    <div className="node-endpoint">{node.api.endpoint}</div>
                    <div className="node-price">{formatCurrency(price)}</div>
                  </div>

                  <div className="node-ports">
                    {/* Input area - click to connect */}
                    <div
                      className={`connection-area input-area ${connecting?.type === 'output' ? 'can-connect' : ''}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleNodeClick(node.id, 'input');
                      }}
                      title="Click to connect input"
                    >
                      <div className="port-dot"></div>
                      <span>INPUT</span>
                    </div>

                    {/* Output area - click to start connection */}
                    <div
                      className={`connection-area output-area ${!connecting ? 'can-connect' : ''}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleNodeClick(node.id, 'output');
                      }}
                      title="Click to connect output"
                    >
                      <span>OUTPUT</span>
                      <div className="port-dot"></div>
                    </div>
                  </div>

                  {/* Configure button */}
                  <div className="node-footer">
                    <button
                      className="config-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditingNode(node.id);
                      }}
                    >
                      [CONFIG]
                    </button>
                  </div>
                </div>
              </div>
            );
          })}

          {nodes.length === 0 && (
            <div className="canvas-empty-state">
              <p>&gt;&gt; CANVAS EMPTY</p>
              <p>&gt;&gt; SELECT APIS FROM THE LEFT PANEL</p>
              <p>&gt;&gt; CLICK TO ADD NODES</p>
            </div>
          )}
        </div>
      </div>

      {/* Control Panel */}
      <div className="workflow-controls">
        <button
          onClick={deployWorkflow}
          className="control-btn deploy-btn"
          disabled={nodes.length === 0}
        >
          [ DEPLOY AS API ]
        </button>
        <button
          onClick={executeWorkflow}
          className="control-btn execute-btn"
          disabled={executing}
        >
          {executing ? '[ EXECUTING... ]' : '[ TEST WORKFLOW ]'}
        </button>
        <button onClick={clearCanvas} className="control-btn clear-btn">
          [ CLEAR CANVAS ]
        </button>
        {connecting && (
          <span className="connecting-indicator">
            &gt;&gt; CONNECTING... (CLICK INPUT AREA ON TARGET NODE)
          </span>
        )}
        {executionResults && (
          <button
            onClick={() => setExecutionResults(null)}
            className="control-btn"
          >
            [ HIDE RESULTS ]
          </button>
        )}
      </div>

      {/* Parameter Configuration Modal */}
      {editingNode && (
        <NodeConfigModal
          node={nodes.find(n => n.id === editingNode)}
          schema={apiSchemas[nodes.find(n => n.id === editingNode)?.api.endpoint]}
          onSave={(params) => {
            updateNodeParameters(editingNode, params);
            setEditingNode(null);
          }}
          onClose={() => setEditingNode(null)}
        />
      )}

      {/* Connection Mapping Modal */}
      {editingConnection && (
        <ConnectionMappingModal
          connection={connections.find(c => c.id === editingConnection)}
          nodes={nodes}
          apiSchemas={apiSchemas}
          onSave={(mappings) => {
            updateConnectionMappings(editingConnection, mappings);
            setEditingConnection(null);
          }}
          onDelete={() => {
            removeConnection(editingConnection);
            setEditingConnection(null);
          }}
          onClose={() => setEditingConnection(null)}
        />
      )}

      {/* Execution Results Modal */}
      {executionResults && (
        <ExecutionResultsModal
          results={executionResults}
          onClose={() => setExecutionResults(null)}
        />
      )}

      {/* Deploy Modal */}
      {showDeployModal && (
        <DeployWorkflowModal
          nodes={nodes}
          connections={connections}
          onClose={() => {
            setShowDeployModal(false);
            setDeploymentResult(null);
          }}
          onSuccess={(result) => {
            setDeploymentResult(result);
          }}
        />
      )}
    </div>
  );
}

// Deploy Workflow Modal Component
function DeployWorkflowModal({ nodes, connections, onClose, onSuccess }) {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    wallet_address: ''
  });
  const [deploying, setDeploying] = useState(false);
  const [deploymentStatus, setDeploymentStatus] = useState(null);

  const handleDeploy = async (e) => {
    e.preventDefault();
    setDeploying(true);

    try {
      const workflowData = {
        name: formData.name,
        description: formData.description,
        wallet_address: formData.wallet_address,
        nodes: nodes.map(n => ({
          id: n.id,
          endpoint: n.api.endpoint,
          inputs: n.parameters || {}
        })),
        connections: connections.map(c => ({
          from: { nodeId: c.from.nodeId },
          to: { nodeId: c.to.nodeId },
          fieldMappings: c.fieldMappings || []
        }))
      };

      const response = await fetch(`${API_BASE_URL}/admin/deploy-workflow`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(workflowData)
      });

      const result = await response.json();

      if (result.success) {
        setDeploymentStatus({
          success: true,
          endpoint: result.endpoint,
          job_id: result.job_id,
          message: result.message
        });
        onSuccess(result);

        // Poll for completion
        pollDeploymentStatus(result.job_id, result.endpoint);
      } else {
        setDeploymentStatus({
          success: false,
          error: result.error
        });
      }
    } catch (error) {
      setDeploymentStatus({
        success: false,
        error: error.message
      });
    } finally {
      setDeploying(false);
    }
  };

  const pollDeploymentStatus = async (jobId, endpoint) => {
    // Poll every 2 seconds for up to 60 seconds
    let attempts = 0;
    const maxAttempts = 30;

    const interval = setInterval(async () => {
      attempts++;

      try {
        const response = await fetch(`${API_BASE_URL}/admin/api-info/${endpoint.replace('/', '')}`);
        if (response.ok) {
          const info = await response.json();

          if (info.token?.address) {
            // Deployment complete!
            setDeploymentStatus(prev => ({
              ...prev,
              completed: true,
              apiUrl: `${API_BASE_URL}${endpoint}`,
              tokenAddress: info.token.address,
              flaunchLink: info.token.view_on_flaunch
            }));
            clearInterval(interval);
          }
        }
      } catch (error) {
        console.error('Error polling status:', error);
      }

      if (attempts >= maxAttempts) {
        clearInterval(interval);
        setDeploymentStatus(prev => ({
          ...prev,
          timeout: true
        }));
      }
    }, 2000);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="deploy-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span>DEPLOY WORKFLOW AS API</span>
          <button className="close-btn" onClick={onClose}>X</button>
        </div>

        <div className="modal-body">
          {!deploymentStatus ? (
            <form onSubmit={handleDeploy}>
              <p className="modal-hint">&gt;&gt; CREATE A NEW API ENDPOINT FROM THIS WORKFLOW</p>

              <div className="form-field">
                <label>API Name <span className="required">*</span></label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="My Chained Workflow"
                  required
                />
              </div>

              <div className="form-field">
                <label>Description</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="This workflow chains weather and stock APIs..."
                  rows="3"
                />
              </div>

              <div className="form-field">
                <label>Creator Wallet Address <span className="required">*</span></label>
                <input
                  type="text"
                  value={formData.wallet_address}
                  onChange={(e) => setFormData({ ...formData, wallet_address: e.target.value })}
                  placeholder="0x..."
                  required
                />
              </div>

              <div className="deployment-info">
                <p><strong>What happens next:</strong></p>
                <ul>
                  <li>✓ New API endpoint created</li>
                  <li>✓ Token launched on Flaunch</li>
                  <li>✓ x402 payment enabled</li>
                  <li>✓ Anyone can call your chained workflow</li>
                </ul>
              </div>

              <div className="modal-actions">
                <button type="button" onClick={onClose} className="cancel-btn">
                  [ CANCEL ]
                </button>
                <button type="submit" className="save-btn" disabled={deploying}>
                  {deploying ? '[ DEPLOYING... ]' : '[ DEPLOY NOW ]'}
                </button>
              </div>
            </form>
          ) : (
            <div className="deployment-status">
              {deploymentStatus.success ? (
                <>
                  <h3 style={{ color: 'var(--terminal-green)' }}>✓ DEPLOYMENT INITIATED</h3>
                  <p>{deploymentStatus.message}</p>

                  {deploymentStatus.completed ? (
                    <>
                      <div className="success-details">
                        <div className="detail-row">
                          <span className="label">API ENDPOINT:</span>
                          <span className="value">{deploymentStatus.apiUrl}</span>
                        </div>
                        <div className="detail-row">
                          <span className="label">TOKEN:</span>
                          <span className="value">{deploymentStatus.tokenAddress?.slice(0, 10)}...</span>
                        </div>
                      </div>

                      <div className="action-buttons">
                        <a
                          href={deploymentStatus.flaunchLink}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="link-btn"
                        >
                          [ VIEW ON FLAUNCH ]
                        </a>
                        <button onClick={onClose} className="save-btn">
                          [ CLOSE ]
                        </button>
                      </div>
                    </>
                  ) : deploymentStatus.timeout ? (
                    <p style={{ color: '#ffaa00' }}>Deployment taking longer than expected. Check back soon!</p>
                  ) : (
                    <div className="loading-animation">
                      <p>⏳ Launching token on Flaunch...</p>
                      <p style={{ fontSize: '0.9rem', color: 'var(--terminal-dim)' }}>This may take 30-60 seconds</p>
                    </div>
                  )}
                </>
              ) : (
                <>
                  <h3 style={{ color: '#ff0000' }}>✗ DEPLOYMENT FAILED</h3>
                  <p style={{ color: '#ff0000' }}>{deploymentStatus.error}</p>
                  <button onClick={onClose} className="cancel-btn">
                    [ CLOSE ]
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Node Configuration Modal Component
function NodeConfigModal({ node, schema, onSave, onClose }) {
  const [parameters, setParameters] = useState(node.parameters || {});

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave(parameters);
  };

  const getInputFields = () => {
    const fields = [];

    if (schema?.input_format?.query_params) {
      Object.entries(schema.input_format.query_params).forEach(([name, spec]) => {
        fields.push({
          name,
          type: spec.type || 'string',
          required: spec.required || false,
          description: spec.description || ''
        });
      });
    }

    if (schema?.input_format?.body?.properties) {
      Object.entries(schema.input_format.body.properties).forEach(([name, spec]) => {
        fields.push({
          name,
          type: spec.type || 'string',
          required: spec.required || false,
          description: spec.description || ''
        });
      });
    }

    if (fields.length === 0) {
      // Generic input field
      fields.push({ name: 'input', type: 'string', required: false, description: '' });
    }

    return fields;
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="config-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span>CONFIGURE NODE: {node.api.name}</span>
          <button className="close-btn" onClick={onClose}>X</button>
        </div>

        <div className="modal-body">
          <form onSubmit={handleSubmit}>
            <p className="modal-hint">&gt;&gt; SET INPUT PARAMETERS (LEAVE EMPTY TO USE CONNECTIONS)</p>

            {getInputFields().map((field) => (
              <div key={field.name} className="form-field">
                <label>
                  {field.name}
                  {field.required && <span className="required">*</span>}
                </label>
                {field.description && (
                  <div className="field-description">{field.description}</div>
                )}
                <input
                  type={field.type === 'number' ? 'number' : 'text'}
                  value={parameters[field.name] || ''}
                  onChange={(e) => setParameters({
                    ...parameters,
                    [field.name]: e.target.value
                  })}
                  placeholder={`Enter ${field.name}...`}
                />
              </div>
            ))}

            <div className="modal-actions">
              <button type="button" onClick={onClose} className="cancel-btn">
                [ CANCEL ]
              </button>
              <button type="submit" className="save-btn">
                [ SAVE ]
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

// Connection Mapping Modal Component
function ConnectionMappingModal({ connection, nodes, apiSchemas, onSave, onDelete, onClose }) {
  const fromNode = nodes.find(n => n.id === connection.from.nodeId);
  const toNode = nodes.find(n => n.id === connection.to.nodeId);

  const fromSchema = apiSchemas[fromNode?.api.endpoint] || {};
  const toSchema = apiSchemas[toNode?.api.endpoint] || {};

  // Get available output fields from source node
  const availableOutputs = fromNode?.outputs || [];

  // Get available input fields from target node
  const availableInputs = toNode?.inputs || [];

  const [mappings, setMappings] = useState(connection.fieldMappings || []);

  const addMapping = () => {
    setMappings([...mappings, { from: '', to: '' }]);
  };

  const removeMapping = (index) => {
    setMappings(mappings.filter((_, i) => i !== index));
  };

  const updateMapping = (index, field, value) => {
    const updated = [...mappings];
    updated[index][field] = value;
    setMappings(updated);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    // Filter out incomplete mappings
    const validMappings = mappings.filter(m => m.from && m.to);
    onSave(validMappings);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="mapping-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span>CONFIGURE CONNECTION: {fromNode?.api.name} → {toNode?.api.name}</span>
          <button className="close-btn" onClick={onClose}>X</button>
        </div>

        <div className="modal-body">
          <form onSubmit={handleSubmit}>
            <p className="modal-hint">&gt;&gt; MAP OUTPUT FIELDS TO INPUT FIELDS</p>

            <div className="mapping-list">
              {mappings.length === 0 ? (
                <div className="no-mappings">
                  <p>No field mappings configured.</p>
                  <p>Click [+ ADD MAPPING] to connect fields.</p>
                </div>
              ) : (
                mappings.map((mapping, index) => (
                  <div key={index} className="mapping-row">
                    <div className="mapping-field">
                      <label>From (Output):</label>
                      <select
                        value={mapping.from}
                        onChange={(e) => updateMapping(index, 'from', e.target.value)}
                        required
                      >
                        <option value="">Select output field...</option>
                        {availableOutputs.map(output => (
                          <option key={output} value={output}>{output}</option>
                        ))}
                      </select>
                    </div>

                    <div className="mapping-arrow">→</div>

                    <div className="mapping-field">
                      <label>To (Input):</label>
                      <select
                        value={mapping.to}
                        onChange={(e) => updateMapping(index, 'to', e.target.value)}
                        required
                      >
                        <option value="">Select input field...</option>
                        {availableInputs.map(input => (
                          <option key={input} value={input}>{input}</option>
                        ))}
                      </select>
                    </div>

                    <button
                      type="button"
                      onClick={() => removeMapping(index)}
                      className="remove-btn"
                      title="Remove mapping"
                    >
                      X
                    </button>
                  </div>
                ))
              )}
            </div>

            <button
              type="button"
              onClick={addMapping}
              className="add-mapping-btn"
            >
              [ + ADD MAPPING ]
            </button>

            <div className="modal-actions">
              <button
                type="button"
                onClick={onDelete}
                className="delete-btn"
              >
                [ DELETE CONNECTION ]
              </button>
              <div style={{ flex: 1 }}></div>
              <button type="button" onClick={onClose} className="cancel-btn">
                [ CANCEL ]
              </button>
              <button type="submit" className="save-btn">
                [ SAVE MAPPINGS ]
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

// Execution Results Modal Component
function ExecutionResultsModal({ results, onClose }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="results-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span>WORKFLOW EXECUTION RESULTS</span>
          <button className="close-btn" onClick={onClose}>X</button>
        </div>

        <div className="modal-body">
          <div className="results-summary">
            <div className="summary-item">
              <span className="label">STATUS:</span>
              <span className={`value ${results.success ? 'success' : 'error'}`}>
                {results.success ? '[SUCCESS]' : '[FAILED]'}
              </span>
            </div>
            <div className="summary-item">
              <span className="label">NODES EXECUTED:</span>
              <span className="value">{results.nodes_executed || 0}</span>
            </div>
            <div className="summary-item">
              <span className="label">TOTAL COST:</span>
              <span className="value">${results.total_cost?.toFixed(10) || '0.0000000000'}</span>
            </div>
          </div>

          <div className="execution-log">
            <h3>EXECUTION LOG</h3>
            {results.execution_log?.map((log, idx) => (
              <div key={idx} className="log-entry">
                <div className="log-header">
                  <span className="node-id">[{log.node_id}]</span>
                  <span className="endpoint">{log.endpoint}</span>
                  <span className={`status ${log.status}`}>[{log.status.toUpperCase()}]</span>
                </div>

                {log.inputs && Object.keys(log.inputs).length > 0 && (
                  <div className="log-section">
                    <div className="section-label">INPUTS:</div>
                    <pre>{JSON.stringify(log.inputs, null, 2)}</pre>
                  </div>
                )}

                {log.output && (
                  <div className="log-section">
                    <div className="section-label">OUTPUT:</div>
                    <pre>{JSON.stringify(log.output, null, 2)}</pre>
                  </div>
                )}

                {log.error && (
                  <div className="log-section error">
                    <div className="section-label">ERROR:</div>
                    <pre>{log.error}</pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default WorkflowBuilder;
