import { useState } from 'react';
import axios from 'axios';
import { Play, Activity, Terminal, BrainCircuit, BarChart3 } from 'lucide-react';
import './index.css';

interface OrchestratorResponse {
  task_id: string;
  iteration: number;
  max_iterations: number;
  user_prompt: string;
  dataset_id: string;
  hypothesis: string;
  strategy_source: string;
  outcome: string;
  reflection_notes: string;
  iteration_log: string[];
  approved: boolean;
}

function App() {
  const [prompt, setPrompt] = useState('Bollinger Band mean reversion with 2-standard-deviation threshold on SPY');
  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState<OrchestratorResponse | null>(null);
  const [error, setError] = useState('');

  const handleRun = async () => {
    setIsRunning(true);
    setError('');
    setResult(null);
    
    try {
      const res = await axios.post('http://localhost:8000/api/run', {
        prompt,
        dataset_id: 'sample_spy_ticks.arrow',
        max_iterations: 2
      });
      setResult(res.data);
    } catch (err: any) {
      setError(err.message || 'Failed to connect to the orchestrator backend.');
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="app-container animate-fade-in">
      <header className="header">
        <h1>HyperTick</h1>
        <p>Distributed Microsecond Backtesting & Simulation Engine</p>
      </header>

      {/* Input Section */}
      <section className="glass-panel" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-blue)' }}>
          <BrainCircuit size={22} />
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)' }}>Strategy Hypothesis</h2>
        </div>
        <div className="input-group">
          <input 
            type="text" 
            className="prompt-input" 
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Describe your quantitative trading strategy..."
            disabled={isRunning}
          />
          <button 
            className={`run-btn ${isRunning ? 'running' : ''}`}
            onClick={handleRun}
            disabled={isRunning}
          >
            {isRunning ? (
              <><Activity size={18} className="animate-spin" /> Synthesizing...</>
            ) : (
              <><Play size={18} fill="currentColor" /> Execute</>
            )}
          </button>
        </div>
        {error && (
          <div style={{
            background: '#fef2f2',
            border: '1px solid #fecaca',
            color: '#b91c1c',
            padding: '12px 16px',
            borderRadius: '10px',
            fontSize: '0.95rem'
          }}>
            {error}
          </div>
        )}
      </section>

      {/* Results Dashboard Grid */}
      <div className="dashboard-grid">
        
        {/* Left Column: Thoughts & Status */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <section className="glass-panel" style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-purple)', marginBottom: '16px' }}>
              <Terminal size={22} />
              <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)' }}>Agent Logs</h2>
            </div>
            
            {result ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {result.iteration_log.map((log, i) => (
                  <div key={i} style={{ 
                    padding: '12px 14px', 
                    background: '#f8fafc', 
                    borderRadius: '8px',
                    border: '1px solid #e2e8f0',
                    borderLeft: `4px solid ${log.includes('evaluator') ? '#ef4444' : '#3b82f6'}`,
                    fontFamily: 'JetBrains Mono',
                    fontSize: '0.88rem',
                    color: '#1e293b',
                    boxShadow: '0 1px 2px rgba(0, 0, 0, 0.02)'
                  }}>
                    {log}
                  </div>
                ))}
                
                <div style={{
                  marginTop: '16px',
                  padding: '14px 16px',
                  background: result.approved ? '#ecfdf5' : '#fff1f2',
                  borderRadius: '10px',
                  border: `1px solid ${result.approved ? '#a7f3d0' : '#ffe4e6'}`
                }}>
                  <h3 style={{
                    color: result.approved ? '#065f46' : '#9f1239',
                    fontSize: '0.88rem',
                    fontWeight: 600,
                    marginBottom: '4px'
                  }}>
                    Reflection Notes:
                  </h3>
                  <p style={{
                    color: result.approved ? '#047857' : '#be123c',
                    fontSize: '0.92rem',
                    lineHeight: 1.5
                  }}>
                    {result.reflection_notes || 'No reflections.'}
                  </p>
                </div>
              </div>
            ) : (
              <div style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '60px 0', fontSize: '0.95rem' }}>
                Awaiting strategy execution...
              </div>
            )}
          </section>
        </div>

        {/* Right Column: Code & Metrics */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <section className="glass-panel" style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#059669', marginBottom: '16px' }}>
              <BarChart3 size={22} />
              <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)' }}>Generated C++ Worker</h2>
            </div>
            
            {result ? (
              <>
                <div style={{ marginBottom: '16px' }}>
                  <span style={{ 
                    display: 'inline-block', 
                    padding: '6px 14px', 
                    borderRadius: '20px', 
                    fontSize: '0.85rem',
                    fontWeight: 600,
                    background: result.approved ? '#ecfdf5' : '#fff1f2',
                    color: result.approved ? '#059669' : '#e11d48',
                    border: `1px solid ${result.approved ? '#a7f3d0' : '#fecdd3'}`
                  }}>
                    Status: {result.approved ? 'APPROVED' : 'REJECTED'} ({result.outcome.split(' ')[1] || 'timeout'})
                  </span>
                </div>
                
                <pre className="code-block">
                  <code>{result.strategy_source}</code>
                </pre>
              </>
            ) : (
              <div style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '60px 0', fontSize: '0.95rem' }}>
                Code will appear here once synthesized.
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

export default App;
