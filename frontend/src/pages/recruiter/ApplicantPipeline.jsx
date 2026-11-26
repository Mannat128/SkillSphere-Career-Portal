
import React, { useEffect, useMemo, useState } from 'react';
import {
  Search, Users, RefreshCw, ChevronDown, Eye,
  UserCheck, Clock, BriefcaseBusiness, X, FileText
} from 'lucide-react';
import api from '../../services/api';
import '../candidate/dashboard.css';

const STAGES = [
  'APPLIED',
  'UNDER_REVIEW',
  'SHORTLISTED',
  'INTERVIEW',
  'SELECTED',
  'REJECTED',
  'WITHDRAWN'
];

const stageLabels = {
  APPLIED: 'Applied',
  UNDER_REVIEW: 'Under Review',
  SHORTLISTED: 'Shortlisted',
  INTERVIEW: 'Interview',
  SELECTED: 'Selected',
  REJECTED: 'Rejected',
  WITHDRAWN: 'Withdrawn'
};

const statusClass = (status) =>
  `pipeline-status pipeline-status-${String(status || '').toLowerCase()}`;

export default function ApplicantPipeline() {
  const [pipeline, setPipeline] = useState({});
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState('');
  const [activeStage, setActiveStage] = useState('APPLIED');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [updatingId, setUpdatingId] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [selectedApplicant, setSelectedApplicant] = useState(null);
  const [newStatus, setNewStatus] = useState('');
  const [notes, setNotes] = useState('');
  const [openingResumeId, setOpeningResumeId] = useState(null);
  const [resumeError, setResumeError] = useState('');

  const loadPipeline = async () => {
    setLoading(true);
    setError('');

    try {
      const [pipelineResponse, jobsResponse] = await Promise.all([
        api.get('/recruiter/pipeline', {
          params: selectedJob ? { job_id: selectedJob } : {}
        }),
        api.get('/recruiter/jobs')
      ]);

      setPipeline(pipelineResponse.data || {});
      setJobs(Array.isArray(jobsResponse.data) ? jobsResponse.data : []);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Unable to load applicant pipeline.'
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPipeline();
  }, [selectedJob]);

  useEffect(() => {
    if (!selectedApplicant) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [selectedApplicant]);

  const allApplicants = useMemo(() => {
    return STAGES.flatMap((stage) =>
      (pipeline[stage] || []).map((applicant) => ({
        ...applicant,
        current_status: stage
      }))
    );
  }, [pipeline]);

  const visibleApplicants = useMemo(() => {
    const applicants = pipeline[activeStage] || [];
    const term = search.trim().toLowerCase();

    if (!term) return applicants;

    return applicants.filter((item) =>
      [
        item.candidate_name,
        item.candidate_email,
        item.job_title
      ].some((value) => String(value || '').toLowerCase().includes(term))
    );
  }, [pipeline, activeStage, search]);

  const updateStatus = async () => {
    if (!selectedApplicant || !newStatus) return;

    setUpdatingId(selectedApplicant.id);
    setError('');
    setSuccess('');

    try {
      await api.put(
        `/recruiter/applicants/${selectedApplicant.id}/status`,
        {
          status: newStatus,
          notes: notes.trim() || null
        }
      );

      setSuccess('Applicant status updated successfully.');
      setSelectedApplicant(null);
      setNotes('');
      setNewStatus('');
      await loadPipeline();
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Unable to update applicant status.'
      );
    } finally {
      setUpdatingId(null);
    }
  };

  const openUpdateModal = (applicant) => {
    setSelectedApplicant(applicant);
    setNewStatus(applicant.current_status || activeStage);
    setNotes('');
    setError('');
    setSuccess('');
  };

  const openApplicantResume = async (applicant) => {
    const urlResumeId = applicant.resume_url?.match(/\/resumes\/(\d+)\/download(?:\?|$)/)?.[1];
    const resumeId = applicant.resume_id || urlResumeId;
    if (!resumeId) {
      setResumeError('This application does not have an accessible resume attached.');
      return;
    }

    const previewWindow = window.open('about:blank', '_blank');
    if (!previewWindow) {
      setResumeError('Your browser blocked the resume tab. Allow pop-ups for SkillSphere and try again.');
      return;
    }
    previewWindow.opener = null;
    setResumeError('');
    setOpeningResumeId(applicant.id);

    try {
      // Use the authenticated API client so the resume stays private. Never
      // navigate the browser to the API path without its Authorization header.
      const response = await api.get(`/resumes/${resumeId}/download`, { responseType: 'blob' });
      const mediaType = String(response.headers?.['content-type'] || response.data?.type || '').toLowerCase();
      const blob = response.data instanceof Blob
        ? response.data
        : new Blob([response.data], { type: mediaType || 'application/octet-stream' });

      if (!blob.size) throw new Error('The resume file is empty.');

      const objectUrl = URL.createObjectURL(blob);
      if (mediaType.includes('application/pdf') || blob.type.toLowerCase().includes('application/pdf')) {
        previewWindow.location.replace(objectUrl);
        const cleanupTimer = window.setInterval(() => {
          if (previewWindow.closed) {
            window.clearInterval(cleanupTimer);
            URL.revokeObjectURL(objectUrl);
          }
        }, 1500);
      } else if (mediaType.startsWith('image/')) {
        previewWindow.location.replace(objectUrl);
        const cleanupTimer = window.setInterval(() => {
          if (previewWindow.closed) {
            window.clearInterval(cleanupTimer);
            URL.revokeObjectURL(objectUrl);
          }
        }, 1500);
      } else {
        previewWindow.close();
        const link = document.createElement('a');
        link.href = objectUrl;
        link.download = `resume-${resumeId}`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
      }
    } catch (err) {
      previewWindow.close();
      const status = err.response?.status;
      if (status === 403) {
        setResumeError('You are not authorized to view this resume. Recruiters can view resumes only for applicants to their own jobs.');
      } else if (status === 404) {
        setResumeError('The resume file is missing or no longer available.');
      } else if (status === 401) {
        setResumeError('Your session has expired. Sign in again to view this resume.');
      } else {
        setResumeError('Unable to open this resume right now. Please try again.');
      }
    } finally {
      setOpeningResumeId(null);
    }
  };

  const getCandidateName = (item) =>
    item.candidate_name || 'Unnamed Candidate';

  const getInitials = (name) =>
    String(name)
      .split(' ')
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0])
      .join('')
      .toUpperCase();

  return (
    <div className="ss-dashboard">
      <div className="ss-heading">
        <div>
          <span className="ss-eyebrow">RECRUITMENT WORKSPACE</span>
          <h1>Applicant Pipeline</h1>
          <p>Track candidates and manage their recruitment progress.</p>
        </div>

        <button className="ss-primary-btn" onClick={loadPipeline}>
          <RefreshCw size={15} /> Refresh
        </button>
      </div>

      {error && <div className="ss-alert">{error}</div>}
      {success && <div className="ss-notice">{success}</div>}
      {resumeError && <div className="ss-alert" role="alert">{resumeError}</div>}

      <div className="ss-kpis">
        <div className="ss-kpi">
          <span>Total Applicants</span>
          <strong>{allApplicants.length}</strong>
          <Users size={19} />
        </div>

        <div className="ss-kpi">
          <span>Shortlisted</span>
          <strong>{(pipeline.SHORTLISTED || []).length}</strong>
          <UserCheck size={19} />
        </div>

        <div className="ss-kpi">
          <span>Interviews</span>
          <strong>{(pipeline.INTERVIEW || []).length}</strong>
          <Clock size={19} />
        </div>

        <div className="ss-kpi">
          <span>Selected</span>
          <strong>{(pipeline.SELECTED || []).length}</strong>
          <BriefcaseBusiness size={19} />
        </div>
      </div>

      <div className="ss-card">
        <div className="ss-card-head">
          <div>
            <h3>Candidate Stages</h3>
            <p>Choose a stage to view its candidates.</p>
          </div>

          <select
            className="pipeline-job-filter"
            value={selectedJob}
            onChange={(e) => setSelectedJob(e.target.value)}
          >
            <option value="">All Jobs</option>
            {jobs.map((job) => (
              <option key={job.id} value={job.id}>
                {job.title}
              </option>
            ))}
          </select>
        </div>

        <div className="pipeline-stage-tabs">
          {STAGES.map((stage) => (
            <button
              key={stage}
              className={activeStage === stage ? 'active' : ''}
              onClick={() => setActiveStage(stage)}
            >
              {stageLabels[stage]}
              <span>{(pipeline[stage] || []).length}</span>
            </button>
          ))}
        </div>

        <div className="pipeline-toolbar">
          <div className="ss-search">
            <Search size={16} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search candidate or job..."
            />
          </div>

          <span className="pipeline-result-count">
            {visibleApplicants.length} candidates
          </span>
        </div>

        {loading ? (
          <div className="ss-loading">Loading applicant pipeline...</div>
        ) : visibleApplicants.length === 0 ? (
          <div className="ss-empty">
            <Users size={30} />
            <h3>No candidates found</h3>
            <p>There are no candidates in this stage yet.</p>
          </div>
        ) : (
          <div className="pipeline-list">
            {visibleApplicants.map((applicant) => (
              <div className="pipeline-candidate" key={applicant.id}>
                <div className="pipeline-avatar">
                  {getInitials(getCandidateName(applicant))}
                </div>

                <div className="pipeline-candidate-info">
                  <h4>{getCandidateName(applicant)}</h4>
                  <p>{applicant.candidate_email || 'Email not available'}</p>
                  <span>
                    <BriefcaseBusiness size={12} />
                    {applicant.job_title || 'Job not available'}
                  </span>
                </div>

                <div className="pipeline-match">
                  <strong>
                    {applicant.match_score != null
                      ? `${Math.round(applicant.match_score)}%`
                      : '—'}
                  </strong>
                  <small>Resume Match</small>
                </div>

                <div className="pipeline-candidate-actions">
                  <span className={statusClass(activeStage)}>
                    {stageLabels[activeStage]}
                  </span>

                  {(applicant.resume_id || applicant.resume_url) && (
                    <button
                      className="pipeline-icon-btn"
                      type="button"
                      title="View resume"
                      aria-label={`View resume for ${getCandidateName(applicant)}`}
                      disabled={openingResumeId === applicant.id}
                      onClick={() => openApplicantResume(applicant)}
                    >
                      <FileText size={15} /> {openingResumeId === applicant.id ? 'Opening…' : ''}
                    </button>
                  )}

                  <button
                    className="pipeline-update-btn"
                    onClick={() => openUpdateModal({
                      ...applicant,
                      current_status: activeStage
                    })}
                  >
                    Update Status <ChevronDown size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {selectedApplicant && (
        <div
          className="ss-modal-overlay pipeline-modal-overlay"
          onClick={() => setSelectedApplicant(null)}
        >
          <div
            className="ss-modal pipeline-modal"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="pipeline-status-modal-title"
          >
            <div className="ss-card-head">
              <div>
                <span className="ss-eyebrow">CANDIDATE MANAGEMENT</span>
                <h3 id="pipeline-status-modal-title">Update Applicant Status</h3>
                <p>{getCandidateName(selectedApplicant)}</p>
              </div>

              <button
                className="pipeline-close-btn"
                onClick={() => setSelectedApplicant(null)}
              >
                <X size={18} />
              </button>
            </div>

            <div className="pipeline-modal-body">
              <label>
                New Status
                <select
                  value={newStatus}
                  onChange={(e) => setNewStatus(e.target.value)}
                >
                  {STAGES.map((stage) => (
                    <option key={stage} value={stage}>
                      {stageLabels[stage]}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Notes (Optional)
                <textarea
                  rows={4}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Add feedback or a reason for this status change..."
                />
              </label>

              <div className="pipeline-modal-actions">
                <button
                  className="pipeline-cancel-btn"
                  onClick={() => setSelectedApplicant(null)}
                >
                  Cancel
                </button>

                <button
                  className="ss-primary-btn"
                  onClick={updateStatus}
                  disabled={!!updatingId}
                >
                  {updatingId ? 'Updating...' : 'Save Changes'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
