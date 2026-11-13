import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { BriefcaseBusiness, Bookmark, ClipboardCheck, BarChart3, ArrowUpRight, CircleUserRound, FileText, Sparkles, CalendarDays } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import api from '../../services/api';
import './dashboard.css';

const card = 'ss-card';
const statusLabel = value => String(value || 'APPLIED').replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
export default function CandidateDashboard() {
  const { user } = useAuth();
  const [profile, setProfile] = useState(null);
  const [completion, setCompletion] = useState(null);
  const [applications, setApplications] = useState([]);
  const [savedJobs, setSavedJobs] = useState([]);
  const [assessments, setAssessments] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errors, setErrors] = useState([]);

  useEffect(() => {
    let active = true;
    Promise.allSettled([
      api.get('/candidate/profile'), api.get('/candidate/profile/completion'), api.get('/applications'),
      api.get('/jobs/saved'), api.get('/candidate/first-round-assessments'), api.get('/jobs', { params: { page: 1, page_size: 5 } })
    ]).then(results => {
      if (!active) return;
      const setters = [setProfile, setCompletion, setApplications, setSavedJobs, setAssessments, setJobs];
      const errs = [];
      results.forEach((r, i) => {
        if (r.status === 'fulfilled') {
          let data = r.value.data;
          if (i === 1) setters[i](data);
          else if (i === 5) setters[i](data.items || data.jobs || []);
          else setters[i](data);
        } else errs.push(['Profile','Completion','Applications','Saved jobs','Assessments','Recommended jobs'][i]);
      });
      setErrors(errs); setLoading(false);
    });
    return () => { active = false; };
  }, []);

  const apps = Array.isArray(applications) ? applications : [];
  const saved = Array.isArray(savedJobs) ? savedJobs : [];
  const tests = Array.isArray(assessments) ? assessments : [];
  const pendingTests = tests.filter(x => ['PENDING','ASSIGNED','IN_PROGRESS'].includes(String(x.status || x.assignment_status || '').toUpperCase()));
  const shortlisted = apps.filter(x => ['SHORTLISTED'].includes(String(x.current_status || '').toUpperCase())).length;
  const interviewCount = apps.filter(x => ['INTERVIEW','INTERVIEW_SCHEDULED'].includes(String(x.current_status || '').toUpperCase())).length;
  const appliedCount = apps.filter(x => ['APPLIED','UNDER_REVIEW'].includes(String(x.current_status || '').toUpperCase())).length;
  const percent = Number(completion?.completion_percentage ?? profile?.profile_percentage ?? 0);
  const statusSegments = useMemo(() => [
    { label: 'Applied', value: appliedCount, color: '#11130D' },
    { label: 'In Review', value: apps.filter(x => x.current_status === 'UNDER_REVIEW').length, color: '#CDF22B' },
    { label: 'Interview', value: interviewCount, color: '#A8CC25' },
    { label: 'Not Selected', value: apps.filter(x => x.current_status === 'REJECTED').length, color: '#D8D8D2' },
  ], [apps, appliedCount, interviewCount]);
  const total = statusSegments.reduce((a,b)=>a+b.value,0);
  let running = 0;
  const gradient = statusSegments.map(s => { const start=running; running += total ? s.value/total*100 : 0; return `${s.color} ${start}% ${running}%`; }).join(', ');

  if (loading) return <div className="ss-loading">Loading your dashboard…</div>;
  return <div className="ss-dashboard">
    <div className="ss-heading"><div><h1>Good {new Date().getHours()<12?'Morning':new Date().getHours()<17?'Afternoon':'Evening'}, {user?.full_name?.split(' ')[0] || 'there'}!</h1><p>Track your progress and discover new opportunities.</p></div><Link className="ss-primary-btn" to="/candidate/jobs">Explore jobs <ArrowUpRight size={15}/></Link></div>
    {errors.length > 0 && <div className="ss-notice">Some dashboard sections could not load: {errors.join(', ')}. Refresh after checking the API connection.</div>}
    {pendingTests.length > 0 && <div className="ss-alert"><ClipboardCheck size={19}/><div><b>You have {pendingTests.length} assessment{pendingTests.length===1?'':'s'} to complete</b><span>Review your assigned first-round assessments.</span></div><Link to="/candidate/assessments">View assessments <ArrowUpRight size={14}/></Link></div>}
    <div className="ss-kpis">
      <div className={`${card} ss-kpi ss-kpi-progress`}><div className="ss-ring" style={{'--progress':`${Math.min(100,Math.max(0,percent))}%`}}><span>{percent}%</span></div><div><b>Profile Complete</b><small>Profile strength</small></div></div>
      <div className={`${card} ss-kpi`}><span className="ss-kpi-icon"><BriefcaseBusiness size={19}/></span><div><b>{apps.length}</b><small>Applications</small></div></div>
      <div className={`${card} ss-kpi`}><span className="ss-kpi-icon amber"><Bookmark size={19}/></span><div><b>{saved.length}</b><small>Saved Jobs</small></div></div>
      <div className={`${card} ss-kpi`}><span className="ss-kpi-icon violet"><BarChart3 size={19}/></span><div><b>{tests.length}</b><small>Assessments</small></div></div>
    </div>
    <div className="ss-two-col">
      <section className={card}><div className="ss-card-head"><h2>Recommended Jobs</h2><Link to="/candidate/jobs">View all <ArrowUpRight size={14}/></Link></div>
        {jobs.length ? <div className="ss-job-list">{jobs.slice(0,5).map(job=><div className="ss-job-row" key={job.id}><div className="ss-company-mark">{(job.company?.name || job.company_name || 'C').slice(0,1).toUpperCase()}</div><div className="ss-job-info"><b>{job.title}</b><small>{job.company?.name || job.company_name || 'Company'} · {job.location || 'Location not specified'}</small></div><Link className="ss-small-btn" to={`/candidate/jobs`}>Explore</Link></div>)}</div> : <div className="ss-empty">No recommended jobs available right now.</div>}
      </section>
      <section className={card}><div className="ss-card-head"><h2>Application Status</h2><Link to="/candidate/applications">Details <ArrowUpRight size={14}/></Link></div><div className="ss-status-content"><div className="ss-donut" style={{background:total ? `conic-gradient(${gradient})` : '#E9E9E3'}}><div><b>{total}</b><small>Applications</small></div></div><div className="ss-legend">{statusSegments.map(s=><div key={s.label}><i style={{background:s.color}}/><span>{s.label}</span><b>{s.value}</b></div>)}</div></div></section>
    </div>
    <div className="ss-two-col ss-bottom-grid"><section className={card}><div className="ss-card-head"><h2>Recent Applications</h2><Link to="/candidate/applications">View all <ArrowUpRight size={14}/></Link></div>{apps.length ? <div className="ss-job-list">{apps.slice(0,4).map(app=><div className="ss-job-row" key={app.id}><div className="ss-company-mark"><BriefcaseBusiness size={16}/></div><div className="ss-job-info"><b>{app.job?.title || `Job #${app.job_id}`}</b><small>{app.job?.company?.name || 'Company'} · {app.applied_at ? new Date(app.applied_at).toLocaleDateString() : 'Date unavailable'}</small></div><span className="ss-status-pill">{statusLabel(app.current_status)}</span></div>)}</div> : <div className="ss-empty">You haven't applied to any jobs yet. Explore opportunities to get started.</div>}</section>
      <section className={card}><div className="ss-card-head"><h2>Profile Readiness</h2><CircleUserRound size={18}/></div><div className="ss-profile-progress"><div className="ss-ring large" style={{'--progress':`${Math.min(100,Math.max(0,percent))}%`}}><span>{percent}%</span></div><div><b>{percent >= 80 ? 'Looking good!' : 'Build a stronger profile'}</b><p>{completion?.missing_fields?.length ? `Complete ${completion.missing_fields.length} remaining profile sections to improve recruiter visibility.` : 'Keep your experience and skills up to date.'}</p><Link to="/candidate/profile">Update profile <ArrowUpRight size={14}/></Link></div></div><div className="ss-quick-links"><Link to="/candidate/resumes"><FileText size={15}/> My resumes</Link><Link to="/candidate/interview-practice"><Sparkles size={15}/> Interview practice</Link><Link to="/candidate/assessments"><CalendarDays size={15}/> Assessments</Link></div></section></div>
  </div>;
}
