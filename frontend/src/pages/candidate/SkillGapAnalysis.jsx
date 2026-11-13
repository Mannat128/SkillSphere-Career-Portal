import React, { useState, useEffect } from 'react';
import {
  BarChart3,
  CheckCircle2,
  AlertTriangle,
  Lightbulb,
  FileText,
  Briefcase,
  TrendingUp,
  ArrowRight,
  Layers,
  History,
  Sparkles,
  RefreshCw,
  Search
} from 'lucide-react';
import api from '../../services/api';

export default function SkillGapAnalysis() {
  const [resumes, setResumes] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [selectedResumeId, setSelectedResumeId] = useState('');
  const [selectedJobId, setSelectedJobId] = useState('');
  
  const [analysisResult, setAnalysisResult] = useState(null);
  const [multiJobResults, setMultiJobResults] = useState(null);
  const [historyList, setHistoryList] = useState([]);
  
  const [loadingInitial, setLoadingInitial] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [comparingMulti, setComparingMulti] = useState(false);
  const [activeTab, setActiveTab] = useState('single'); // 'single' | 'multi' | 'history'
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoadingInitial(true);
    setErrorMsg('');
    try {
      const [resumesRes, jobsRes, historyRes] = await Promise.all([
        api.get('/resumes'),
        api.get('/jobs'),
        api.get('/resume-analysis')
      ]);

      const resumeData = resumesRes.data || [];
      const jobData = (jobsRes.data || []).filter(j => j.status === 'PUBLISHED');
      const histData = historyRes.data || [];

      setResumes(resumeData);
      setJobs(jobData);
      setHistoryList(histData);

      if (resumeData.length > 0) {
        setSelectedResumeId(resumeData[0].id.toString());
      }
      if (jobData.length > 0) {
        setSelectedJobId(jobData[0].id.toString());
      }
    } catch (err) {
      console.error('Failed to load matching data', err);
      setErrorMsg('Could not load resumes or open jobs. Please try refreshing.');
    } finally {
      setLoadingInitial(false);
    }
  };

  const handleRunAnalysis = async () => {
    if (!selectedResumeId || !selectedJobId) {
      setErrorMsg('Please select both a resume and a job.');
      return;
    }

    setAnalyzing(true);
    setErrorMsg('');
    try {
      const res = await api.post(`/resume-analysis/analyze?resume_id=${selectedResumeId}&job_id=${selectedJobId}`);
      setAnalysisResult(res.data);
      // Refresh history list
      const histRes = await api.get('/resume-analysis');
      setHistoryList(histRes.data || []);
    } catch (err) {
      console.error('Analysis failed', err);
      const detail = err.response?.data?.detail || 'Analysis could not be generated. Ensure resume data is valid.';
      setErrorMsg(detail);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleRunMultiComparison = async () => {
    if (!selectedResumeId) {
      setErrorMsg('Please select a resume to compare across jobs.');
      return;
    }
    if (jobs.length === 0) {
      setErrorMsg('No active jobs available to compare against.');
      return;
    }

    setComparingMulti(true);
    setErrorMsg('');
    try {
      const payload = {
        resume_id: parseInt(selectedResumeId, 10),
        job_ids: jobs.map(j => j.id)
      };
      const res = await api.post('/resume-analysis/compare-multi', payload);
      setMultiJobResults(res.data?.comparisons || []);
    } catch (err) {
      console.error('Multi comparison failed', err);
      const detail = err.response?.data?.detail || 'Multi-job comparison failed.';
      setErrorMsg(detail);
    } finally {
      setComparingMulti(false);
    }
  };

  const getScoreColor = (score) => {
    if (score >= 75) return '#10B981'; // Green
    if (score >= 50) return 'var(--primary-powder-blue-dark)'; // Blue
    return 'var(--accent-peach-dark)'; // Peach/Orange
  };

  return (
    <div>
      {/* Header */}
      <div className="page-header" style={{ marginBottom: '24px' }}>
        <div>
          <h2 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <BarChart3 size={28} color="var(--primary-powder-blue)" />
            Skill Gap Analysis & Job Matching
          </h2>
          <p className="page-subtitle">
            Compare your verified resume skills against job requirements, uncover missing skills, and get personalized recommendations.
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '24px', borderBottom: '1px solid var(--border-soft)', paddingBottom: '12px' }}>
        <button
          onClick={() => setActiveTab('single')}
          className={`btn ${activeTab === 'single' ? 'btn-primary' : 'btn-outline'}`}
          style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 18px' }}
        >
          <Search size={16} /> Single Job Match
        </button>
        <button
          onClick={() => setActiveTab('multi')}
          className={`btn ${activeTab === 'multi' ? 'btn-primary' : 'btn-outline'}`}
          style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 18px' }}
        >
          <Layers size={16} /> Multi-Job Ranking
        </button>
        <button
          onClick={() => setActiveTab('history')}
          className={`btn ${activeTab === 'history' ? 'btn-primary' : 'btn-outline'}`}
          style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 18px' }}
        >
          <History size={16} /> Past Analysis History ({historyList.length})
        </button>
      </div>

      {errorMsg && (
        <div style={{
          background: 'var(--danger-bg)',
          color: 'var(--danger)',
          padding: '12px 16px',
          borderRadius: 'var(--radius-md)',
          marginBottom: '20px',
          fontSize: '0.9rem',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          border: '1px solid rgba(239, 68, 68, 0.2)'
        }}>
          <AlertTriangle size={18} />
          <span>{errorMsg}</span>
        </div>
      )}

      {loadingInitial ? (
        <div className="card" style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
          <RefreshCw size={36} className="spin" style={{ margin: '0 auto 12px', color: 'var(--primary-powder-blue)' }} />
          <p>Loading resumes and job market requirements...</p>
        </div>
      ) : resumes.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '60px 20px' }}>
          <FileText size={48} color="var(--primary-powder-blue)" style={{ margin: '0 auto 16px' }} />
          <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '8px' }}>No Resume Found</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.92rem', maxWidth: '480px', margin: '0 auto 20px' }}>
            Upload or build a resume to unlock Skill Gap Analysis and automated job matching.
          </p>
          <a href="/candidate/resumes" className="btn btn-primary">
            Upload Resume Now
          </a>
        </div>
      ) : (
        <>
          {/* TAB 1: SINGLE JOB MATCH */}
          {activeTab === 'single' && (
            <div>
              {/* Selectors Card */}
              <div className="card" style={{ marginBottom: '24px', padding: '24px' }}>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Sparkles size={20} color="var(--primary-powder-blue)" />
                  Select Resume & Target Job
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px', marginBottom: '20px' }}>
                  {/* Resume Select */}
                  <div>
                    <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px', color: 'var(--text-secondary)' }}>
                      Select Your Resume:
                    </label>
                    <div style={{ position: 'relative' }}>
                      <select
                        className="form-control"
                        value={selectedResumeId}
                        onChange={(e) => setSelectedResumeId(e.target.value)}
                        style={{ paddingLeft: '38px', height: '44px' }}
                      >
                        {resumes.map((r) => (
                          <option key={r.id} value={r.id}>
                            {r.original_filename} {r.is_primary ? '(Primary)' : ''}
                          </option>
                        ))}
                      </select>
                      <FileText size={18} style={{ position: 'absolute', left: '12px', top: '13px', color: 'var(--text-muted)' }} />
                    </div>
                  </div>

                  {/* Job Select */}
                  <div>
                    <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px', color: 'var(--text-secondary)' }}>
                      Target Job Opportunity:
                    </label>
                    <div style={{ position: 'relative' }}>
                      <select
                        className="form-control"
                        value={selectedJobId}
                        onChange={(e) => setSelectedJobId(e.target.value)}
                        style={{ paddingLeft: '38px', height: '44px' }}
                      >
                        {jobs.map((j) => (
                          <option key={j.id} value={j.id}>
                            {j.title} – {j.company?.name || 'Company'} ({j.location})
                          </option>
                        ))}
                      </select>
                      <Briefcase size={18} style={{ position: 'absolute', left: '12px', top: '13px', color: 'var(--text-muted)' }} />
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <button
                    onClick={handleRunAnalysis}
                    disabled={analyzing || !selectedResumeId || !selectedJobId}
                    className="btn btn-primary"
                    style={{ padding: '10px 24px', fontWeight: 700, fontSize: '0.95rem' }}
                  >
                    {analyzing ? (
                      <>
                        <RefreshCw size={16} className="spin" style={{ marginRight: '8px' }} />
                        Analyzing Match...
                      </>
                    ) : (
                      <>Run Skill Gap Analysis</>
                    )}
                  </button>
                </div>
              </div>

              {/* Analysis Result Display */}
              {analysisResult && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  {/* Top Score Banner */}
                  <div className="card" style={{
                    background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.95) 0%, var(--background-lavender-light) 100%)',
                    border: '1px solid var(--border-soft)',
                    padding: '28px'
                  }}>
                    <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '20px' }}>
                      <div style={{ flex: 1, minWidth: '260px' }}>
                        <span className="badge badge-peach" style={{ marginBottom: '8px' }}>
                          Verified Match Result
                        </span>
                        <h3 style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)', margin: '4px 0' }}>
                          {analysisResult.job_title || 'Position'}
                        </h3>
                        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '12px' }}>
                          Company: <strong>{analysisResult.company_name || 'Employer'}</strong>
                        </p>
                        <p style={{ fontSize: '0.92rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                          {analysisResult.explanation}
                        </p>
                      </div>

                      {/* Match Score Circle */}
                      <div style={{
                        width: '120px',
                        height: '120px',
                        borderRadius: '50%',
                        border: `6px solid ${getScoreColor(analysisResult.match_score)}`,
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        background: '#FFFFFF',
                        boxShadow: '0 4px 14px rgba(0, 0, 0, 0.06)'
                      }}>
                        <span style={{ fontSize: '1.75rem', fontWeight: 900, color: getScoreColor(analysisResult.match_score) }}>
                          {Math.round(analysisResult.match_score)}%
                        </span>
                        <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                          Match Score
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Skills Grid: Matched vs Missing */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
                    {/* Matched Skills */}
                    <div className="card" style={{ borderLeft: '4px solid var(--primary-powder-blue)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
                        <div style={{
                          width: '32px',
                          height: '32px',
                          borderRadius: '8px',
                          background: 'rgba(141, 185, 240, 0.25)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: 'var(--primary-powder-blue-dark)'
                        }}>
                          <CheckCircle2 size={18} />
                        </div>
                        <div>
                          <h4 style={{ fontSize: '1.05rem', fontWeight: 700 }}>
                            Matched Skills ({analysisResult.matched_skills?.length || 0})
                          </h4>
                          <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                            Found in both your resume profile and job requirements
                          </p>
                        </div>
                      </div>

                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', minHeight: '60px' }}>
                        {analysisResult.matched_skills && analysisResult.matched_skills.length > 0 ? (
                          analysisResult.matched_skills.map((skill, idx) => (
                            <span
                              key={idx}
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '6px',
                                padding: '6px 12px',
                                borderRadius: '20px',
                                background: 'var(--primary-powder-blue-light)',
                                color: '#0F172A',
                                fontWeight: 600,
                                fontSize: '0.82rem',
                                border: '1px solid rgba(141, 185, 240, 0.4)'
                              }}
                            >
                              <CheckCircle2 size={12} color="#0284C7" />
                              {skill}
                            </span>
                          ))
                        ) : (
                          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', fontStyle: 'italic' }}>
                            No exact skill matches identified.
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Missing Skills */}
                    <div className="card" style={{ borderLeft: '4px solid var(--accent-peach)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
                        <div style={{
                          width: '32px',
                          height: '32px',
                          borderRadius: '8px',
                          background: 'rgba(245, 182, 158, 0.25)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: 'var(--accent-peach-dark)'
                        }}>
                          <AlertTriangle size={18} />
                        </div>
                        <div>
                          <h4 style={{ fontSize: '1.05rem', fontWeight: 700 }}>
                            Missing Skills ({analysisResult.missing_skills?.length || 0})
                          </h4>
                          <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                            Required for this role but not yet on your verified profile
                          </p>
                        </div>
                      </div>

                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', minHeight: '60px' }}>
                        {analysisResult.missing_skills && analysisResult.missing_skills.length > 0 ? (
                          analysisResult.missing_skills.map((skill, idx) => (
                            <span
                              key={idx}
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '6px',
                                padding: '6px 12px',
                                borderRadius: '20px',
                                background: 'var(--accent-peach-light)',
                                color: '#7C2D12',
                                fontWeight: 600,
                                fontSize: '0.82rem',
                                border: '1px solid rgba(245, 182, 158, 0.5)'
                              }}
                            >
                              <AlertTriangle size={12} color="#EA580C" />
                              {skill}
                            </span>
                          ))
                        ) : (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#10B981', fontSize: '0.88rem', fontWeight: 600 }}>
                            <CheckCircle2 size={16} /> All required technologies are satisfied!
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Recommendations Card */}
                  <div className="card" style={{ background: 'var(--surface-white)', padding: '24px' }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px' }}>
                      <div style={{
                        width: '40px',
                        height: '40px',
                        borderRadius: '12px',
                        background: 'linear-gradient(135deg, var(--primary-powder-blue) 0%, var(--accent-peach) 100%)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#0F172A',
                        flexShrink: 0
                      }}>
                        <Lightbulb size={22} />
                      </div>
                      <div>
                        <h4 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '6px' }}>
                          Targeted Growth & Action Plan
                        </h4>
                        <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem', lineHeight: 1.6, marginBottom: '16px' }}>
                          {analysisResult.recommendations}
                        </p>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
                          <a href="/candidate/technical-assessments" className="btn btn-outline" style={{ fontSize: '0.85rem', padding: '6px 14px' }}>
                            Take Practice Quizzes
                          </a>
                          <a href="/candidate/interview-practice" className="btn btn-outline" style={{ fontSize: '0.85rem', padding: '6px 14px' }}>
                            AI Mock Interview
                          </a>
                          <a href="/candidate/resume-builder" className="btn btn-outline" style={{ fontSize: '0.85rem', padding: '6px 14px' }}>
                            Update Resume Profile
                          </a>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: MULTI-JOB COMPARISON */}
          {activeTab === 'multi' && (
            <div>
              <div className="card" style={{ marginBottom: '24px', padding: '24px' }}>
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '16px' }}>
                  <div>
                    <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '4px' }}>
                      Multi-Job Market Ranking
                    </h3>
                    <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem' }}>
                      Compare your selected resume across all {jobs.length} active job postings to see where you have the highest fit.
                    </p>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <select
                      className="form-control"
                      value={selectedResumeId}
                      onChange={(e) => setSelectedResumeId(e.target.value)}
                      style={{ minWidth: '220px' }}
                    >
                      {resumes.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.original_filename}
                        </option>
                      ))}
                    </select>
                    <button
                      onClick={handleRunMultiComparison}
                      disabled={comparingMulti || jobs.length === 0}
                      className="btn btn-primary"
                      style={{ whiteSpace: 'nowrap' }}
                    >
                      {comparingMulti ? (
                        <>
                          <RefreshCw size={16} className="spin" style={{ marginRight: '6px' }} />
                          Ranking...
                        </>
                      ) : (
                        'Rank All Open Jobs'
                      )}
                    </button>
                  </div>
                </div>
              </div>

              {multiJobResults ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {multiJobResults.length === 0 ? (
                    <div className="card" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                      No job comparisons returned.
                    </div>
                  ) : (
                    multiJobResults.map((comp, idx) => (
                      <div key={idx} className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '18px 24px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                          <div style={{
                            width: '42px',
                            height: '42px',
                            borderRadius: '10px',
                            background: idx === 0 ? 'var(--primary-powder-blue)' : 'var(--background-lavender)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontWeight: 800,
                            color: '#0F172A',
                            fontSize: '1rem'
                          }}>
                            #{idx + 1}
                          </div>
                          <div>
                            <h4 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0 }}>
                              {comp.job_title}
                            </h4>
                            <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', margin: '2px 0 0' }}>
                              Company: {comp.company_name} | Matched: {comp.matched_skills?.length || 0} | Missing: {comp.missing_skills?.length || 0}
                            </p>
                          </div>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                          <div style={{ textAlign: 'right' }}>
                            <span style={{ fontSize: '1.25rem', fontWeight: 800, color: getScoreColor(comp.match_score) }}>
                              {Math.round(comp.match_score)}%
                            </span>
                            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Fit Score</div>
                          </div>
                          <button
                            onClick={() => {
                              setAnalysisResult(comp);
                              setActiveTab('single');
                            }}
                            className="btn btn-outline"
                            style={{ padding: '6px 14px', fontSize: '0.82rem' }}
                          >
                            View Details
                          </button>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              ) : (
                <div className="card" style={{ textAlign: 'center', padding: '50px 20px', color: 'var(--text-muted)' }}>
                  <TrendingUp size={40} color="var(--primary-powder-blue)" style={{ margin: '0 auto 12px' }} />
                  <p>Click "Rank All Open Jobs" to run market-wide skill benchmarking.</p>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: HISTORY */}
          {activeTab === 'history' && (
            <div className="card" style={{ padding: '24px' }}>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <History size={20} color="var(--primary-powder-blue)" />
                Past Skill Gap Analyses
              </h3>

              {historyList.length === 0 ? (
                <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', textAlign: 'center', padding: '30px 0' }}>
                  No previous analyses found. Select a resume and job on the "Single Job Match" tab to run your first evaluation.
                </p>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-soft)', textAlign: 'left', color: 'var(--text-muted)' }}>
                        <th style={{ padding: '12px 14px' }}>Job Title</th>
                        <th style={{ padding: '12px 14px' }}>Company</th>
                        <th style={{ padding: '12px 14px' }}>Match Score</th>
                        <th style={{ padding: '12px 14px' }}>Matched Skills</th>
                        <th style={{ padding: '12px 14px' }}>Missing Skills</th>
                        <th style={{ padding: '12px 14px', textAlign: 'right' }}>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {historyList.map((item) => (
                        <tr key={item.id} style={{ borderBottom: '1px solid var(--border-soft)' }}>
                          <td style={{ padding: '14px', fontWeight: 600 }}>{item.job_title}</td>
                          <td style={{ padding: '14px', color: 'var(--text-secondary)' }}>{item.company_name}</td>
                          <td style={{ padding: '14px' }}>
                            <span style={{
                              fontWeight: 800,
                              color: getScoreColor(item.match_score),
                              background: 'var(--background-lavender-light)',
                              padding: '4px 8px',
                              borderRadius: '6px'
                            }}>
                              {Math.round(item.match_score)}%
                            </span>
                          </td>
                          <td style={{ padding: '14px', color: 'var(--text-secondary)' }}>
                            {item.matched_skills?.slice(0, 3).join(', ') || 'None'}
                            {item.matched_skills?.length > 3 ? ` +${item.matched_skills.length - 3}` : ''}
                          </td>
                          <td style={{ padding: '14px', color: 'var(--text-secondary)' }}>
                            {item.missing_skills?.slice(0, 3).join(', ') || 'None'}
                            {item.missing_skills?.length > 3 ? ` +${item.missing_skills.length - 3}` : ''}
                          </td>
                          <td style={{ padding: '14px', textAlign: 'right' }}>
                            <button
                              onClick={() => {
                                setAnalysisResult(item);
                                setActiveTab('single');
                              }}
                              className="btn btn-outline"
                              style={{ padding: '4px 10px', fontSize: '0.8rem' }}
                            >
                              Inspect
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
