import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { BriefcaseBusiness, Users, Star, CalendarDays, ArrowUpRight, Plus, UserRoundCheck } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import api from '../../services/api';
import '../candidate/dashboard.css';

const card='ss-card';
export default function RecruiterDashboard(){
 const {user}=useAuth(); const [analytics,setAnalytics]=useState(null); const [jobs,setJobs]=useState([]); const [pipeline,setPipeline]=useState([]); const [loading,setLoading]=useState(true); const [errors,setErrors]=useState([]);
 useEffect(()=>{let active=true;Promise.allSettled([api.get('/recruiter/analytics'),api.get('/recruiter/jobs'),api.get('/recruiter/pipeline')]).then(rs=>{if(!active)return;const e=[];if(rs[0].status==='fulfilled')setAnalytics(rs[0].value.data);else e.push('Analytics');if(rs[1].status==='fulfilled')setJobs(rs[1].value.data||[]);else e.push('Jobs');if(rs[2].status==='fulfilled'){const grouped=rs[2].value.data||{};setPipeline(Array.isArray(grouped)?grouped:Object.entries(grouped).flatMap(([status,rows])=>(rows||[]).map(item=>({...item,current_status:status}))))}else e.push('Pipeline');setErrors(e);setLoading(false)});return()=>{active=false}},[]);
 const stageCount=(...s)=>pipeline.filter(x=>s.includes(String(x.current_status||x.status||'').toUpperCase())).length;
 const stages=[{label:'Applied',value:stageCount('APPLIED')},{label:'In Review',value:stageCount('UNDER_REVIEW')},{label:'Shortlisted',value:stageCount('SHORTLISTED')},{label:'Interview',value:stageCount('INTERVIEW','INTERVIEW_SCHEDULED')}];
 const max=Math.max(1,...stages.map(x=>x.value));
 if(loading)return <div className="ss-loading">Loading recruiter dashboard…</div>;
 return <div className="ss-dashboard"><div className="ss-heading"><div><h1>Welcome, {user?.full_name?.split(' ')[0]||'Recruiter'}!</h1><p>Manage jobs, track applicants and streamline hiring.</p></div><Link className="ss-primary-btn" to="/recruiter/jobs"><Plus size={15}/> Post a job</Link></div>
 {errors.length>0&&<div className="ss-notice">Unable to load: {errors.join(', ')}. Check the backend connection and refresh.</div>}
 <div className="ss-kpis">
  {[{label:'Active Jobs',value:analytics?.active_jobs??0,icon:BriefcaseBusiness},{label:'Total Applicants',value:analytics?.total_applicants??0,icon:Users},{label:'Shortlisted',value:analytics?.shortlisted_applicants??0,icon:Star},{label:'Interviews',value:analytics?.interviews_scheduled??0,icon:CalendarDays}].map((x,i)=><div className={`${card} ss-kpi`} key={x.label}><span className={`ss-kpi-icon ${i===2?'amber':''}`}><x.icon size={19}/></span><div><b>{x.value}</b><small>{x.label}</small></div></div>)}
 </div>
 <div className="ss-two-col"><section className={card}><div className="ss-card-head"><h2>Hiring Pipeline</h2><Link to="/recruiter/pipeline">View applicants <ArrowUpRight size={14}/></Link></div><div className="ss-pipeline-bars">{stages.map((s,i)=><div key={s.label} className="ss-pipeline-stage"><div className="ss-pipeline-track"><div style={{height:`${Math.max(4,s.value/max*100)}%`}}/></div><b>{s.value}</b><small>{s.label}</small></div>)}</div></section>
 <section className={card}><div className="ss-card-head"><h2>Recent Jobs</h2><Link to="/recruiter/jobs">View all <ArrowUpRight size={14}/></Link></div>{jobs.length?<div className="ss-job-list">{jobs.slice(0,5).map(j=><div className="ss-job-row" key={j.id}><div className="ss-company-mark"><BriefcaseBusiness size={15}/></div><div className="ss-job-info"><b>{j.title}</b><small>{j.status||'Status unavailable'} · {j.location||'Location not specified'}</small></div><Link className="ss-small-btn" to="/recruiter/jobs">Manage</Link></div>)}</div>:<div className="ss-empty">No job postings yet. Create your first job to start hiring.</div>}</section></div>
 <div className="ss-two-col"><section className={card}><div className="ss-card-head"><h2>Recruitment Overview</h2><UserRoundCheck size={18}/></div><div className="ss-overview-list"><div><span>Total jobs created</span><b>{analytics?.total_jobs??0}</b></div><div><span>Selected candidates</span><b>{analytics?.selected_candidates??0}</b></div><div><span>Assessment scorecards</span><b>{analytics?.total_applicants??0}</b></div></div></section><section className={card}><div className="ss-card-head"><h2>Quick Actions</h2></div><div className="ss-quick-links vertical"><Link to="/recruiter/jobs"><BriefcaseBusiness size={15}/> Manage job postings</Link><Link to="/recruiter/question-bank"><Star size={15}/> Build an assessment</Link><Link to="/recruiter/interviews"><CalendarDays size={15}/> Schedule interviews</Link><Link to="/recruiter/pipeline"><Users size={15}/> Review applicants</Link></div></section></div>
 </div>
}
