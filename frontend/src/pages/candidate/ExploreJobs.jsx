import React, { useState, useEffect } from 'react';
import {
  Search,
  MapPin,
  Briefcase,
  DollarSign,
  Bookmark,
  CheckCircle,
  Clock,
  Building,
  Send,
  Eye,
  X,
  Filter,
} from 'lucide-react';
import api from '../../services/api';

export default function ExploreJobs() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [employmentType, setEmploymentType] = useState('');
  const [experienceLevel, setExperienceLevel] = useState('');
  const [savedJobIds, setSavedJobIds] = useState([]);

  // Apply Modal
  const [selectedJobForApply, setSelectedJobForApply] = useState(null);
  const [coverLetter, setCoverLetter] = useState('');
  const [applying, setApplying] = useState(false);
  const [applySuccessMsg, setApplySuccessMsg] = useState('');

  // Details Modal
  const [viewDetailsJob, setViewDetailsJob] = useState(null);

  useEffect(() => {
    fetchJobs();
    fetchSavedJobs();
  }, [employmentType, experienceLevel]);

  const fetchJobs = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search.trim()) params.append('keyword', search.trim());
      if (employmentType) params.append('employment_type', employmentType);
      if (experienceLevel) params.append('experience_level', experienceLevel);

      const res = await api.get(`/jobs?${params.toString()}`);
      setJobs(res.data.items || res.data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const fetchSavedJobs = async () => {
    try {
      const res = await api.get('/jobs/saved');
      const ids = (res.data || []).map((j) => j.id);
      setSavedJobIds(ids);
    } catch (e) {}
  };

  const handleToggleSaveJob = async (jobId) => {
    try {
      if (savedJobIds.includes(jobId)) {
        await api.delete(`/jobs/${jobId}/save`);
        setSavedJobIds(savedJobIds.filter((id) => id !== jobId));
      } else {
        await api.post(`/jobs/${jobId}/save`);
        setSavedJobIds([...savedJobIds, jobId]);
      }
    } catch (e) {
      alert('Unable to toggle saved status');
    }
  };

  const handleApplySubmit = async (e) => {
    e.preventDefault();
    if (!selectedJobForApply) return;
    setApplying(true);
    setApplySuccessMsg('');

    try {
      await api.post(`/applications/jobs/${selectedJobForApply.id}/apply`, {
        cover_letter: coverLetter,
      });
      setApplySuccessMsg(`Successfully applied for ${selectedJobForApply.title}!`);
      setTimeout(() => {
        setSelectedJobForApply(null);
        setCoverLetter('');
        setApplySuccessMsg('');
      }, 1800);
    } catch (err) {
      alert(err.response?.data?.detail || 'Application failed or duplicate application exists.');
    } finally {
      setApplying(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 className="page-title">Explore Open Engineering Roles</h2>
          <p className="page-subtitle">
            Search verified developer opportunities and apply with your profile and resume.
          </p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="card" style={{ marginBottom: '24px', padding: '18px 24px' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '14px', alignItems: 'center' }}>
          <div style={{ flex: 1, minWidth: '220px', position: 'relative' }}>
            <Search size={18} color="var(--text-muted)" style={{ position: 'absolute', left: '12px', top: '12px' }} />
            <input
              type="text"
              placeholder="Search by job title or keyword..."
              className="form-input"
              style={{ paddingLeft: '38px' }}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && fetchJobs()}
            />
          </div>

          <div style={{ width: '160px' }}>
            <select
              className="form-select"
              value={employmentType}
              onChange={(e) => setEmploymentType(e.target.value)}
            >
              <option value="">All Types</option>
              <option value="Full-time">Full-time</option>
              <option value="Part-time">Part-time</option>
              <option value="Contract">Contract</option>
              <option value="Internship">Internship</option>
            </select>
          </div>

          <div style={{ width: '160px' }}>
            <select
              className="form-select"
              value={experienceLevel}
              onChange={(e) => setExperienceLevel(e.target.value)}
            >
              <option value="">All Experience Levels</option>
              <option value="Entry-Level">Entry-Level</option>
              <option value="Mid-Level">Mid-Level</option>
              <option value="Senior">Senior</option>
              <option value="Lead / Principal">Lead / Principal</option>
            </select>
          </div>

          <button onClick={fetchJobs} className="btn btn-primary" style={{ padding: '10px 18px' }}>
            Search
          </button>
        </div>
      </div>

      {/* Jobs Grid */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '50px', color: 'var(--text-muted)' }}>
          Loading open opportunities...
        </div>
      ) : jobs.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '60px 20px' }}>
          <Briefcase size={48} color="var(--primary-powder-blue)" style={{ margin: '0 auto 14px' }} />
          <h3 style={{ fontSize: '1.2rem', fontWeight: 700 }}>No Jobs Found</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem', marginTop: '4px' }}>
            Try adjusting your search keywords or filter options.
          </p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '20px' }}>
          {jobs.map((job) => {
            const isSaved = savedJobIds.includes(job.id);
            return (
              <div key={job.id} className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                    <span className="badge badge-blue">{job.employment_type}</span>
                    <button
                      onClick={() => handleToggleSaveJob(job.id)}
                      title={isSaved ? 'Remove Bookmark' : 'Save Job'}
                      style={{ color: isSaved ? 'var(--accent-sunset-peach-dark)' : 'var(--text-muted)', cursor: 'pointer' }}
                    >
                      <Bookmark size={18} fill={isSaved ? 'var(--accent-sunset-peach-dark)' : 'none'} />
                    </button>
                  </div>

                  <h3 style={{ fontSize: '1.18rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                    {job.title}
                  </h3>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                    <Building size={14} />
                    <span>{job.company?.name || 'Company'}</span>
                    <span>•</span>
                    <MapPin size={14} />
                    <span>{job.location}</span>
                  </div>

                  <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', margin: '14px 0', lineHeight: 1.5 }}>
                    {job.description ? job.description.slice(0, 110) + '...' : ''}
                  </p>

                  {/* Skills tags */}
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '16px' }}>
                    {(job.required_skills || []).map((skill) => (
                      <span key={skill} className="badge" style={{ background: '#F1F5F9', color: 'var(--text-secondary)' }}>
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Bottom Actions */}
                <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <button
                    onClick={() => setViewDetailsJob(job)}
                    className="btn btn-outline"
                    style={{ fontSize: '0.82rem', padding: '6px 12px' }}
                  >
                    <Eye size={14} /> Details
                  </button>

                  <button
                    onClick={() => setSelectedJobForApply(job)}
                    className="btn btn-primary"
                    style={{ fontSize: '0.82rem', padding: '6px 16px' }}
                  >
                    <Send size={14} /> Apply Now
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Apply Modal */}
      {selectedJobForApply && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '540px' }}>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 800, marginBottom: '6px' }}>
              Apply for {selectedJobForApply.title}
            </h3>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '18px' }}>
              {selectedJobForApply.company?.name || 'Company'} • {selectedJobForApply.location}
            </p>

            {applySuccessMsg ? (
              <div style={{ padding: '20px', background: '#ECFDF5', color: '#065F46', borderRadius: '10px', textAlign: 'center' }}>
                <CheckCircle size={36} color="#059669" style={{ margin: '0 auto 8px' }} />
                <h4 style={{ fontWeight: 800 }}>{applySuccessMsg}</h4>
                <p style={{ fontSize: '0.82rem', marginTop: '4px' }}>
                  The recruiter will review your profile. If shortlisted, you will receive a First Round Assessment.
                </p>
              </div>
            ) : (
              <form onSubmit={handleApplySubmit}>
                <div className="form-group">
                  <label className="form-label">Cover Letter / Note to Recruiter (Optional)</label>
                  <textarea
                    rows={4}
                    className="form-textarea"
                    placeholder="Briefly highlight why your background is a strong fit for this position..."
                    value={coverLetter}
                    onChange={(e) => setCoverLetter(e.target.value)}
                  />
                </div>

                <div style={{ padding: '12px', background: 'var(--bg-lavender-white)', borderRadius: '8px', fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '18px' }}>
                  Your registered candidate profile details and latest uploaded resume will be submitted to the recruiter.
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                  <button
                    type="button"
                    onClick={() => setSelectedJobForApply(null)}
                    className="btn btn-outline"
                    disabled={applying}
                  >
                    Cancel
                  </button>
                  <button type="submit" disabled={applying} className="btn btn-primary">
                    {applying ? 'Submitting Application...' : 'Confirm & Apply'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* View Details Modal */}
      {viewDetailsJob && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '650px', maxHeight: '85vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
              <div>
                <span className="badge badge-blue">{viewDetailsJob.employment_type}</span>
                <span className="badge badge-peach" style={{ marginLeft: '8px' }}>{viewDetailsJob.experience_level}</span>
                <h3 style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--text-primary)', marginTop: '8px' }}>
                  {viewDetailsJob.title}
                </h3>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                  {viewDetailsJob.company?.name || 'Company'} • {viewDetailsJob.location}
                </p>
              </div>
              <button onClick={() => setViewDetailsJob(null)} style={{ color: 'var(--text-muted)' }}>
                <X size={20} />
              </button>
            </div>

            <div style={{ margin: '18px 0' }}>
              <h4 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '6px' }}>Description</h4>
              <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                {viewDetailsJob.description}
              </p>
            </div>

            <div style={{ margin: '18px 0' }}>
              <h4 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '8px' }}>Required Technical Skills</h4>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {(viewDetailsJob.required_skills || []).map((sk) => (
                  <span key={sk} className="badge badge-blue">{sk}</span>
                ))}
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '24px' }}>
              <button onClick={() => setViewDetailsJob(null)} className="btn btn-outline">
                Close
              </button>
              <button
                onClick={() => {
                  setSelectedJobForApply(viewDetailsJob);
                  setViewDetailsJob(null);
                }}
                className="btn btn-primary"
              >
                Apply for Position
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
