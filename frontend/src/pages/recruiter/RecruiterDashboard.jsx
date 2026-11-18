
import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  BriefcaseBusiness,
  Users,
  UserCheck,
  CalendarDays,
  ArrowUpRight,
  ClipboardList,
  Building2,
  BarChart3,
  Plus
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import api from '../../services/api';
import '../candidate/dashboard.css';

const card = 'ss-card';

export default function RecruiterDashboard() {
  const { user } = useAuth();

  const [analytics, setAnalytics] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errors, setErrors] = useState([]);

  useEffect(() => {
    let active = true;

    Promise.allSettled([
      api.get('/recruiter/analytics'),
      api.get('/recruiter/jobs')
    ]).then(results => {
      if (!active) return;

      const failed = [];

      if (results[0].status === 'fulfilled') {
        setAnalytics(results[0].value.data);
      } else {
        failed.push('Recruitment analytics');
      }

      if (results[1].status === 'fulfilled') {
        setJobs(Array.isArray(results[1].value.data)
          ? results[1].value.data
          : []);
      } else {
        failed.push('Job listings');
      }

      setErrors(failed);
      setLoading(false);
    });

    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return <div className="ss-loading">Loading recruiter dashboard…</div>;
  }

  const stats = analytics || {};
  const jobStats = Array.isArray(stats.job_statistics)
    ? stats.job_statistics
    : [];

  const maxApplicants = Math.max(
    1,
    ...jobStats.map(item => Number(item.applicants || 0))
  );

  const greeting = new Date().getHours() < 12
    ? 'Morning'
    : new Date().getHours() < 17
      ? 'Afternoon'
      : 'Evening';

  const kpis = [
    {
      label: 'Total Jobs',
      value: stats.total_jobs ?? 0,
      icon: BriefcaseBusiness,
      color: ''
    },
    {
      label: 'Active Jobs',
      value: stats.active_jobs ?? 0,
      icon: ClipboardList,
      color: 'amber'
    },
    {
      label: 'Total Applicants',
      value: stats.total_applicants ?? 0,
      icon: Users,
      color: 'violet'
    },
    {
      label: 'Shortlisted',
      value: stats.shortlisted_applicants ?? 0,
      icon: UserCheck,
      color: ''
    }
  ];

  return (
    <div className="ss-dashboard">

      <div className="ss-heading">
        <div>
          <h1>
            Good {greeting}, {user?.full_name?.split(' ')[0] || 'Recruiter'}!
          </h1>
          <p>Manage your hiring process and track recruitment performance.</p>
        </div>

        <Link className="ss-primary-btn" to="/recruiter/jobs">
          <Plus size={15} />
          Manage Jobs
          <ArrowUpRight size={14} />
        </Link>
      </div>

      {errors.length > 0 && (
        <div className="ss-notice">
          Unable to load: {errors.join(', ')}. Please refresh after checking the API connection.
        </div>
      )}

      <div className="ss-kpis">
        {kpis.map(item => {
          const Icon = item.icon;

          return (
            <div className={`${card} ss-kpi`} key={item.label}>
              <span className={`ss-kpi-icon ${item.color}`}>
                <Icon size={19} />
              </span>
              <div>
                <b>{item.value}</b>
                <small>{item.label}</small>
              </div>
            </div>
          );
        })}
      </div>

      <div className="ss-two-col">

        <section className={card}>
          <div className="ss-card-head">
            <h2>Job-wise Applicants</h2>
            <BarChart3 size={18} />
          </div>

          {jobStats.length > 0 ? (
            <div className="ss-pipeline-bars">
              {jobStats.slice(0, 6).map((item, index) => (
                <div className="ss-pipeline-stage" key={`${item.job_title}-${index}`}>
                  <b>{item.applicants}</b>

                  <div className="ss-pipeline-track">
                    <div
                      style={{
                        height: `${Math.max(
                          3,
                          (Number(item.applicants || 0) / maxApplicants) * 100
                        )}%`
                      }}
                    />
                  </div>

                  <small title={item.job_title}>
                    {item.job_title?.length > 13
                      ? `${item.job_title.slice(0, 13)}…`
                      : item.job_title}
                  </small>
                </div>
              ))}
            </div>
          ) : (
            <div className="ss-empty">
              No job application statistics available yet.
            </div>
          )}
        </section>

        <section className={card}>
          <div className="ss-card-head">
            <h2>Recruitment Overview</h2>
            <BarChart3 size={18} />
          </div>

          <div className="ss-overview-list">
            <div>
              <span>Total Applicants</span>
              <b>{stats.total_applicants ?? 0}</b>
            </div>

            <div>
              <span>Shortlisted Candidates</span>
              <b>{stats.shortlisted_applicants ?? 0}</b>
            </div>

            <div>
              <span>Interviews Scheduled</span>
              <b>{stats.interviews_scheduled ?? 0}</b>
            </div>

            <div>
              <span>Selected Candidates</span>
              <b>{stats.selected_candidates ?? 0}</b>
            </div>
          </div>

          <div className="ss-quick-links vertical">
            <Link to="/recruiter/pipeline">
              <Users size={15} />
              Manage Applicant Pipeline
              <ArrowUpRight size={13} />
            </Link>

            <Link to="/recruiter/assessments/results">
              <ClipboardList size={15} />
              Assessment Results
              <ArrowUpRight size={13} />
            </Link>
          </div>
        </section>

      </div>

      <div className="ss-two-col">

        <section className={card}>
          <div className="ss-card-head">
            <h2>Recent Job Postings</h2>
            <Link to="/recruiter/jobs">
              View all <ArrowUpRight size={14} />
            </Link>
          </div>

          {jobs.length > 0 ? (
            <div className="ss-job-list">
              {jobs.slice(0, 5).map(job => (
                <div className="ss-job-row" key={job.id}>
                  <div className="ss-company-mark">
                    <BriefcaseBusiness size={16} />
                  </div>

                  <div className="ss-job-info">
                    <b>{job.title}</b>
                    <small>
                      {job.location || 'Location not specified'}
                      {' · '}
                      {job.total_applicants ?? 0} applicants
                    </small>
                  </div>

                  <span className="ss-status-pill">
                    {String(job.status || 'UNKNOWN')
                      .replaceAll('_', ' ')}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="ss-empty">
              No jobs posted yet. Create your first job posting.
            </div>
          )}
        </section>

        <section className={card}>
          <div className="ss-card-head">
            <h2>Recruiter Workspace</h2>
            <Building2 size={18} />
          </div>

          <div className="ss-quick-links vertical">
            <Link to="/recruiter/company">
              <Building2 size={15} />
              Company Profile
              <ArrowUpRight size={13} />
            </Link>

            <Link to="/recruiter/jobs">
              <BriefcaseBusiness size={15} />
              Manage Job Postings
              <ArrowUpRight size={13} />
            </Link>

            <Link to="/recruiter/question-bank">
              <ClipboardList size={15} />
              Assessment Question Bank
              <ArrowUpRight size={13} />
            </Link>

            <Link to="/recruiter/interviews">
              <CalendarDays size={15} />
              Interview Scheduler
              <ArrowUpRight size={13} />
            </Link>

            <Link to="/recruiter/comparison">
              <Users size={15} />
              Compare Candidates
              <ArrowUpRight size={13} />
            </Link>
          </div>
        </section>

      </div>

    </div>
  );
}
