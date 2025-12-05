import React, { useState, useRef, useEffect } from 'react';
import './WorkflowBuilder.css';

const API_BASE_URL = 'http://127.0.0.1:5000';

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
  const [executionResults, setExecutionResults] = useState(null);
  const [executing, setExecuting] = useState(false);

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

  const handleOutputClick = (nodeId, outputName) => {
    if (connecting) {
      // Can't connect output to output, cancel
      setConnecting(null);
    } else {
      // Start a connection
      setConnecting({ nodeId, outputName });
    }
  };

  const handleInputClick = (nodeId, inputName) => {
    if (connecting && connecting.nodeId !== nodeId) {
      const newConnection = {
        id: `conn-${Date.now()}`,
        from: { nodeId: connecting.nodeId, output: connecting.outputName },
        to: { nodeId, input: inputName }
      };
      setConnections([...connections, newConnection]);
      setConnecting(null);
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
          from: c.from,
          to: c.to
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

              // Calculate midpoint for the label
              const midX = (x1 + x2) / 2;
              const midY = (y1 + y2) / 2;

              return (
                <g key={conn.id}>
                  <line
                    x1={x1}
                    y1={y1}
                    x2={x2}
                    y2={y2}
                    stroke="var(--terminal-green)"
                    strokeWidth="2"
                    strokeDasharray="5,5"
                  />
                  <circle
                    cx={midX}
                    cy={midY}
                    r="8"
                    fill="var(--terminal-green)"
                    onClick={() => removeConnection(conn.id)}
                    style={{ cursor: 'pointer' }}
                  />
                  <text
                    x={midX}
                    y={midY + 3}
                    fill="#000"
                    fontSize="10"
                    textAnchor="middle"
                    style={{ pointerEvents: 'none', fontWeight: 'bold' }}
                  >
                    X
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
                    {/* Input ports */}
                    <div className="input-ports">
                      {node.inputs.map((inputName, idx) => (
                        <div
                          key={`input-${idx}`}
                          className="port input-port"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleInputClick(node.id, inputName);
                          }}
                          title={`Input: ${inputName}`}
                        >
                          <div className="port-dot"></div>
                          <span className="port-label">{inputName}</span>
                        </div>
                      ))}
                    </div>

                    {/* Output ports */}
                    <div className="output-ports">
                      {node.outputs.map((outputName, idx) => (
                        <div
                          key={`output-${idx}`}
                          className="port output-port"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleOutputClick(node.id, outputName);
                          }}
                          title={`Output: ${outputName}`}
                        >
                          <span className="port-label">{outputName}</span>
                          <div className="port-dot"></div>
                        </div>
                      ))}
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
          onClick={executeWorkflow}
          className="control-btn execute-btn"
          disabled={executing}
        >
          {executing ? '[ EXECUTING... ]' : '[ EXECUTE WORKFLOW ]'}
        </button>
        <button onClick={clearCanvas} className="control-btn clear-btn">
          [ CLEAR CANVAS ]
        </button>
        {connecting && (
          <span className="connecting-indicator">
            &gt;&gt; CONNECTING... (CLICK INPUT PORT TO COMPLETE)
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

      {/* Execution Results Modal */}
      {executionResults && (
        <ExecutionResultsModal
          results={executionResults}
          onClose={() => setExecutionResults(null)}
        />
      )}
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
