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
      // Pointing to local FastAPI server we just built
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
          <BrainCircuit size={24} />
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>Strategy Hypothesis</h2>
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
              <><Activity size={20} className="animate-spin" /> Synthesizing...</>
            ) : (
              <><Play size={20} /> Execute</>
            )}
          </button>
        </div>
        {error && <div style={{ color: '#ef4444', marginTop: '8px' }}>{error}</div>}
      </section>

      {/* Results Dashboard Grid */}
      <div className="dashboard-grid">
        
        {/* Left Column: Thoughts & Status */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <section className="glass-panel" style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-purple)', marginBottom: '16px' }}>
              <Terminal size={24} />
              <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>Agent Logs</h2>
            </div>
            
            {result ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {result.iteration_log.map((log, i) => (
                  <div key={i} style={{ 
                    padding: '12px', 
                    background: 'rgba(0,0,0,0.4)', 
                    borderRadius: '8px',
                    borderLeft: `4px solid ${log.includes('evaluator') ? '#ef4444' : '#3b82f6'}`,
                    fontFamily: 'JetBrains Mono',
                    fontSize: '0.9rem',
                    color: '#e2e8f0'
                  }}>
                    {log}
                  </div>
                ))}
                
                <div style={{ marginTop: '16px' }}>
                  <h3 style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '8px' }}>Reflection Notes:</h3>
                  <p style={{ color: '#fca5a5', fontSize: '0.95rem' }}>{result.reflection_notes || 'No reflections.'}</p>
                </div>
              </div>
            ) : (
              <div style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '40px 0' }}>
                Awaiting strategy execution...
              </div>
            )}
          </section>
        </div>

        {/* Right Column: Code & Metrics */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <section className="glass-panel" style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#10b981', marginBottom: '16px' }}>
              <BarChart3 size={24} />
              <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>Generated C++ Worker</h2>
            </div>
            
            {result ? (
              <>
                <div style={{ marginBottom: '16px' }}>
                  <span style={{ 
                    display: 'inline-block', 
                    padding: '4px 12px', 
                    borderRadius: '16px', 
                    fontSize: '0.85rem',
                    background: result.approved ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                    color: result.approved ? '#34d399' : '#f87171',
                    border: `1px solid ${result.approved ? '#34d399' : '#f87171'}`
                  }}>
                    Status: {result.approved ? 'APPROVED' : 'REJECTED'} ({result.outcome.split(' ')[1] || 'timeout'})
                  </span>
                </div>
                
                <pre className="code-block">
                  <code>{result.strategy_source}</code>
                </pre>
              </>
            ) : (
              <div style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '40px 0' }}>
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
