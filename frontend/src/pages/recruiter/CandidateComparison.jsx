import './CandidateComparison.css';
import React, { useEffect, useMemo, useState } from 'react';
import {
  Search,
  Users,
  RefreshCw,
  GitCompareArrows,
  X
} from 'lucide-react';

import api from '../../services/api';
import '../candidate/dashboard.css';

const STATUS_LABELS = {
  APPLIED: 'Applied',
  UNDER_REVIEW: 'Under Review',
  SHORTLISTED: 'Shortlisted',
  INTERVIEW: 'Interview',
  SELECTED: 'Selected',
  REJECTED: 'Rejected',
  WITHDRAWN: 'Withdrawn'
};

export default function CandidateComparison() {
  const [applicants, setApplicants] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [comparison, setComparison] = useState([]);
  const [search, setSearch] = useState('');
  const [jobFilter, setJobFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [comparing, setComparing] = useState(false);
  const [error, setError] = useState('');

  const loadApplicants = async () => {
    setLoading(true);
    setError('');

    try {
      const response = await api.get('/recruiter/applicants');

      setApplicants(
        Array.isArray(response.data) ? response.data : []
      );
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Unable to load applicants.'
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadApplicants();
  }, []);

  const jobs = useMemo(() => {
    const uniqueJobs = new Map();

    applicants.forEach((item) => {
      if (item.job_id) {
        uniqueJobs.set(item.job_id, item.job_title);
      }
    });

    return Array.from(
      uniqueJobs,
      ([id, title]) => ({ id, title })
    );
  }, [applicants]);

  const filteredApplicants = useMemo(() => {
    const term = search.trim().toLowerCase();

    return applicants.filter((item) => {
      const matchesJob =
        !jobFilter ||
        String(item.job_id) === String(jobFilter);

      const matchesSearch =
        !term ||
        [
          item.candidate_name,
          item.candidate_email,
          item.job_title
        ].some((value) =>
          String(value || '').toLowerCase().includes(term)
        );

      return matchesJob && matchesSearch;
    });
  }, [applicants, search, jobFilter]);

  const toggleCandidate = (applicationId) => {
    setSelectedIds((previous) => {
      if (previous.includes(applicationId)) {
        return previous.filter((id) => id !== applicationId);
      }

      if (previous.length >= 4) {
        setError('You can compare up to 4 candidates at a time.');
        return previous;
      }

      setError('');
      setComparison([]);

      return [...previous, applicationId];
    });
  };

  const compareCandidates = async () => {
    if (selectedIds.length < 2) {
      setError('Please select at least 2 candidates to compare.');
      return;
    }

    setComparing(true);
    setError('');
    setComparison([]);

    try {
      const response = await api.get(
        '/recruiter/compare-candidates',
        {
          params: {
            application_ids: selectedIds
          },
          paramsSerializer: {
            indexes: null
          }
        }
      );

      const results = Array.isArray(response.data)
        ? response.data
        : [];

      setComparison(results);

      if (results.length === 0) {
        setError('No valid candidate records were returned.');
      } else if (results.length !== selectedIds.length) {
        setError(
          'Some selected applications were unavailable for comparison.'
        );
      }
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Unable to compare selected candidates.'
      );
    } finally {
      setComparing(false);
    }
  };

  const getName = (candidate) =>
    candidate.candidate_name || 'Unnamed Candidate';

  const getInitials = (name) =>
    String(name)
      .split(' ')
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0])
      .join('')
      .toUpperCase();

  const renderList = (items, emptyText) => {
    if (!Array.isArray(items) || items.length === 0) {
      return (
        <span className="comparison-empty">
          {emptyText}
        </span>
      );
    }

    return (
      <ul className="comparison-list">
        {items.map((item, index) => (
          <li key={`${item}-${index}`}>{item}</li>
        ))}
      </ul>
    );
  };

  return (
    <div className="ss-dashboard">
      <div className="ss-heading">
        <div>
          <span className="ss-eyebrow">
            RECRUITMENT INTELLIGENCE
          </span>
          <h1>Candidate Comparison</h1>
          <p>
            Compare candidate profiles and identify the best match.
          </p>
        </div>

        <button
          className="ss-primary-btn"
          onClick={loadApplicants}
          disabled={loading}
        >
          <RefreshCw size={15} />
          Refresh
        </button>
      </div>

      {error && <div className="ss-alert">{error}</div>}

      <div className="ss-card comparison-selection-card">
        <div className="ss-card-head">
          <div>
            <h3>Select Candidates</h3>
            <p>
              Select 2 to 4 applicants for side-by-side comparison.
            </p>
          </div>

          <span className="comparison-selected-count">
            {selectedIds.length}/4 selected
          </span>
        </div>

        <div className="comparison-filters">
          <div className="ss-search">
            <Search size={16} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search candidate or job..."
            />
          </div>

          <select
            value={jobFilter}
            onChange={(e) => setJobFilter(e.target.value)}
          >
            <option value="">All Jobs</option>

            {jobs.map((job) => (
              <option key={job.id} value={job.id}>
                {job.title}
              </option>
            ))}
          </select>
        </div>

        {loading ? (
          <div className="ss-loading">
            Loading applicants...
          </div>
        ) : filteredApplicants.length === 0 ? (
          <div className="ss-empty">
            <Users size={28} />
            <h3>No applicants found</h3>
            <p>
              Applicants will appear here when candidates apply to your jobs.
            </p>
          </div>
        ) : (
          <div className="comparison-applicant-list">
            {filteredApplicants.map((item) => {
              const candidateName =
                item.candidate_name ||
                `Candidate #${item.candidate_id}`;

              const email =
                item.candidate_email || 'Email unavailable';

              const checked = selectedIds.includes(item.id);

              return (
                <label
                  className={`comparison-applicant ${
                    checked ? 'selected' : ''
                  }`}
                  key={item.id}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleCandidate(item.id)}
                  />

                  <div className="pipeline-avatar">
                    {getInitials(candidateName)}
                  </div>

                  <div className="comparison-applicant-info">
                    <strong>{candidateName}</strong>
                    <span>{email}</span>
                    <small>{item.job_title}</small>
                  </div>

                  <span className="comparison-status">
                    {STATUS_LABELS[item.current_status] ||
                      item.current_status}
                  </span>
                </label>
              );
            })}
          </div>
        )}

        <div className="comparison-selection-footer">
          <button
            className="pipeline-cancel-btn"
            onClick={() => {
              setSelectedIds([]);
              setComparison([]);
              setError('');
            }}
          >
            Clear Selection
          </button>

          <button
            className="ss-primary-btn"
            onClick={compareCandidates}
            disabled={selectedIds.length < 2 || comparing}
          >
            <GitCompareArrows size={15} />
            {comparing ? 'Comparing...' : 'Compare Candidates'}
          </button>
        </div>
      </div>

      {comparison.length > 0 && (
        <div className="ss-card comparison-results-card">
          <div className="ss-card-head">
            <div>
              <span className="ss-eyebrow">
                COMPARISON REPORT
              </span>
              <h3>Candidate Overview</h3>
              <p>
                Compare the selected candidate information.
              </p>
            </div>

            <button
              className="pipeline-cancel-btn"
              onClick={() => setComparison([])}
            >
              <X size={14} /> Close
            </button>
          </div>

          <div className="comparison-grid">
            <div className="comparison-label-column">
              <div className="comparison-cell comparison-header-cell">
                Candidate
              </div>
              <div className="comparison-cell">Job Applied</div>
              <div className="comparison-cell">Resume Match</div>
              <div className="comparison-cell">Current Status</div>
              <div className="comparison-cell">Matched Skills</div>
              <div className="comparison-cell">Missing Skills</div>
              <div className="comparison-cell">All Skills</div>
              <div className="comparison-cell">Experience</div>
              <div className="comparison-cell">Education</div>
            </div>

            {comparison.map((candidate) => {
              const score = Math.min(
                100,
                Math.max(0, Number(candidate.match_score) || 0)
              );

              return (
                <div
                  className="comparison-candidate-column"
                  key={candidate.application_id}
                >
                  <div className="comparison-cell comparison-header-cell">
                    <div className="comparison-person">
                      <div className="pipeline-avatar">
                        {getInitials(getName(candidate))}
                      </div>
                      <strong>{getName(candidate)}</strong>
                      <small>
                        {candidate.candidate_email || 'Email unavailable'}
                      </small>
                    </div>
                  </div>

                  <div className="comparison-cell">
                    {candidate.job_title || '—'}
                  </div>

                  <div className="comparison-cell">
                    <div className="comparison-score">
                      <strong>{Math.round(score)}%</strong>
                      <div className="comparison-score-track">
                        <span style={{ width: `${score}%` }} />
                      </div>
                    </div>
                  </div>

                  <div className="comparison-cell">
                    <span className="comparison-status">
                      {STATUS_LABELS[candidate.current_status] ||
                        candidate.current_status}
                    </span>
                  </div>

                  <div className="comparison-cell">
                    {renderList(
                      candidate.matched_skills,
                      'No matched skills'
                    )}
                  </div>

                  <div className="comparison-cell">
                    {renderList(
                      candidate.missing_skills,
                      'No missing skills'
                    )}
                  </div>

                  <div className="comparison-cell">
                    {renderList(
                      candidate.skills,
                      'No skills added'
                    )}
                  </div>

                  <div className="comparison-cell">
                    {renderList(
                      candidate.experiences,
                      'No experience added'
                    )}
                  </div>

                  <div className="comparison-cell">
                    {renderList(
                      candidate.educations,
                      'No education added'
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <p className="comparison-disclaimer">
            Resume match scores are based on available resume analysis.
            Review candidate details and interview performance before
            making a hiring decision.
          </p>
        </div>
      )}
    </div>
  );
}
