import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, User, FileText, BriefcaseBusiness, Bookmark, Send,
  ClipboardCheck, BarChart3, Sparkles, Code2, Award, Users, Building2,
  Database, GitCompare, CalendarDays, ShieldCheck, ShieldAlert,
  FileSpreadsheet, Briefcase, MessageCircle, ChevronLeft, ChevronRight
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function Sidebar({ collapsed = false, onToggle }) {
  const { user } = useAuth();
  const role = String(user?.role || 'CANDIDATE').toUpperCase();

  const candidate = [
    ['/candidate/dashboard', 'Dashboard', LayoutDashboard],
    ['/candidate/profile', 'My Profile', User],
    ['/candidate/resumes', 'My Resume', FileText],
    ['/candidate/jobs', 'Explore Jobs', BriefcaseBusiness],
    ['/candidate/saved-jobs', 'Saved Jobs', Bookmark],
    ['/candidate/applications', 'My Applications', Send],
    ['/candidate/assessments', 'Assessments', ClipboardCheck],
    ['/candidate/matching', 'Skill Gap Analysis', BarChart3],
    ['/candidate/interview-practice', 'Interview Practice', Sparkles],
    ['/candidate/technical-assessments', 'Technical Quizzes', Code2],
    ['/candidate/resume-builder', 'Resume Builder', Award],
    ['/candidate/support', 'Support Center', MessageCircle]
  ];

  const recruiter = [
    ['/recruiter/dashboard', 'Dashboard', LayoutDashboard],
    ['/recruiter/jobs', 'Manage Jobs', BriefcaseBusiness],
    ['/recruiter/pipeline', 'Applicants', Users],
    ['/recruiter/question-bank', 'Question Bank', Database],
    ['/recruiter/assessments/results', 'Assessment Results', ClipboardCheck],
    ['/recruiter/interviews', 'Interview Scheduling', CalendarDays],
    ['/recruiter/comparison', 'Compare Candidates', GitCompare],
    ['/recruiter/company', 'Company Profile', Building2],
    ['/recruiter/support', 'Support Center', MessageCircle]
  ];

  const admin = [
    ['/admin/dashboard', 'Dashboard', LayoutDashboard],
    ['/admin/users', 'User Management', Users],
    ['/admin/recruiters', 'Recruiter Verification', ShieldCheck],
    ['/admin/jobs', 'Job Moderation', Briefcase],
    ['/admin/pending-approvals', 'Pending Approvals', ClipboardCheck],
    ['/admin/question-bank', 'Question Bank', Database],
    ['/admin/proctoring', 'Proctoring History', ShieldAlert],
    ['/admin/audit-logs', 'Audit Logs', FileSpreadsheet],
    ['/admin/support', 'Support Center', MessageCircle]
  ];

  const links = role === 'ADMIN' ? admin : role === 'RECRUITER' ? recruiter : candidate;

  return (
    <aside className={`ss-sidebar${collapsed ? ' ss-sidebar-collapsed' : ''}`}>
      <button
        type="button"
        className="ss-sidebar-toggle"
        onClick={onToggle}
        title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {collapsed ? <ChevronRight size={17} /> : <ChevronLeft size={17} />}
      </button>

      <div className={`ss-brand${collapsed ? ' is-collapsed' : ''}`} title="SkillSphere">
        <span className="ss-brand-mark">S</span>
        {!collapsed && <span>SkillSphere</span>}
      </div>

      {!collapsed && (
        <div className="ss-sidebar-label">
          {role === 'ADMIN' ? 'Administration' : role === 'RECRUITER' ? 'Recruiter Portal' : 'Job Seeker Portal'}
        </div>
      )}

      <nav className="ss-sidebar-nav">
        {links.map(([to, label, Icon]) => (
          <NavLink
            key={to}
            to={to}
            end={to.endsWith('dashboard')}
            title={collapsed ? label : undefined}
            className={({ isActive }) => `ss-nav-link${isActive ? ' active' : ''}`}
          >
            <Icon size={17} />
            {!collapsed && <span>{label}</span>}
          </NavLink>
        ))}
      </nav>

      <div className={`ss-sidebar-footer${collapsed ? ' is-collapsed' : ''}`} title={collapsed ? `${user?.full_name || 'User'} · ${role}` : undefined}>
        <div className="ss-avatar-small">
          {(user?.full_name || 'U').split(' ').map(x => x[0]).slice(0, 2).join('').toUpperCase()}
        </div>
        {!collapsed && (
          <div className="ss-sidebar-user">
            <b>{user?.full_name || 'User'}</b>
            <small>{role.toLowerCase()}</small>
          </div>
        )}
      </div>
    </aside>
  );
}
