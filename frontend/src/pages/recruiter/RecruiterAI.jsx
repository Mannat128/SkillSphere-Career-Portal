import React, { useState } from 'react';
import api from '../../services/api';

const tools = [
  ['generate_jd', 'Job Description Generator'], ['improve_jd', 'Improve a Job Description'],
  ['suggest_skills', 'Skill Suggestions'], ['assessment_plan', 'Assessment Assistant'],
  ['evaluate_candidate', 'Candidate Evaluation Assistance'],
];

export default function RecruiterAI() {
  const [tool, setTool] = useState('generate_jd');
  const [details, setDetails] = useState('{}');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError(''); setResult(null);
    let parsed;
    try { parsed = JSON.parse(details); } catch { setError('Enter valid JSON details.'); return; }
    setBusy(true);
    try {
      const response = await api.post('/recruiter-ai/tools', { tool, details: parsed });
      setResult(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'The AI provider could not complete this request.');
    } finally { setBusy(false); }
  }

  return <main style={{ maxWidth: 900, margin: '36px auto', padding: 24 }}>
    <h1>Recruiter AI Assistant</h1>
    <p>Use AI to draft and review recruiting materials. Candidate evaluations are advisory and do not make hiring decisions.</p>
    <form onSubmit={submit} style={{ display: 'grid', gap: 16 }}>
      <label>Tool<select value={tool} onChange={(e) => setTool(e.target.value)} style={{ display: 'block', padding: 10, width: '100%' }}>{tools.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
      <label>Details as JSON<textarea rows={9} value={details} onChange={(e) => setDetails(e.target.value)} placeholder='{"role":"Backend Engineer","skills":["Python","SQL"]}' style={{ display: 'block', padding: 10, width: '100%', fontFamily: 'monospace' }} /></label>
      <button disabled={busy} type="submit">{busy ? 'Generating…' : 'Generate with AI'}</button>
    </form>
    {error && <p role="alert" style={{ color: '#a22' }}>{error}</p>}
    {result && <section style={{ marginTop: 24, padding: 18, border: '1px solid #ddd', borderRadius: 8 }}><h2>AI result</h2><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{typeof result.result === 'string' ? result.result : JSON.stringify(result.result, null, 2)}</pre>{result.caveats?.length > 0 && <><h3>Notes</h3><ul>{result.caveats.map((note, i) => <li key={i}>{note}</li>)}</ul></>}</section>}
  </main>;
}
