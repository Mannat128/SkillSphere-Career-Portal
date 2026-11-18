import React, { useCallback, useEffect, useState } from 'react';
import {
  RefreshCw,
  ShieldCheck,
  BriefcaseBusiness,
  CheckCircle2,
  XCircle,
  MapPin,
  CalendarDays
} from 'lucide-react';

import api from '../../services/api';
import './AdminDashboard.css';
import './PendingApprovals.css';

const asText = (value) => String(value ?? '').replaceAll('_', ' ');

export default function PendingApprovals() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyKey, setBusyKey] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');

    try {
      const jobsResponse = await api.get('/admin/jobs', {
        params: { status: 'MODERATION_PENDING' }
      });

      setJobs(
        Array.isArray(jobsResponse.data)
          ? jobsResponse.data
          : []
      );
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Unable to load pending job approvals.'
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const reviewJob = async (job, new_status) => {
    const notes = new_status === 'MODERATION_REJECTED'
      ? window.prompt('Enter the reason for rejecting this job:')
      : '';

    if (
      new_status === 'MODERATION_REJECTED' &&
      !notes?.trim()
    ) {
      return;
    }

    const action = new_status === 'PUBLISHED'
      ? 'approve'
      : 'reject';

    if (
      !window.confirm(
        `Are you sure you want to ${action} this job?`
      )
    ) {
      return;
    }

    const key = `job-${job.id}`;

    setBusyKey(key);
    setError('');
    setNotice('');

    try {
      await api.put(
        `/admin/jobs/${job.id}/moderate`,
        null,
        {
          params: {
            new_status,
            notes: notes?.trim() || undefined
          }
        }
      );

      setNotice(
        `Job ${action === 'approve' ? 'approved' : 'rejected'} successfully.`
      );

      await load();
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Could not update job approval.'
      );
    } finally {
      setBusyKey('');
    }
  };

  return (
    <div className="ss-dashboard ss-pending-page">
      <div className="ss-heading">
        <div>
          <div className="ss-pending-eyebrow">
            <ShieldCheck size={14} />
            ADMIN REVIEW CENTER
          </div>

          <h1>Pending Job Approvals</h1>

          <p>
            Review recruiter job postings before they become visible
            to candidates.
          </p>
        </div>

        <button
          className="ss-primary-btn"
          onClick={load}
          disabled={loading}
        >
          <RefreshCw
            size={14}
            className={loading ? 'ss-pending-spin' : ''}
          />
          Refresh
        </button>
      </div>

      {error && (
        <div className="ss-notice">
          {error}
        </div>
      )}

      {notice && (
        <div className="ss-pending-success">
          {notice}
        </div>
      )}

      {loading ? (
        <div className="ss-loading">
          Loading pending job approvals…
        </div>
      ) : (
        <section className="ss-card ss-pending-section">
          <div className="ss-pending-section-head">
            <div>
              <h2>
                <BriefcaseBusiness size={18} />
                Job Approval
              </h2>

              <p>
                Approve jobs to publish them or reject them
                with a reason.
              </p>
            </div>

            <span>
              {jobs.length} Pending
            </span>
          </div>

          {jobs.length ? (
            <div className="ss-table-wrap">
              <table className="ss-table ss-pending-table">
                <thead>
                  <tr>
                    <th>Job</th>
                    <th>Company</th>
                    <th>Location</th>
                    <th>Employment</th>
                    <th>Submitted</th>
                    <th>Actions</th>
                  </tr>
                </thead>

                <tbody>
                  {jobs.map((job) => (
                    <tr key={job.id}>
                      <td>
                        <b>
                          {job.title || 'Untitled job'}
                        </b>

                        <small>
                          Job #{job.id}
                        </small>
                      </td>

                      <td>
                        {job.company_name || '—'}
                      </td>

                      <td>
                        <span className="ss-pending-inline">
                          <MapPin size={13} />
                          {job.location || '—'}
                        </span>
                      </td>

                      <td>
                        {asText(job.employment_type) || '—'}
                      </td>

                      <td>
                        <span className="ss-pending-inline">
                          <CalendarDays size={13} />

                          {job.created_at
                            ? new Date(
                                job.created_at
                              ).toLocaleDateString()
                            : '—'}
                        </span>
                      </td>

                      <td>
                        <div className="ss-action-group">
                          <button
                            className="ss-small-btn"
                            disabled={
                              busyKey === `job-${job.id}`
                            }
                            onClick={() =>
                              reviewJob(job, 'PUBLISHED')
                            }
                          >
                            <CheckCircle2 size={13} />
                            Approve
                          </button>

                          <button
                            className="ss-small-btn danger"
                            disabled={
                              busyKey === `job-${job.id}`
                            }
                            onClick={() =>
                              reviewJob(
                                job,
                                'MODERATION_REJECTED'
                              )
                            }
                          >
                            <XCircle size={13} />
                            Reject
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="ss-pending-empty">
              <BriefcaseBusiness size={24} />

              <b>
                No pending job approvals
              </b>

              <p>
                New jobs submitted by recruiters will appear here.
              </p>
            </div>
          )}
        </section>
      )}
    </div>
  );
}