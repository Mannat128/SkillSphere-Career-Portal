import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Bookmark,
  Briefcase,
  Building,
  MapPin,
  Trash2,
  ArrowRight,
} from 'lucide-react';
import api from '../../services/api';

export default function SavedJobs() {
  const [savedJobs, setSavedJobs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSaved();
  }, []);

  const fetchSaved = async () => {
    setLoading(true);
    try {
      const res = await api.get('/jobs/saved');
      setSavedJobs(res.data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleRemove = async (jobId) => {
    try {
      await api.delete(`/jobs/${jobId}/save`);
      setSavedJobs(savedJobs.filter((j) => j.id !== jobId));
    } catch (e) {
      alert('Failed to remove saved job');
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 className="page-title">Saved Jobs</h2>
          <p className="page-subtitle">
            Review and apply to engineering roles you previously bookmarked.
          </p>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '50px', color: 'var(--text-muted)' }}>
          Loading saved jobs...
        </div>
      ) : savedJobs.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '60px 20px' }}>
          <Bookmark size={48} color="var(--primary-powder-blue)" style={{ margin: '0 auto 14px' }} />
          <h3 style={{ fontSize: '1.2rem', fontWeight: 700 }}>No Saved Jobs</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem', marginTop: '4px', marginBottom: '20px' }}>
            Browse open jobs and click the bookmark icon to save roles for later.
          </p>
          <Link to="/candidate/jobs" className="btn btn-primary">
            Explore Open Jobs
          </Link>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '20px' }}>
          {savedJobs.map((job) => (
            <div key={job.id} className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                  <span className="badge badge-blue">{job.employment_type}</span>
                  <button
                    onClick={() => handleRemove(job.id)}
                    title="Remove from saved"
                    style={{ color: 'var(--danger)', cursor: 'pointer' }}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>

                <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                  {job.title}
                </h3>

                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                  {job.company?.name || 'Company'} • {job.location}
                </p>

                <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', margin: '14px 0', lineHeight: 1.5 }}>
                  {job.description ? job.description.slice(0, 110) + '...' : ''}
                </p>

                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '16px' }}>
                  {(job.required_skills || []).map((sk) => (
                    <span key={sk} className="badge" style={{ background: '#F1F5F9' }}>
                      {sk}
                    </span>
                  ))}
                </div>
              </div>

              <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '14px' }}>
                <Link
                  to="/candidate/jobs"
                  className="btn btn-primary"
                  style={{ width: '100%', justifyContent: 'center', fontSize: '0.85rem' }}
                >
                  Apply via Jobs Board <ArrowRight size={14} />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
