import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------
const getWsUrl = () => {
  const loc = window.location;
  const protocol = loc.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${loc.host}/ws`;
};

const API_URL = '/api/state';
const HISTORY_URL = '/api/history';
const RECONNECT_DELAY_MS = 3000;

// ---------------------------------------------------------------------------
// RN Type badge
// ---------------------------------------------------------------------------
function TypeBadge({ type }) {
  if (!type) return <span className="type-badge type-unknown">—</span>;
  const cls =
    type === 'NR'     ? 'type-nr'     :
    type === 'LTE'    ? 'type-lte'    :
    type === 'NR+LTE' ? 'type-nrlte'  : 'type-unknown';
  return <span className={`type-badge ${cls}`}>{type}</span>;
}

// ---------------------------------------------------------------------------
// CU Accordion group
// ---------------------------------------------------------------------------
function CuGroup({ cuName, nodes, defaultExpanded = true, sortCol, sortAsc, onSort }) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const healthy = nodes.filter(n => n.node_state === 'HEALTHY').length;
  const oos     = nodes.filter(n => n.node_state === 'OOS').length;
  const reboot  = nodes.filter(n => n.node_state === 'REBOOTED').length;

  const sortIndicator = (col) => {
    if (sortCol !== col) return '';
    return sortAsc ? ' ▲' : ' ▼';
  };

  return (
    <div className="cu-group">
      {/* CU header row — click to expand/collapse */}
      <div
        className="cu-group-header"
        onClick={() => setExpanded(e => !e)}
        role="button"
        aria-expanded={expanded}
      >
        <span className="cu-expand-arrow">{expanded ? '▾' : '▸'}</span>
        <span className="cu-group-name">{cuName}</span>
        <span className="cu-group-meta">
          <span className="cu-badge total">{nodes.length} RNs</span>
          {healthy > 0 && <span className="cu-badge healthy">{healthy} healthy</span>}
          {oos     > 0 && <span className="cu-badge oos">{oos} OOS</span>}
          {reboot  > 0 && <span className="cu-badge reboot">{reboot} rebooted</span>}
        </span>
      </div>

      {expanded && (
        <table className="cu-table">
          <thead>
            <tr>
              <th onClick={() => onSort('rn_name')}>RN Name{sortIndicator('rn_name')}</th>
              <th onClick={() => onSort('rn_type')}>Type{sortIndicator('rn_type')}</th>
              <th onClick={() => onSort('pci')}>PCI{sortIndicator('pci')}</th>
              <th onClick={() => onSort('ip')}>IP{sortIndicator('ip')}</th>
              <th onClick={() => onSort('uptime_seconds')}>Uptime{sortIndicator('uptime_seconds')}</th>
              <th onClick={() => onSort('node_state')}>State{sortIndicator('node_state')}</th>
              <th onClick={() => onSort('reboot_count')}>Reboots{sortIndicator('reboot_count')}</th>
              <th onClick={() => onSort('last_seen')}>Last Seen{sortIndicator('last_seen')}</th>
            </tr>
          </thead>
          <tbody>
            {nodes.map(n => (
              <tr key={`${n.cu_name}-${n.rn_id}`}>
                <td>{n.rn_name}</td>
                <td><TypeBadge type={n.rn_type} /></td>
                <td>{n.pci || '—'}</td>
                <td className="ip-cell">{n.ip || '—'}</td>
                <td>{n.uptime_display}</td>
                <td>
                  <span className={`state-badge ${n.node_state}`}>{n.node_state}</span>
                </td>
                <td>
                  <span className={`reboot-count ${n.reboot_count > 0 ? 'has-reboots' : ''}`}>
                    {n.reboot_count}
                  </span>
                </td>
                <td>{n.last_seen ? new Date(n.last_seen).toLocaleTimeString() : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main App
// ---------------------------------------------------------------------------
function App() {
  const [nodes, setNodes]               = useState([]);
  const [events, setEvents]             = useState([]);
  const [history, setHistory]           = useState([]);
  const [selectedNodeId, setSelectedNodeId] = useState('ALL');
  const [newCuIp, setNewCuIp]           = useState('');
  const [newCuName, setNewCuName]       = useState('');
  const [discoverStatus, setDiscoverStatus] = useState('');
  const [discoverError, setDiscoverError]   = useState('');
  const [isDiscovering, setIsDiscovering]   = useState(false);
  const [deleteCuIp, setDeleteCuIp]     = useState('');
  const [deleteStatus, setDeleteStatus] = useState('');
  const [deleteError, setDeleteError]   = useState('');
  const [isDeletingCu, setIsDeletingCu] = useState(false);
  const [connected, setConnected]       = useState(false);
  const [filter, setFilter]             = useState('');
  const [stateFilter, setStateFilter]   = useState('ALL');
  const [sortCol, setSortCol]           = useState('rn_name');
  const [sortAsc, setSortAsc]           = useState(true);

  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);

  // -----------------------------------------------------------------------
  // WebSocket lifecycle
  // -----------------------------------------------------------------------
  const connectWs = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;
    const ws = new WebSocket(getWsUrl());
    wsRef.current = ws;

    ws.onopen = () => { setConnected(true); };
    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        if (data.type === 'state_update') {
          setNodes(data.nodes || []);
          setEvents(data.recent_events || []);
        }
      } catch {}
    };
    ws.onclose = () => {
      setConnected(false);
      reconnectTimer.current = setTimeout(connectWs, RECONNECT_DELAY_MS);
    };
    ws.onerror = () => { ws.close(); };
  }, []);

  useEffect(() => {
    connectWs();
    return () => {
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connectWs]);

  useEffect(() => {
    if (nodes.length === 0) {
      fetch(API_URL).then(r => r.json()).then(data => {
        if (data.nodes) setNodes(data.nodes);
      }).catch(() => {});
    }
  }, []);

  const refreshHistory = useCallback((nodeId = 'ALL') => {
    const url = nodeId === 'ALL'
      ? HISTORY_URL
      : `${HISTORY_URL}?rn_id=${encodeURIComponent(nodeId)}`;
    fetch(url).then(r => r.json()).then(data => {
      if (Array.isArray(data.history)) setHistory(data.history);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    refreshHistory(selectedNodeId);
    const timer = setInterval(() => refreshHistory(selectedNodeId), 60000);
    return () => clearInterval(timer);
  }, [refreshHistory, selectedNodeId]);

  // -----------------------------------------------------------------------
  // CU Management
  // -----------------------------------------------------------------------
  const handleDiscoverCu = async (e) => {
    e.preventDefault();
    setDiscoverStatus(''); setDiscoverError('');
    const ip = newCuIp.trim();
    if (!ip) { setDiscoverError('Enter a CU IP address.'); return; }
    setIsDiscovering(true);
    try {
      const response = await fetch('/api/cus/discover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ip, name: newCuName.trim() || null }),
      });
      const ct = response.headers.get('content-type') || '';
      const data = ct.includes('application/json') ? await response.json() : { detail: await response.text() };
      if (!response.ok) throw new Error(data.detail || 'Unable to discover CU');
      if (Array.isArray(data.nodes)) setNodes(data.nodes);
      refreshHistory(selectedNodeId);
      setDiscoverStatus(data.message || 'CU added successfully.');
      setNewCuIp(''); setNewCuName(''); setSelectedNodeId('ALL');
    } catch (err) {
      setDiscoverError(err.message || 'Discovery failed.');
    } finally {
      setIsDiscovering(false);
    }
  };

  const handleDeleteCu = async (e) => {
    e.preventDefault();
    setDeleteStatus(''); setDeleteError('');
    const ip = deleteCuIp.trim();
    if (!ip) { setDeleteError('Select a CU to delete.'); return; }
    setIsDeletingCu(true);
    try {
      const response = await fetch('/api/cus', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ip }),
      });
      const ct = response.headers.get('content-type') || '';
      const data = ct.includes('application/json') ? await response.json() : { detail: await response.text() };
      if (!response.ok) throw new Error(data.detail || 'Unable to delete CU');
      if (Array.isArray(data.nodes)) setNodes(data.nodes);
      refreshHistory(selectedNodeId);
      setDeleteStatus(data.message || 'CU removed successfully.');
      setDeleteCuIp(''); setSelectedNodeId('ALL');
    } catch (err) {
      setDeleteError(err.message || 'Delete failed.');
    } finally {
      setIsDeletingCu(false);
    }
  };

  // -----------------------------------------------------------------------
  // Derived data
  // -----------------------------------------------------------------------
  const sortedFilteredNodes = useMemo(() => {
    let result = nodes;
    if (filter) {
      const q = filter.toLowerCase();
      result = result.filter(n =>
        n.cu_name.toLowerCase().includes(q) ||
        n.rn_name.toLowerCase().includes(q) ||
        (n.ip || '').includes(q) ||
        (n.rn_type || '').toLowerCase().includes(q)
      );
    }
    if (stateFilter !== 'ALL') {
      result = result.filter(n => n.node_state === stateFilter);
    }
    return [...result].sort((a, b) => {
      let va = a[sortCol], vb = b[sortCol];
      if (typeof va === 'string') va = va.toLowerCase();
      if (typeof vb === 'string') vb = vb.toLowerCase();
      if (va < vb) return sortAsc ? -1 : 1;
      if (va > vb) return sortAsc ? 1 : -1;
      return 0;
    });
  }, [nodes, filter, stateFilter, sortCol, sortAsc]);

  // Group sorted nodes by CU
  const groupedByCu = useMemo(() => {
    const map = new Map();
    for (const n of sortedFilteredNodes) {
      if (!map.has(n.cu_name)) map.set(n.cu_name, []);
      map.get(n.cu_name).push(n);
    }
    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [sortedFilteredNodes]);

  const stats = useMemo(() => {
    const total   = nodes.length;
    const healthy = nodes.filter(n => n.node_state === 'HEALTHY').length;
    const reboots = nodes.reduce((s, n) => s + n.reboot_count, 0);
    const cus     = new Set(nodes.map(n => n.cu_name)).size;
    return { total, healthy, reboots, cus };
  }, [nodes]);

  const historyBars = useMemo(() => {
    const buckets = new Map();
    history.forEach(entry => {
      const ts = new Date(entry.timestamp);
      if (Number.isNaN(ts.getTime())) return;
      const key = new Date(ts); key.setMinutes(0, 0, 0);
      const k = key.toISOString();
      const cur = buckets.get(k) || { label: '', count: 0, ts: key };
      cur.count += 1;
      cur.label = key.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      buckets.set(k, cur);
    });
    return Array.from(buckets.values())
      .sort((a, b) => a.ts - b.ts)
      .slice(-8)
      .map(item => ({ ...item, height: Math.min(72, Math.max(12, item.count * 12)) }));
  }, [history]);

  const nodeOptions = useMemo(() =>
    [...nodes]
      .sort((a, b) => `${a.cu_name}-${a.rn_name}`.localeCompare(`${b.cu_name}-${b.rn_name}`))
      .map(n => ({ value: `${n.cu_name}-${n.rn_id}`, label: `${n.cu_name} / ${n.rn_name}` })),
  [nodes]);

  const cuOptions = useMemo(() => {
    const seen = new Set();
    return nodes
      .filter(n => n.cu_ip && !seen.has(n.cu_ip) && seen.add(n.cu_ip))
      .sort((a, b) => a.cu_name.localeCompare(b.cu_name))
      .map(n => ({ value: n.cu_ip, label: `${n.cu_name} (${n.cu_ip})` }));
  }, [nodes]);

  const selectedNodeLabel = useMemo(() => {
    if (selectedNodeId === 'ALL') return 'All nodes';
    const node = nodes.find(n => `${n.cu_name}-${n.rn_id}` === selectedNodeId);
    return node ? `${node.cu_name} / ${node.rn_name}` : 'Selected node';
  }, [nodes, selectedNodeId]);

  const selectedHistoryRows = useMemo(() => history.slice(0, 8), [history]);

  const handleSort = (col) => {
    if (sortCol === col) setSortAsc(a => !a);
    else { setSortCol(col); setSortAsc(true); }
  };

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------
  return (
    <React.Fragment>
      {/* Header */}
      <header className="header">
        <div>
          <h1>Airspan Lab Monitor</h1>
          <span className="subtitle">Real-time RN status dashboard</span>
        </div>
        <div className="conn-badge">
          <span className={`conn-dot ${connected ? 'connected' : 'disconnected'}`} />
          {connected ? 'Live' : 'Reconnecting…'}
        </div>
      </header>

      {/* CU management */}
      <form className="discover-bar" onSubmit={handleDiscoverCu}>
        <input type="text" placeholder="Enter CU IP" value={newCuIp}
          onChange={e => setNewCuIp(e.target.value)} />
        <input type="text" placeholder="Optional CU name" value={newCuName}
          onChange={e => setNewCuName(e.target.value)} />
        <button type="submit" disabled={isDiscovering}>
          {isDiscovering ? 'Discovering...' : 'Add CU'}
        </button>
      </form>
      {discoverStatus && <div className="discover-message success">{discoverStatus}</div>}
      {discoverError  && <div className="discover-message error">{discoverError}</div>}

      <form className="delete-bar" onSubmit={handleDeleteCu}>
        <select value={deleteCuIp} onChange={e => setDeleteCuIp(e.target.value)}>
          <option value="">Delete a monitored CU</option>
          {cuOptions.map(cu => (
            <option key={cu.value} value={cu.value}>{cu.label}</option>
          ))}
        </select>
        <button type="submit" className="danger" disabled={isDeletingCu || cuOptions.length === 0}>
          {isDeletingCu ? 'Deleting...' : 'Delete CU'}
        </button>
      </form>
      {deleteStatus && <div className="discover-message success">{deleteStatus}</div>}
      {deleteError  && <div className="discover-message error">{deleteError}</div>}

      {/* Summary stats */}
      <div className="stats-row">
        <div className="stat-card">
          <div className="label">Control Units</div>
          <div className="value">{stats.cus}</div>
        </div>
        <div className="stat-card">
          <div className="label">Radio Nodes</div>
          <div className="value">{stats.total}</div>
        </div>
        <div className="stat-card">
          <div className="label">Healthy</div>
          <div className="value" style={{ color: 'var(--state-healthy)' }}>{stats.healthy}</div>
        </div>
        <div className="stat-card">
          <div className="label">Total Reboots</div>
          <div className="value" style={{ color: stats.reboots > 0 ? 'var(--state-rebooted)' : 'inherit' }}>
            {stats.reboots}
          </div>
        </div>
      </div>

      {/* History graph */}
      <div className="history-panel">
        <div className="history-header">
          <div>
            <h2>Status History</h2>
            <p>Recent state-change volume by hour</p>
          </div>
          <div className="history-controls">
            <select value={selectedNodeId} onChange={e => setSelectedNodeId(e.target.value)}>
              <option value="ALL">All nodes</option>
              {nodeOptions.map(n => (
                <option key={n.value} value={n.value}>{n.label}</option>
              ))}
            </select>
            <span className="history-count">{selectedNodeLabel}</span>
          </div>
        </div>
        {historyBars.length === 0 ? (
          <div className="history-empty">Waiting for history data...</div>
        ) : (
          <div className="history-chart" aria-label="Status history chart">
            {historyBars.map(bar => (
              <div className="history-bar-group" key={bar.ts.toISOString()}>
                <div className="history-bar" style={{ height: `${bar.height}px` }} />
                <span>{bar.label}</span>
                <small>{bar.count}</small>
              </div>
            ))}
          </div>
        )}
        <div className="history-footer">{history.length} records total</div>
        {selectedNodeId !== 'ALL' && selectedHistoryRows.length > 0 && (
          <div className="history-list">
            {selectedHistoryRows.map(entry => (
              <div className="history-list-row" key={`${entry.timestamp}-${entry.rn_id}-${entry.new_status}`}>
                <span>{entry.timestamp ? new Date(entry.timestamp).toLocaleString() : '—'}</span>
                <span>{entry.old_status || '—'} → {entry.new_status}</span>
                <span>{entry.rn_id}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="filter-bar">
        <input type="text" placeholder="Search CU, RN, IP, or type…"
          value={filter} onChange={e => setFilter(e.target.value)} />
        <select value={stateFilter} onChange={e => setStateFilter(e.target.value)}>
          <option value="ALL">All States</option>
          <option value="HEALTHY">Healthy</option>
          <option value="REBOOTED">Rebooted</option>
          <option value="OOS">OOS</option>
        </select>
      </div>

      {/* CU-grouped node accordion */}
      <div className="table-container">
        {groupedByCu.length === 0 ? (
          <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '40px' }}>
            {nodes.length === 0 ? 'Waiting for first poll cycle…' : 'No nodes match the filter'}
          </div>
        ) : (
          groupedByCu.map(([cuName, cuNodes]) => (
            <CuGroup
              key={cuName}
              cuName={cuName}
              nodes={cuNodes}
              sortCol={sortCol}
              sortAsc={sortAsc}
              onSort={handleSort}
            />
          ))
        )}
      </div>

      {/* Recent events */}
      {events.length > 0 && (
        <div className="events-panel">
          <h2>Recent Events</h2>
          {events.slice().reverse().map((e, i) => (
            <div className="event-item" key={i}>
              <span className="event-time">
                {e.timestamp ? new Date(e.timestamp).toLocaleString() : '—'}
              </span>
              <span className="event-type">{e.event_type}</span>
              <span>{e.cu_name} / {e.rn_name}</span>
              <span className="event-detail">{e.details}</span>
            </div>
          ))}
        </div>
      )}
    </React.Fragment>
  );
}

export default App;
