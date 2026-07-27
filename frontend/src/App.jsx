import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------
// In Vite dev, window.location.host is 3000, but API is proxied.
const getWsUrl = () => {
  const loc = window.location;
  const protocol = loc.protocol === 'https:' ? 'wss:' : 'ws:';
  // If proxy is active, the websocket is also proxied to the same host/port.
  return `${protocol}//${loc.host}/ws`;
};

const API_URL = '/api/state';
const RECONNECT_DELAY_MS = 3000;

function App() {
  const [nodes, setNodes] = useState([]);
  const [events, setEvents] = useState([]);
  const [connected, setConnected] = useState(false);
  const [filter, setFilter] = useState('');
  const [stateFilter, setStateFilter] = useState('ALL');
  const [sortCol, setSortCol] = useState('rn_name');
  const [sortAsc, setSortAsc] = useState(true);
  
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);

  // -----------------------------------------------------------------------
  // WebSocket lifecycle
  // -----------------------------------------------------------------------
  const connectWs = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(getWsUrl());
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      console.log('[WS] Connected');
    };

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        if (data.type === 'state_update') {
          setNodes(data.nodes || []);
          setEvents(data.recent_events || []);
        }
      } catch (err) {
        console.error('[WS] Parse error', err);
      }
    };

    ws.onclose = () => {
      setConnected(false);
      console.log('[WS] Disconnected — retrying in', RECONNECT_DELAY_MS, 'ms');
      reconnectTimer.current = setTimeout(connectWs, RECONNECT_DELAY_MS);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, []);

  useEffect(() => {
    connectWs();
    return () => {
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connectWs]);

  // -----------------------------------------------------------------------
  // Fallback: if WS never connects, try REST once.
  // -----------------------------------------------------------------------
  useEffect(() => {
    if (nodes.length === 0) {
      fetch(API_URL)
        .then((r) => r.json())
        .then((data) => {
          if (data.nodes) setNodes(data.nodes);
        })
        .catch(() => {});
    }
  }, []);

  // -----------------------------------------------------------------------
  // Derived data — filtering & sorting
  // -----------------------------------------------------------------------
  const filteredNodes = useMemo(() => {
    let result = nodes;
    if (filter) {
      const q = filter.toLowerCase();
      result = result.filter(
        (n) =>
          n.cu_name.toLowerCase().includes(q) ||
          n.rn_name.toLowerCase().includes(q) ||
          n.ip.includes(q)
      );
    }
    if (stateFilter !== 'ALL') {
      result = result.filter((n) => n.node_state === stateFilter);
    }
    // Sort
    result = [...result].sort((a, b) => {
      let va = a[sortCol];
      let vb = b[sortCol];
      if (typeof va === 'string') va = va.toLowerCase();
      if (typeof vb === 'string') vb = vb.toLowerCase();
      if (va < vb) return sortAsc ? -1 : 1;
      if (va > vb) return sortAsc ? 1 : -1;
      return 0;
    });
    return result;
  }, [nodes, filter, stateFilter, sortCol, sortAsc]);

  // -----------------------------------------------------------------------
  // Summary stats
  // -----------------------------------------------------------------------
  const stats = useMemo(() => {
    const total = nodes.length;
    const healthy = nodes.filter((n) => n.node_state === 'HEALTHY').length;
    const reboots = nodes.reduce((s, n) => s + n.reboot_count, 0);
    const cus = new Set(nodes.map((n) => n.cu_name)).size;
    return { total, healthy, reboots, cus };
  }, [nodes]);

  // -----------------------------------------------------------------------
  // Sorting handler
  // -----------------------------------------------------------------------
  const handleSort = (col) => {
    if (sortCol === col) {
      setSortAsc(!sortAsc);
    } else {
      setSortCol(col);
      setSortAsc(true);
    }
  };

  const sortIndicator = (col) => {
    if (sortCol !== col) return '';
    return sortAsc ? ' ▲' : ' ▼';
  };

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

      {/* Filters */}
      <div className="filter-bar">
        <input
          type="text"
          placeholder="Search CU, RN, or IP…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <select value={stateFilter} onChange={(e) => setStateFilter(e.target.value)}>
          <option value="ALL">All States</option>
          <option value="HEALTHY">Healthy</option>
          <option value="REBOOTED">Rebooted</option>
          <option value="OOS">OOS</option>
        </select>
      </div>

      {/* Node table */}
      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th onClick={() => handleSort('cu_name')}>CU Name{sortIndicator('cu_name')}</th>
              <th onClick={() => handleSort('rn_name')}>RN Name{sortIndicator('rn_name')}</th>
              <th onClick={() => handleSort('ip')}>IP{sortIndicator('ip')}</th>
              <th onClick={() => handleSort('pci')}>PCI{sortIndicator('pci')}</th>
              <th onClick={() => handleSort('uptime_seconds')}>Uptime{sortIndicator('uptime_seconds')}</th>
              <th onClick={() => handleSort('node_state')}>State{sortIndicator('node_state')}</th>
              <th onClick={() => handleSort('reboot_count')}>Reboots{sortIndicator('reboot_count')}</th>
              <th onClick={() => handleSort('last_seen')}>Last Seen{sortIndicator('last_seen')}</th>
            </tr>
          </thead>
          <tbody>
            {filteredNodes.length === 0 ? (
              <tr>
                <td colSpan="8" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '32px' }}>
                  {nodes.length === 0 ? 'Waiting for first poll cycle…' : 'No nodes match the filter'}
                </td>
              </tr>
            ) : (
              filteredNodes.map((n) => (
                <tr key={`${n.cu_name}-${n.rn_id}`}>
                  <td>{n.cu_name}</td>
                  <td>{n.rn_name}</td>
                  <td>{n.ip}</td>
                  <td>{n.pci}</td>
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
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Recent events */}
      {events.length > 0 && (
        <div className="events-panel">
          <h2>Recent Events</h2>
          {events
            .slice()
            .reverse()
            .map((e, i) => (
              <div className="event-item" key={i}>
                <span className="event-time">
                  {e.timestamp ? new Date(e.timestamp).toLocaleString() : '—'}
                </span>
                <span className="event-type">{e.event_type}</span>
                <span>
                  {e.cu_name} / {e.rn_name}
                </span>
                <span className="event-detail">{e.details}</span>
              </div>
            ))}
        </div>
      )}
    </React.Fragment>
  );
}

export default App;
