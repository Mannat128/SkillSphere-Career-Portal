import React, { useState, useEffect } from 'react';
import {
  Building,
  Globe,
  MapPin,
  Users,
  Save,
  CheckCircle,
} from 'lucide-react';
import api from '../../services/api';

export default function CompanyProfile() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [company, setCompany] = useState({
    name: '',
    website: '',
    industry: '',
    description: '',
    headquarters: '',
    company_size: '50-200',
  });

  useEffect(() => {
    fetchCompany();
  }, []);

  const fetchCompany = async () => {
    setLoading(true);
    try {
      const res = await api.get('/recruiter/company');
      const data = res.data;
      setCompany({
        name: data.name || '',
        website: data.website || '',
        industry: data.industry || 'Technology',
        description: data.description || '',
        headquarters: data.headquarters || '',
        company_size: data.company_size || '50-200',
      });
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setSaveSuccess(false);

    try {
      await api.put('/recruiter/company', company);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2500);
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to update company profile');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div style={{ padding: '50px', textAlign: 'center', color: 'var(--text-muted)' }}>Loading company profile...</div>;
  }

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      <div className="page-header">
        <div>
          <h2 className="page-title">Company Profile</h2>
          <p className="page-subtitle">
            Configure your employer branding details displayed on job postings and applicant dashboards.
          </p>
        </div>
      </div>

      {saveSuccess && (
        <div style={{ padding: '14px 18px', background: '#ECFDF5', color: '#065F46', borderRadius: '10px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <CheckCircle size={18} />
          <span>Company profile updated successfully!</span>
        </div>
      )}

      <div className="card" style={{ padding: '32px' }}>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Company Name *</label>
            <input
              type="text"
              required
              className="form-input"
              value={company.name}
              onChange={(e) => setCompany({ ...company, name: e.target.value })}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div className="form-group">
              <label className="form-label">Company Website</label>
              <input
                type="text"
                placeholder="https://example.com"
                className="form-input"
                value={company.website}
                onChange={(e) => setCompany({ ...company, website: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Industry</label>
              <input
                type="text"
                placeholder="e.g. Cloud Computing / FinTech"
                className="form-input"
                value={company.industry}
                onChange={(e) => setCompany({ ...company, industry: e.target.value })}
              />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div className="form-group">
              <label className="form-label">Headquarters Location</label>
              <input
                type="text"
                placeholder="e.g. San Francisco, CA"
                className="form-input"
                value={company.headquarters}
                onChange={(e) => setCompany({ ...company, headquarters: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Company Size</label>
              <select
                className="form-select"
                value={company.company_size}
                onChange={(e) => setCompany({ ...company, company_size: e.target.value })}
              >
                <option value="1-10">1-10 Employees</option>
                <option value="11-50">11-50 Employees</option>
                <option value="50-200">50-200 Employees</option>
                <option value="200-1000">200-1,000 Employees</option>
                <option value="1000+">1,000+ Employees</option>
              </select>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">About the Company</label>
            <textarea
              rows={4}
              placeholder="Describe company mission, engineering culture, and products..."
              className="form-textarea"
              value={company.description}
              onChange={(e) => setCompany({ ...company, description: e.target.value })}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '24px' }}>
            <button type="submit" disabled={saving} className="btn btn-primary" style={{ padding: '12px 24px' }}>
              <Save size={18} /> {saving ? 'Saving...' : 'Save Company Details'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
