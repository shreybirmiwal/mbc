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

  useEffect(() => {
    fetchApis();
  }, []);

  const fetchApis = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/admin/list-apis`);
      const data = await response.json();
      const apisList = data.apis || [];
      setApis(apisList);

      // Fetch pricing details for each API
      const detailsPromises = apisList.map(async (api) => {
        try {
          const endpoint = api.endpoint.replace(/^\//, '');
          const infoResponse = await fetch(`${API_BASE_URL}/admin/api-info/${endpoint}`);
          if (infoResponse.ok) {
            const info = await infoResponse.json();
            return { endpoint: api.endpoint, info };
          }
        } catch (error) {
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
    }
  };

  const addNodeToCanvas = (api) => {
    const newNode = {
      id: `node-${Date.now()}`,
      api: api,
      position: { 
        x: 100 + (nodes.length * 50) % 400, 
        y: 100 + Math.floor(nodes.length / 5) * 200 
      },
      inputs: ['input'],
      outputs: ['output']
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

  const handleOutputClick = (nodeId, outputIndex) => {
    if (connecting) {
      // Complete the connection
      if (connecting.nodeId !== nodeId) {
        const newConnection = {
          id: `conn-${Date.now()}`,
          from: { nodeId: connecting.nodeId, output: connecting.outputIndex },
          to: { nodeId, input: 0 }
        };
        setConnections([...connections, newConnection]);
      }
      setConnecting(null);
    } else {
      // Start a connection
      setConnecting({ nodeId, outputIndex });
    }
  };

  const handleInputClick = (nodeId, inputIndex) => {
    if (connecting && connecting.nodeId !== nodeId) {
      const newConnection = {
        id: `conn-${Date.now()}`,
        from: { nodeId: connecting.nodeId, output: connecting.outputIndex },
        to: { nodeId, input: inputIndex }
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

    // For now, just show the workflow structure
    const workflowData = {
      nodes: nodes.map(n => ({
        id: n.id,
        api: n.api.endpoint,
        position: n.position
      })),
      connections: connections.map(c => ({
        from: c.from.nodeId,
        to: c.to.nodeId
      })),
      totalPrice: calculateTotalPrice()
    };

    console.log('Executing workflow:', workflowData);
    alert(`>> WORKFLOW READY\n>> NODES: ${nodes.length}\n>> CONNECTIONS: ${connections.length}\n>> TOTAL COST: ${formatCurrency(calculateTotalPrice())}`);
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
                <p>>> NO APIS AVAILABLE</p>
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
                      {node.inputs.map((input, idx) => (
                        <div
                          key={`input-${idx}`}
                          className="port input-port"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleInputClick(node.id, idx);
                          }}
                          title="Input"
                        >
                          <div className="port-dot"></div>
                          <span className="port-label">IN</span>
                        </div>
                      ))}
                    </div>
                    
                    {/* Output ports */}
                    <div className="output-ports">
                      {node.outputs.map((output, idx) => (
                        <div
                          key={`output-${idx}`}
                          className="port output-port"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleOutputClick(node.id, idx);
                          }}
                          title="Output"
                        >
                          <span className="port-label">OUT</span>
                          <div className="port-dot"></div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}

          {nodes.length === 0 && (
            <div className="canvas-empty-state">
              <p>>> CANVAS EMPTY</p>
              <p>>> SELECT APIS FROM THE LEFT PANEL</p>
              <p>>> CLICK TO ADD NODES</p>
            </div>
          )}
        </div>
      </div>

      {/* Control Panel */}
      <div className="workflow-controls">
        <button onClick={executeWorkflow} className="control-btn execute-btn">
          [ EXECUTE WORKFLOW ]
        </button>
        <button onClick={clearCanvas} className="control-btn clear-btn">
          [ CLEAR CANVAS ]
        </button>
        {connecting && (
          <span className="connecting-indicator">
            >> CONNECTING... (CLICK INPUT PORT TO COMPLETE)
          </span>
        )}
      </div>
    </div>
  );
}

export default WorkflowBuilder;
