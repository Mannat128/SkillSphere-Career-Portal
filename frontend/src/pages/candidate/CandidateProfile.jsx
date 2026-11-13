import React, { useEffect, useMemo, useState } from 'react';
import { User, GraduationCap, Briefcase, Code2, FolderKanban, Award, Camera, Save, Plus, Trash2, Shield, Bell, Target, RefreshCw, X, CheckCircle2 } from 'lucide-react';
import api from '../../services/api';

const emptyProfile = { headline: '', phone: '', location: '', bio: '' };
const inputStyle = { width: '100%', padding: '10px 12px', border: '1px solid #E7E5DF', borderRadius: 10, background: '#fff', color: '#171914', outlineColor: '#CDF22B' };
const labelStyle = { display: 'block', fontSize: 12, fontWeight: 700, color: '#55584E', marginBottom: 6 };
const buttonStyle = { display: 'inline-flex', alignItems: 'center', gap: 7, padding: '9px 13px', borderRadius: 9, background: '#CDF22B', color: '#10120B', fontWeight: 800, fontSize: 12, cursor: 'pointer' };
const panelStyle = { background: '#fff', border: '1px solid #ECEAE3', borderRadius: 16, padding: 20, boxShadow: '0 5px 18px rgba(20,22,12,.04)' };

function Field({ label, value, onChange, placeholder = '', type = 'text', ...props }) {
  return <label style={{ display: 'block' }}><span style={labelStyle}>{label}</span><input style={inputStyle} type={type} value={value ?? ''} onChange={e => onChange(e.target.value)} placeholder={placeholder} {...props} /></label>;
}
function TextArea({ label, value, onChange, placeholder = '' }) {
  return <label style={{ display: 'block' }}><span style={labelStyle}>{label}</span><textarea style={{ ...inputStyle, minHeight: 90, resize: 'vertical' }} value={value ?? ''} onChange={e => onChange(e.target.value)} placeholder={placeholder} /></label>;
}
function Section({ title, icon: Icon, action, children }) {
  return <section style={panelStyle}><div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 16 }}><h3 style={{ display: 'flex', alignItems: 'center', gap: 9, fontSize: 16, fontWeight: 800, color: '#14160F' }}><Icon size={18} />{title}</h3>{action}</div>{children}</section>;
}
function Empty({ children }) { return <div style={{ padding: '20px 12px', textAlign: 'center', color: '#85877E', fontSize: 13, background: '#FAF9F5', borderRadius: 10 }}>{children}</div>; }

export default function CandidateProfile() {
  const [profile, setProfile] = useState(emptyProfile);
  const [completion, setCompletion] = useState(null);
  const [details, setDetails] = useState({ skills: [], educations: [], experiences: [], projects: [], certifications: [] });
  const [career, setCareer] = useState({ preferred_job_titles: [], preferred_skills: [], preferred_locations: [], work_modes: [], employment_types: [], expected_salary_min: '', expected_salary_max: '', salary_currency: 'INR', notice_period_days: 0, availability_status: 'Immediately', is_open_to_work: true });
  const [visibility, setVisibility] = useState('PUBLIC_TO_RECRUITERS');
  const [alerts, setAlerts] = useState({ keywords: '', preferred_location: '', preferred_job_type: '', experience_level: '', is_active: false });
  const [avatar, setAvatar] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [active, setActive] = useState('profile');
  const [forms, setForms] = useState({});

  const completionPercent = Number(completion?.completion_percentage ?? 0);
  const apiOrigin = useMemo(() => { try { return new URL(api.defaults.baseURL).origin; } catch { return ''; } }, []);
  const refresh = async () => {
    setLoading(true);
    try {
      const [p, c, v, cp, a] = await Promise.all([
        api.get('/candidate/profile'), api.get('/candidate/profile/completion'), api.get('/candidate/profile/visibility'), api.get('/candidate/career-preferences'), api.get('/candidate/alert-preferences')
      ]);
      setProfile({ headline: p.data.headline || '', phone: p.data.phone || '', location: p.data.location || '', bio: p.data.bio || '' });
      setDetails({ skills: p.data.skills || [], educations: p.data.educations || [], experiences: p.data.experiences || [], projects: p.data.projects || [], certifications: p.data.certifications || [] });
      setAvatar(p.data.avatar_url || ''); setCompletion(c.data); setVisibility(v.data.visibility || 'PUBLIC_TO_RECRUITERS');
      setCareer({ ...career, ...cp.data, expected_salary_min: cp.data.expected_salary_min ?? '', expected_salary_max: cp.data.expected_salary_max ?? '' });
      setAlerts(a.data || { keywords: '', preferred_location: '', preferred_job_type: '', experience_level: '', is_active: false });
    } catch (e) { setMessage(e.response?.data?.detail || 'Unable to load complete profile data.'); }
    finally { setLoading(false); }
  };
  useEffect(() => { refresh(); }, []);

  const saveProfile = async (e) => {
    e.preventDefault(); setSaving(true); setMessage('');
    try { await api.put('/candidate/profile', profile); await refresh(); setMessage('Profile details saved successfully.'); }
    catch (e) { setMessage(e.response?.data?.detail || 'Could not save profile details.'); }
    finally { setSaving(false); }
  };
  const uploadAvatar = async (file) => {
    if (!file) return;
    const data = new FormData(); data.append('file', file);
    try { const res = await api.post('/candidate/profile/picture', data, { headers: { 'Content-Type': 'multipart/form-data' } }); setAvatar(res.data.avatar_url); await refresh(); setMessage('Profile picture updated.'); }
    catch (e) { setMessage(e.response?.data?.detail || 'Profile picture upload failed.'); }
  };
  const deleteAvatar = async () => { try { await api.delete('/candidate/profile/picture'); setAvatar(''); await refresh(); setMessage('Profile picture removed.'); } catch (e) { setMessage(e.response?.data?.detail || 'Could not remove picture.'); } };

  const saveCareer = async (e) => {
    e.preventDefault(); setSaving(true);
    const list = v => String(v || '').split(',').map(x => x.trim()).filter(Boolean);
    const payload = { ...career, preferred_job_titles: Array.isArray(career.preferred_job_titles) ? career.preferred_job_titles : list(career.preferred_job_titles), preferred_skills: Array.isArray(career.preferred_skills) ? career.preferred_skills : list(career.preferred_skills), preferred_locations: Array.isArray(career.preferred_locations) ? career.preferred_locations : list(career.preferred_locations), work_modes: Array.isArray(career.work_modes) ? career.work_modes : list(career.work_modes), employment_types: Array.isArray(career.employment_types) ? career.employment_types : list(career.employment_types), expected_salary_min: career.expected_salary_min === '' ? null : Number(career.expected_salary_min), expected_salary_max: career.expected_salary_max === '' ? null : Number(career.expected_salary_max) };
    try { await api.put('/candidate/career-preferences', payload); await refresh(); setMessage('Career preferences saved.'); } catch (e) { setMessage(e.response?.data?.detail || 'Could not save career preferences.'); } finally { setSaving(false); }
  };
  const saveVisibility = async (value) => { setVisibility(value); try { await api.put('/candidate/profile/visibility', { visibility: value }); setMessage('Profile visibility updated.'); } catch (e) { setMessage(e.response?.data?.detail || 'Could not update visibility.'); } };
  const saveAlerts = async (e) => { e.preventDefault(); try { await api.put('/candidate/alert-preferences', alerts); setMessage('Job alert preferences saved.'); } catch (e) { setMessage(e.response?.data?.detail || 'Could not save job alerts.'); } };

  const addRecord = async (kind) => {
    const f = forms[kind] || {};
    const config = {
      educations: { url: '/candidate/education', required: ['institution', 'degree'], payload: { institution: f.institution, degree: f.degree, field_of_study: f.field_of_study || null, graduation_year: f.graduation_year || null, grade: f.grade || null } },
      experiences: { url: '/candidate/experience', required: ['company', 'position'], payload: { company: f.company, position: f.position, location: f.location || null, start_date: f.start_date || null, end_date: f.end_date || null, is_current: !!f.is_current, description: f.description || null } },
      projects: { url: '/candidate/projects', required: ['title'], payload: { title: f.title, description: f.description || null, technologies: f.technologies || null, project_url: f.project_url || null } },
      certifications: { url: '/candidate/certifications', required: ['name', 'issuing_organization'], payload: { name: f.name, issuing_organization: f.issuing_organization, issue_date: f.issue_date || null, credential_url: f.credential_url || null } },
    }[kind];
    if (!config || config.required.some(k => !String(f[k] || '').trim())) { setMessage('Please complete all required fields.'); return; }
    try { await api.post(config.url, config.payload); setForms({ ...forms, [kind]: {} }); await refresh(); setMessage('Record added successfully.'); }
    catch (e) { setMessage(e.response?.data?.detail || 'Could not add record.'); }
  };
  const deleteRecord = async (kind, id) => {
    if (!window.confirm('Delete this record? This cannot be undone.')) return;
    const paths = { educations: `/candidate/education/${id}`, experiences: `/candidate/experience/${id}`, projects: `/candidate/projects/${id}`, certifications: `/candidate/certifications/${id}` };
    try { await api.delete(paths[kind]); await refresh(); setMessage('Record deleted.'); } catch (e) { setMessage(e.response?.data?.detail || 'Could not delete record.'); }
  };
  const editRecord = async (kind, item) => {
    const ask = (label, value = '') => window.prompt(label, value ?? '');
    let payload = null;
    if (kind === 'educations') {
      const institution = ask('Institution', item.institution); if (institution === null) return;
      const degree = ask('Degree', item.degree); if (degree === null) return;
      payload = { institution, degree, field_of_study: ask('Field of study', item.field_of_study) || null, graduation_year: ask('Graduation year', item.graduation_year) || null, grade: ask('Grade', item.grade) || null };
    } else if (kind === 'experiences') {
      const company = ask('Company', item.company); if (company === null) return;
      const position = ask('Position', item.position); if (position === null) return;
      payload = { company, position, location: ask('Location', item.location) || null, start_date: ask('Start date', item.start_date) || null, end_date: ask('End date', item.end_date) || null, is_current: item.is_current, description: ask('Description', item.description) || null };
    } else if (kind === 'projects') {
      const title = ask('Project title', item.title); if (title === null) return;
      payload = { title, description: ask('Description', item.description) || null, technologies: ask('Technologies', item.technologies) || null, project_url: ask('Project URL', item.project_url) || null };
    } else if (kind === 'certifications') {
      const name = ask('Certification name', item.name); if (name === null) return;
      const issuing_organization = ask('Issuing organization', item.issuing_organization); if (issuing_organization === null) return;
      payload = { name, issuing_organization, issue_date: ask('Issue date', item.issue_date) || null, credential_url: ask('Credential URL', item.credential_url) || null };
    }
    const paths = { educations: `/candidate/education/${item.id}`, experiences: `/candidate/experience/${item.id}`, projects: `/candidate/projects/${item.id}`, certifications: `/candidate/certifications/${item.id}` };
    try { await api.put(paths[kind], payload); await refresh(); setMessage('Record updated successfully.'); }
    catch (e) { setMessage(e.response?.data?.detail || 'Could not update record.'); }
  };
  const addSkill = async (e) => { e.preventDefault(); const name = forms.skillName?.trim(); if (!name) return; try { await api.post('/candidate/skills', null, { params: { skill_name: name, proficiency: forms.skillLevel || 'Intermediate' } }); setForms({ ...forms, skillName: '', skillLevel: 'Intermediate' }); await refresh(); setMessage('Skill added.'); } catch (e) { setMessage(e.response?.data?.detail || 'Could not add skill.'); } };
  const deleteSkill = async (id) => { try { await api.delete(`/candidate/skills/${id}`); await refresh(); } catch (e) { setMessage(e.response?.data?.detail || 'Could not remove skill.'); } };

  const tabs = [{ id: 'profile', label: 'Basic profile', icon: User }, { id: 'career', label: 'Career preferences', icon: Target }, { id: 'alerts', label: 'Job alerts', icon: Bell }, { id: 'privacy', label: 'Privacy', icon: Shield }];
  const setForm = (kind, key, value) => setForms(prev => ({ ...prev, [kind]: { ...(prev[kind] || {}), [key]: value } }));
  const commaValue = v => Array.isArray(v) ? v.join(', ') : v || '';

  if (loading) return <div style={{ padding: 36, color: '#777' }}>Loading your profile…</div>;
  return <div style={{ maxWidth: 1180, margin: '0 auto', color: '#171914' }}>
    <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, marginBottom: 22, flexWrap: 'wrap' }}><div><div style={{ color: '#77796F', fontSize: 11, fontWeight: 800, letterSpacing: 1.1, textTransform: 'uppercase' }}>Candidate workspace</div><h1 style={{ fontSize: 26, fontWeight: 900, marginTop: 5 }}>My Profile</h1><p style={{ color: '#77796F', fontSize: 13, marginTop: 4 }}>Manage your professional identity and preferences.</p></div><button onClick={refresh} style={{ ...buttonStyle, background: '#F0EFE9' }}><RefreshCw size={14}/> Refresh</button></header>
    {message && <div style={{ padding: '11px 14px', background: '#F4F8E8', border: '1px solid #DDE9B5', borderRadius: 10, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}><CheckCircle2 size={16}/>{message}<button onClick={() => setMessage('')} style={{ marginLeft: 'auto' }}><X size={15}/></button></div>}
    <div style={{ ...panelStyle, marginBottom: 18, display: 'grid', gridTemplateColumns: 'auto 1fr auto', alignItems: 'center', gap: 16 }}>
      <div style={{ width: 64, height: 64, borderRadius: 50, overflow: 'hidden', background: '#08090B', color: '#CDF22B', display: 'grid', placeItems: 'center', fontWeight: 900, fontSize: 20 }}>{avatar ? <img src={avatar.startsWith('http') ? avatar : `${apiOrigin}${avatar}`} alt="Profile" style={{ width: '100%', height: '100%', objectFit: 'cover' }}/> : ' '}</div>
      <div><div style={{ fontWeight: 900, fontSize: 16 }}>Profile completeness</div><div style={{ height: 8, borderRadius: 20, background: '#ECEBE5', overflow: 'hidden', marginTop: 9 }}><div style={{ height: '100%', width: `${completionPercent}%`, background: '#CDF22B', borderRadius: 20 }}/></div><div style={{ color: '#77796F', fontSize: 12, marginTop: 5 }}>{completionPercent}% complete {completion?.missing_fields?.length ? `· ${completion.missing_fields.length} items remaining` : ''}</div></div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}><label style={buttonStyle}><Camera size={14}/> Upload photo<input type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={e => uploadAvatar(e.target.files?.[0])}/></label>{avatar && <button onClick={deleteAvatar} style={{ ...buttonStyle, background: '#F8E9E6', color: '#A33B2B' }}>Remove</button>}</div>
    </div>
    <div style={{ display: 'flex', gap: 8, borderBottom: '1px solid #E8E6DE', marginBottom: 18, flexWrap: 'wrap' }}>{tabs.map(t => <button key={t.id} onClick={() => setActive(t.id)} style={{ display: 'flex', gap: 7, alignItems: 'center', padding: '11px 13px', borderBottom: active === t.id ? '3px solid #CDF22B' : '3px solid transparent', color: active === t.id ? '#171914' : '#77796F', fontWeight: 800, fontSize: 12 }}>{<t.icon size={15} />}{t.label}</button>)}</div>

    {active === 'profile' && <div style={{ display: 'grid', gap: 16 }}>
      <Section title="Basic information" icon={User}><form onSubmit={saveProfile} style={{ display: 'grid', gap: 13 }}><div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 12 }}><Field label="Professional headline" value={profile.headline} onChange={v => setProfile({ ...profile, headline: v })}/><Field label="Phone number" value={profile.phone} onChange={v => setProfile({ ...profile, phone: v })}/><Field label="Location" value={profile.location} onChange={v => setProfile({ ...profile, location: v })}/></div><TextArea label="Professional bio" value={profile.bio} onChange={v => setProfile({ ...profile, bio: v })}/><div><button disabled={saving} style={buttonStyle}><Save size={14}/>{saving ? 'Saving…' : 'Save profile'}</button></div></form></Section>
      <Section title="Education" icon={GraduationCap} action={<button style={buttonStyle} onClick={() => setForms({ ...forms, showEducation: !forms.showEducation })}><Plus size={14}/> Add education</button>}>
        {details.educations.length ? details.educations.map(x => <div key={x.id} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, padding: 12, borderBottom: '1px solid #F0EFEA' }}><div><b>{x.degree}</b><div style={{ fontSize: 12, color: '#777' }}>{x.institution} {x.field_of_study ? `· ${x.field_of_study}` : ''} {x.graduation_year ? `· ${x.graduation_year}` : ''}</div></div><div style={{display:'flex',gap:10}}><button onClick={() => editRecord('educations', x)} aria-label="Edit education" style={{fontSize:11,fontWeight:800}}>Edit</button><button onClick={() => deleteRecord('educations', x.id)} aria-label="Delete education"><Trash2 size={16}/></button></div></div>) : <Empty>No education records added.</Empty>}
        {forms.showEducation && <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 10, marginTop: 12 }}><Field label="Institution *" value={forms.educations?.institution} onChange={v => setForm('educations','institution',v)}/><Field label="Degree *" value={forms.educations?.degree} onChange={v => setForm('educations','degree',v)}/><Field label="Field of study" value={forms.educations?.field_of_study} onChange={v => setForm('educations','field_of_study',v)}/><Field label="Graduation year" value={forms.educations?.graduation_year} onChange={v => setForm('educations','graduation_year',v)}/><Field label="Grade" value={forms.educations?.grade} onChange={v => setForm('educations','grade',v)}/><button style={buttonStyle} onClick={() => addRecord('educations')}>Save education</button></div>}
      </Section>
      <Section title="Work experience" icon={Briefcase} action={<button style={buttonStyle} onClick={() => setForms({ ...forms, showExperience: !forms.showExperience })}><Plus size={14}/> Add experience</button>}>
        {details.experiences.length ? details.experiences.map(x => <div key={x.id} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, padding: 12, borderBottom: '1px solid #F0EFEA' }}><div><b>{x.position}</b><div style={{ fontSize: 12, color: '#777' }}>{x.company} {x.location ? `· ${x.location}` : ''}</div><div style={{ fontSize: 12, color: '#777' }}>{x.start_date || ''} – {x.is_current ? 'Present' : x.end_date || ''}</div></div><div style={{display:'flex',gap:10}}><button onClick={() => editRecord('experiences', x)} style={{fontSize:11,fontWeight:800}}>Edit</button><button onClick={() => deleteRecord('experiences', x.id)}><Trash2 size={16}/></button></div></div>) : <Empty>No work experience records added.</Empty>}
        {forms.showExperience && <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 10, marginTop: 12 }}><Field label="Company *" value={forms.experiences?.company} onChange={v => setForm('experiences','company',v)}/><Field label="Position *" value={forms.experiences?.position} onChange={v => setForm('experiences','position',v)}/><Field label="Location" value={forms.experiences?.location} onChange={v => setForm('experiences','location',v)}/><Field label="Start date" value={forms.experiences?.start_date} onChange={v => setForm('experiences','start_date',v)}/><Field label="End date" value={forms.experiences?.end_date} onChange={v => setForm('experiences','end_date',v)}/><TextArea label="Description" value={forms.experiences?.description} onChange={v => setForm('experiences','description',v)}/><label style={{ fontSize: 12 }}><input type="checkbox" checked={!!forms.experiences?.is_current} onChange={e => setForm('experiences','is_current',e.target.checked)}/> Current role</label><button style={buttonStyle} onClick={() => addRecord('experiences')}>Save experience</button></div>}
      </Section>
      <Section title="Skills" icon={Code2}><form onSubmit={addSkill} style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}><input style={{ ...inputStyle, flex: '1 1 220px' }} placeholder="Add a skill" value={forms.skillName || ''} onChange={e => setForms({ ...forms, skillName: e.target.value })}/><select style={{ ...inputStyle, width: 150 }} value={forms.skillLevel || 'Intermediate'} onChange={e => setForms({ ...forms, skillLevel: e.target.value })}><option>Beginner</option><option>Intermediate</option><option>Advanced</option><option>Expert</option></select><button style={buttonStyle}><Plus size={14}/> Add skill</button></form><div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>{details.skills.length ? details.skills.map(s => <span key={s.skill_id} style={{ display: 'inline-flex', gap: 8, alignItems: 'center', padding: '7px 10px', borderRadius: 20, background: '#F3F5E8', fontSize: 12, fontWeight: 700 }}>{s.name}<small style={{ color: '#777' }}>{s.proficiency}</small><button onClick={() => deleteSkill(s.skill_id)}><X size={13}/></button></span>) : <Empty>No skills added.</Empty>}</div></Section>
      <Section title="Projects" icon={FolderKanban} action={<button style={buttonStyle} onClick={() => setForms({ ...forms, showProject: !forms.showProject })}><Plus size={14}/> Add project</button>}>{details.projects.length ? details.projects.map(x => <div key={x.id} style={{ display: 'flex', justifyContent: 'space-between', padding: 12, borderBottom: '1px solid #F0EFEA' }}><div><b>{x.title}</b><div style={{ fontSize: 12, color: '#777' }}>{x.technologies}</div></div><div style={{display:'flex',gap:10}}><button onClick={() => editRecord('projects', x)} style={{fontSize:11,fontWeight:800}}>Edit</button><button onClick={() => deleteRecord('projects', x.id)}><Trash2 size={16}/></button></div></div>) : <Empty>No projects added.</Empty>}{forms.showProject && <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 10, marginTop: 12 }}><Field label="Project title *" value={forms.projects?.title} onChange={v => setForm('projects','title',v)}/><Field label="Technologies" value={forms.projects?.technologies} onChange={v => setForm('projects','technologies',v)}/><Field label="Project URL" value={forms.projects?.project_url} onChange={v => setForm('projects','project_url',v)}/><TextArea label="Description" value={forms.projects?.description} onChange={v => setForm('projects','description',v)}/><button style={buttonStyle} onClick={() => addRecord('projects')}>Save project</button></div>}</Section>
      <Section title="Certifications" icon={Award} action={<button style={buttonStyle} onClick={() => setForms({ ...forms, showCertification: !forms.showCertification })}><Plus size={14}/> Add certification</button>}>{details.certifications.length ? details.certifications.map(x => <div key={x.id} style={{ display: 'flex', justifyContent: 'space-between', padding: 12, borderBottom: '1px solid #F0EFEA' }}><div><b>{x.name}</b><div style={{ fontSize: 12, color: '#777' }}>{x.issuing_organization} {x.issue_date ? `· ${x.issue_date}` : ''}</div></div><div style={{display:'flex',gap:10}}><button onClick={() => editRecord('certifications', x)} style={{fontSize:11,fontWeight:800}}>Edit</button><button onClick={() => deleteRecord('certifications', x.id)}><Trash2 size={16}/></button></div></div>) : <Empty>No certifications added.</Empty>}{forms.showCertification && <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 10, marginTop: 12 }}><Field label="Certification *" value={forms.certifications?.name} onChange={v => setForm('certifications','name',v)}/><Field label="Issuing organization *" value={forms.certifications?.issuing_organization} onChange={v => setForm('certifications','issuing_organization',v)}/><Field label="Issue date" value={forms.certifications?.issue_date} onChange={v => setForm('certifications','issue_date',v)}/><Field label="Credential URL" value={forms.certifications?.credential_url} onChange={v => setForm('certifications','credential_url',v)}/><button style={buttonStyle} onClick={() => addRecord('certifications')}>Save certification</button></div>}</Section>
    </div>}

    {active === 'career' && <Section title="Career preferences" icon={Target}><form onSubmit={saveCareer} style={{ display: 'grid', gap: 12 }}><div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 12 }}>{[['preferred_job_titles','Preferred job titles'],['preferred_skills','Preferred skills'],['preferred_locations','Preferred locations'],['work_modes','Work modes (Remote, Hybrid, On-site)'],['employment_types','Employment types']].map(([key,label]) => <Field key={key} label={`${label} · comma separated`} value={commaValue(career[key])} onChange={v => setCareer({ ...career, [key]: v })}/>)}</div><div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', gap: 12 }}><Field label="Minimum salary" type="number" value={career.expected_salary_min} onChange={v => setCareer({ ...career, expected_salary_min: v })}/><Field label="Maximum salary" type="number" value={career.expected_salary_max} onChange={v => setCareer({ ...career, expected_salary_max: v })}/><Field label="Currency" value={career.salary_currency} onChange={v => setCareer({ ...career, salary_currency: v })}/><Field label="Notice period (days)" type="number" value={career.notice_period_days} onChange={v => setCareer({ ...career, notice_period_days: Number(v) })}/></div><label style={{ fontSize: 13, fontWeight: 700 }}><input type="checkbox" checked={!!career.is_open_to_work} onChange={e => setCareer({ ...career, is_open_to_work: e.target.checked })}/> Open to work</label><label style={{ display: 'block' }}><span style={labelStyle}>Availability</span><select style={inputStyle} value={career.availability_status} onChange={e => setCareer({ ...career, availability_status: e.target.value })}><option>Immediately</option><option>Within 15 days</option><option>Within 30 days</option><option>Within 60 days</option><option>Not looking</option></select></label><button style={buttonStyle} disabled={saving}><Save size={14}/> Save preferences</button></form></Section>}
    {active === 'alerts' && <Section title="Job alert preferences" icon={Bell}><form onSubmit={saveAlerts} style={{ display: 'grid', gap: 12 }}><Field label="Keywords" value={alerts.keywords} onChange={v => setAlerts({ ...alerts, keywords: v })}/><div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 12 }}><Field label="Preferred location" value={alerts.preferred_location} onChange={v => setAlerts({ ...alerts, preferred_location: v })}/><Field label="Preferred job type" value={alerts.preferred_job_type} onChange={v => setAlerts({ ...alerts, preferred_job_type: v })}/><Field label="Experience level" value={alerts.experience_level} onChange={v => setAlerts({ ...alerts, experience_level: v })}/></div><label style={{ fontSize: 13, fontWeight: 700 }}><input type="checkbox" checked={!!alerts.is_active} onChange={e => setAlerts({ ...alerts, is_active: e.target.checked })}/> Enable job alerts</label><button style={buttonStyle}><Save size={14}/> Save alerts</button></form></Section>}
    {active === 'privacy' && <Section title="Profile privacy" icon={Shield}><p style={{ color: '#77796F', fontSize: 13, marginBottom: 14 }}>Control whether recruiters can discover your profile.</p><div style={{ display: 'grid', gap: 10 }}><label style={{ ...panelStyle, display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}><input type="radio" checked={visibility === 'PUBLIC_TO_RECRUITERS'} onChange={() => saveVisibility('PUBLIC_TO_RECRUITERS')}/><span><b style={{ display: 'block' }}>Visible to recruiters</b><small style={{ color: '#777' }}>Recruiters can discover your profile for relevant roles.</small></span></label><label style={{ ...panelStyle, display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}><input type="radio" checked={visibility === 'PRIVATE'} onChange={() => saveVisibility('PRIVATE')}/><span><b style={{ display: 'block' }}>Private</b><small style={{ color: '#777' }}>Your profile is hidden from recruiter discovery.</small></span></label></div></Section>}
  </div>;
}
